"""Fast, reusable NAV retrieval for the mutual-fund Portfolio Builder.

Portfolio analysis needs complete NAV histories for a small set of funds. The
old route fetched each fund independently even though TigZig already exposes a
multi-scheme query. This service uses one synchronous TigZig batch query in a
worker thread, caches successful histories briefly, and falls back concurrently
only for schemes missing from the batch result.
"""

import asyncio
import time
from typing import Any

from backend.models.mutual_fund import NAVRecord
from backend.services.data.tigzig import TigZigDatasetError, get_tigzig_dataset
from backend.services.mutual_funds.fetcher import MutualFundFetcher
from backend.utils.logging import logger


_nav_cache: dict[str, tuple[list[NAVRecord], float]] = {}
_CACHE_TTL_SECONDS = 300


def _cache_get(code: str) -> list[NAVRecord] | None:
    cached = _nav_cache.get(code)
    if cached is None:
        return None
    records, expires = cached
    if time.time() >= expires:
        _nav_cache.pop(code, None)
        return None
    return records


def _cache_put(code: str, records: list[NAVRecord]) -> None:
    if len(records) >= 2:
        _nav_cache[code] = (records, time.time() + _CACHE_TTL_SECONDS)


async def fetch_complete_nav_histories(
    fetcher: MutualFundFetcher,
    scheme_codes: list[str],
) -> dict[str, list[NAVRecord]]:
    """Fetch complete NAV histories for all unique scheme codes.

    Uses the TigZig bulk query for all cache misses. Missing/failed schemes use
    the existing per-scheme fetcher concurrently, preserving the existing
    TigZig -> MFAPI fallback behavior.
    """
    unique_codes = list(dict.fromkeys(code.strip() for code in scheme_codes if code and code.strip()))
    result: dict[str, list[NAVRecord]] = {}
    missing: list[str] = []

    for code in unique_codes:
        cached = _cache_get(code)
        if cached is not None:
            result[code] = cached
        else:
            missing.append(code)

    if not missing:
        logger.info("TIMING: portfolio NAV batch CACHE HIT | schemes=%d", len(unique_codes))
        return result

    dataset = get_tigzig_dataset()
    if dataset.is_available:
        started = time.perf_counter()
        try:
            raw_by_code = await asyncio.to_thread(
                dataset.query_nav,
                [int(code) for code in missing],
                None,
                None,
            )
            logger.info(
                "TIMING: portfolio NAV batch TigZig | schemes=%d | rows=%d | %.3f sec",
                len(missing),
                sum(len(rows) for rows in raw_by_code.values()),
                time.perf_counter() - started,
            )
            for code in missing:
                rows = raw_by_code.get(int(code), [])
                if len(rows) >= 2:
                    records = [NAVRecord(date=row["date"], nav=row["nav"]) for row in rows]
                    result[code] = records
                    _cache_put(code, records)
        except (TigZigDatasetError, ValueError, TypeError) as exc:
            logger.warning("Portfolio NAV batch TigZig query failed: %s", exc)
        except Exception as exc:
            logger.warning("Portfolio NAV batch unexpected failure: %s", exc)

    fallback_codes = [code for code in missing if code not in result]
    if fallback_codes:
        started = time.perf_counter()
        semaphore = asyncio.Semaphore(8)

        async def fallback(code: str) -> tuple[str, list[NAVRecord]]:
            async with semaphore:
                try:
                    records = await fetcher.get_nav_history(code, lookback_years=None)
                    return code, records
                except Exception as exc:
                    logger.warning("Portfolio NAV fallback failed for %s: %s", code, exc)
                    return code, []

        fallback_results = await asyncio.gather(*(fallback(code) for code in fallback_codes))
        for code, records in fallback_results:
            if len(records) >= 2:
                result[code] = records
                _cache_put(code, records)
        logger.info(
            "TIMING: portfolio NAV fallback | schemes=%d | successful=%d | %.3f sec",
            len(fallback_codes),
            sum(1 for _, records in fallback_results if len(records) >= 2),
            time.perf_counter() - started,
        )

    return result
