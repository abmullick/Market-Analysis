import asyncio
import time
from datetime import datetime, timedelta
from typing import Any

from backend.config.settings import Settings
from backend.models.mutual_fund import MutualFund, NAVRecord, SchemeSearchResult
from backend.services.data.amfi import AmfiClient
from backend.services.data.mfapi import MfapiClient, MfapiError
from backend.services.mutual_funds.cache import metrics_cache
from backend.services.mutual_funds.lookback import (
    get_date_range_for_lookback,
    get_required_lookback_years,
)
from backend.services.mutual_funds.normalizer import (
    normalize_nav_history,
    normalize_scheme,
)
from backend.utils.logging import logger

from backend.services.data.tigzig import get_tigzig_dataset, get_tigzig_metadata, TigZigDatasetError
from backend.services.mutual_funds.calculator import MetricsCalculator
from backend.services.mutual_funds.fund_grouper import (
    FundGrouper,
    normalize_fund_name,
    select_ranking_candidate,
)
from backend.services.mutual_funds.category_normalizer import normalize_category


class MutualFundFetcher:
    def __init__(self, settings: Settings):
        self.mfapi = MfapiClient(settings=settings)
        self.amfi = AmfiClient(settings=settings)
        self.cache_ttl = settings.cache_ttl_seconds
        self._schemes_cache: dict[str, tuple[list[MutualFund], float]] = {}
        self._scheme_cache: dict[str, tuple[MutualFund, float]] = {}
        self._underlying_funds_cache: tuple[list[dict[str, Any]], float] | None = None

    async def get_scheme(self, scheme_code: str) -> MutualFund:
        cached, expires = self._scheme_cache.get(scheme_code, (None, 0))
        if cached and time.time() < expires:
            logger.info("Returning cached scheme: %s", scheme_code)
            return cached

        raw = await self.mfapi.fetch_scheme(scheme_code)
        scheme = normalize_scheme(raw)
        self._scheme_cache[scheme_code] = (scheme, time.time() + self.cache_ttl)
        return scheme

    async def get_nav_history(
        self,
        scheme_code: str,
        lookback_years: int | None = None,
    ) -> list[NAVRecord]:
        start_date = None
        end_date = None
        if lookback_years:
            start_date, end_date = get_date_range_for_lookback(lookback_years)

        dataset = get_tigzig_dataset()
        if dataset.is_available:
            try:
                result = await self.get_nav_history_tigzig(scheme_code, lookback_years)
                if result:
                    return result
                logger.debug(f"TigZig returned no data for {scheme_code}, falling back to MFAPI")
            except Exception as e:
                logger.warning(f"TigZig query failed for {scheme_code}: {e}, falling back to MFAPI")

        try:
            raw = await self.mfapi.fetch_nav_history(scheme_code, start_date=start_date, end_date=end_date)
        except MfapiError as e:
            raise MfapiError(f"Failed to fetch NAV history for scheme {scheme_code}: {e}") from e
        records = normalize_nav_history(raw)
        logger.debug(
            "NAV history for %s: %d records (lookback=%s years)",
            scheme_code,
            len(records),
            lookback_years or "full",
        )
        return records

    async def get_or_compute_metrics(
        self,
        scheme_code: str,
        lookback_years: int,
    ) -> dict[str, Any] | None:
        cached = metrics_cache.get(scheme_code, lookback_years)
        if cached is not None:
            logger.info("CACHE HIT: %s (%d-year lookback)", scheme_code, lookback_years)
            return cached

        logger.info("CACHE MISS: %s (%d-year lookback)", scheme_code, lookback_years)
        try:
            navs = await self.get_nav_history(scheme_code, lookback_years=lookback_years)
        except Exception as e:
            logger.warning("NAV fetch failed for %s: %s", scheme_code, e)
            return None

        if len(navs) < 2:
            logger.warning("Insufficient NAV data for %s: %d records", scheme_code, len(navs))
            return None

        try:
            calculator = MetricsCalculator(scheme_code=scheme_code, nav_records=navs)
            metrics = calculator.calculate().model_dump()
        except Exception as e:
            logger.warning("Metric calculation failed for %s: %s", scheme_code, e)
            return None

        metrics_cache.put(scheme_code, lookback_years, metrics)
        return metrics

    async def get_metrics(
        self,
        scheme_code: str,
        scheme_name: str,
        criteria_names: list[str],
    ) -> dict[str, Any] | None:
        lookback_years = get_required_lookback_years(criteria_names)
        cached = metrics_cache.get(scheme_code, lookback_years)
        if cached is not None:
            logger.info("CACHE HIT: %s (%d-year lookback)", scheme_code, lookback_years)
            return cached

        logger.info("CACHE MISS: %s (%d-year lookback)", scheme_code, lookback_years)
        from backend.services.mutual_funds.calculator import MetricsCalculator
        t0 = time.time()
        try:
            navs = await self.get_nav_history(scheme_code, lookback_years=lookback_years)
            fetch_time = time.time() - t0
            logger.info("NAV fetch %s: %.2f seconds (%d records)", scheme_code, fetch_time, len(navs))
            if len(navs) < 2:
                logger.warning("Insufficient NAV data for %s: %d records", scheme_code, len(navs))
                return None
            calc_start = time.time()
            calculator = MetricsCalculator(scheme_code=scheme_code, nav_records=navs)
            metrics = calculator.calculate()
            calc_time = time.time() - calc_start
            logger.info("Metric calculation %s: %.2f seconds", scheme_code, calc_time)
            result = metrics.model_dump()
            result["scheme_code"] = scheme_code
            result["scheme_name"] = scheme_name
            metrics_cache.put(scheme_code, lookback_years, result)
            return result
        except Exception as e:
            logger.warning("Failed to calculate metrics for %s: %s", scheme_code, e)
            return None

    async def get_metrics_batch(
        self,
        funds: list[dict[str, Any]],
        criteria_names: list[str],
        chunk_size: int = 100,
    ) -> list[dict[str, Any] | None]:
        from backend.services.data.tigzig import _get_memory_mb
        from backend.services.mutual_funds.lookback import get_date_range_for_lookback

        mem_before = _get_memory_mb()
        logger.info(f"Memory before metrics batch: {mem_before:.1f} MB")
        lookback_years = get_required_lookback_years(criteria_names)
        start_date, end_date = get_date_range_for_lookback(lookback_years)
        logger.info(
            f"Metrics batch: {len(funds)} funds, lookback={lookback_years}y, "
            f"date_range={start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        )
        dataset = get_tigzig_dataset()
        cached_results: dict[int, dict[str, Any] | None] = {}
        funds_to_process: list[tuple[int, dict[str, Any]]] = []
        for fund in funds:
            code = int(fund["_representative_scheme_code"])
            cached = metrics_cache.get(str(code), lookback_years)
            if cached is not None:
                cached_results[code] = cached
            else:
                funds_to_process.append((code, fund))
        logger.info(
            f"Metrics batch: {len(funds)} total, {len(cached_results)} cached, "
            f"{len(funds_to_process)} to process"
        )
        all_results: dict[int, dict[str, Any] | None] = dict(cached_results)
        num_chunks = 0
        total_rows_read = 0

        for i in range(0, len(funds_to_process), chunk_size):
            chunk = funds_to_process[i:i + chunk_size]
            num_chunks += 1
            chunk_codes = [code for code, _ in chunk]
            chunk_funds = {code: fund for code, fund in chunk}
            chunk_nav_data: dict[int, list[dict[str, Any]]] = {}
            if dataset.is_available:
                try:
                    chunk_nav_data = dataset.query_nav(
                        chunk_codes,
                        start_date=start_date.strftime("%Y-%m-%d"),
                        end_date=end_date.strftime("%Y-%m-%d"),
                    )
                    rows_for_chunk = sum(len(v) for v in chunk_nav_data.values())
                    total_rows_read += rows_for_chunk
                    logger.info(
                        f"Chunk {num_chunks}: read {rows_for_chunk:,} rows for {len(chunk_codes)} schemes "
                        f"(date_range={start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})"
                    )
                    for code in chunk_codes:
                        rows = chunk_nav_data.get(code, [])
                        if rows:
                            dates = [r["date"] for r in rows]
                            logger.debug(f"  Scheme {code}: {len(rows)} rows, first={min(dates)}, last={max(dates)}")
                        else:
                            logger.warning(f"  Scheme {code}: 0 rows returned by TigZig")
                except TigZigDatasetError as e:
                    logger.warning(f"Chunk {num_chunks} TigZig query failed: {e}")

            fallback_semaphore = asyncio.Semaphore(16)

            async def fetch_fallback_nav(code: int, fund: dict[str, Any], initial_nav_data: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
                fund_name = fund.get("_canonical_fund_name", fund.get("scheme_name", ""))
                nav_data = initial_nav_data
                if len(nav_data) >= 2:
                    return code, nav_data
                fallback_started = time.perf_counter()
                logger.info(
                    "TIMING: metrics fallback START | scheme=%s | fund=%s | bulk_rows=%d",
                    code, fund_name, len(nav_data),
                )
                async with fallback_semaphore:
                    try:
                        tigzig_started = time.perf_counter()
                        tigzig_records = await self.get_nav_history_tigzig(str(code), lookback_years)
                        logger.info(
                            "TIMING: metrics fallback TigZig | scheme=%s | %.3f sec | rows=%d",
                            code, time.perf_counter() - tigzig_started, len(tigzig_records),
                        )
                        if len(tigzig_records) >= 2:
                            nav_data = [{"date": r.date, "nav": r.nav} for r in tigzig_records]
                        else:
                            mfapi_started = time.perf_counter()
                            nav_records = await self._get_nav_history_mfapi(str(code), lookback_years)
                            logger.info(
                                "TIMING: metrics fallback MFAPI | scheme=%s | %.3f sec | rows=%d",
                                code, time.perf_counter() - mfapi_started, len(nav_records),
                            )
                            if len(nav_records) >= 2:
                                nav_data = [{"date": r.date, "nav": r.nav} for r in nav_records]
                    except Exception as e:
                        logger.warning("Metrics fallback failed for %s (%s): %s", fund_name, code, e)
                logger.info(
                    "TIMING: metrics fallback END | scheme=%s | %.3f sec | final_rows=%d",
                    code, time.perf_counter() - fallback_started, len(nav_data),
                )
                return code, nav_data

            fallback_tasks = [
                fetch_fallback_nav(code, fund, chunk_nav_data.get(code, []))
                for code, fund in chunk
                if len(chunk_nav_data.get(code, [])) < 2
            ]
            fallback_results = await asyncio.gather(*fallback_tasks)
            fallback_nav_by_code = dict(fallback_results)

            for code, fund in chunk:
                fund_name = fund.get("_canonical_fund_name", fund.get("scheme_name", ""))
                nav_data = chunk_nav_data.get(code, [])
                if len(nav_data) < 2:
                    nav_data = fallback_nav_by_code.get(code, nav_data)
                if len(nav_data) < 2:
                    logger.warning("Insufficient NAV data for %s (%s)", fund_name, code)
                    all_results[code] = None
                    continue
                try:
                    calc_started = time.perf_counter()
                    nav_records = [NAVRecord(date=d["date"], nav=d["nav"]) for d in nav_data]
                    calculator = MetricsCalculator(scheme_code=str(code), nav_records=nav_records)
                    metrics = calculator.calculate()
                    logger.info(
                        "TIMING: metrics calculation | scheme=%s | %.3f sec | rows=%d",
                        code, time.perf_counter() - calc_started, len(nav_records),
                    )
                    result = metrics.model_dump()
                    result["scheme_code"] = str(code)
                    result["scheme_name"] = fund_name
                    result["amc"] = fund.get("amc")
                    result["nav"] = fund.get("nav")
                    result["nav_date"] = fund.get("nav_date")
                    metrics_cache.put(str(code), lookback_years, result)
                    all_results[code] = result
                except Exception as e:
                    logger.exception(f"Metric calculation failed for {fund_name} ({code})")
                    all_results[code] = None
            del chunk_nav_data
            if num_chunks % 5 == 0:
                logger.info(f"Processed {num_chunks} chunks ({min((num_chunks) * chunk_size, len(funds_to_process))}/{len(funds_to_process)} funds)")

        results: list[dict[str, Any] | None] = []
        for fund in funds:
            code = int(fund["_representative_scheme_code"])
            results.append(all_results.get(code))
        mem_after = _get_memory_mb()
        logger.info(
            f"Batch metrics: {len(funds)} funds in {num_chunks} chunks, "
            f"{sum(1 for r in results if r is not None)} successful, "
            f"{total_rows_read:,} total rows read, memory: {mem_before:.1f} -> {mem_after:.1f} MB (delta: {mem_after - mem_before:.1f} MB)"
        )
        return results

    async def search_schemes(self, query: str, limit: int = 100, offset: int = 0) -> list[SchemeSearchResult]:
        q = (query or "").strip().lower()
        if not q:
            return []
        schemes = await self.get_all_schemes()
        newest_nav_date: datetime | None = None
        for s in schemes:
            if s.nav_date:
                try:
                    d = datetime.strptime(s.nav_date, "%d-%b-%Y")
                    if newest_nav_date is None or d > newest_nav_date:
                        newest_nav_date = d
                except ValueError:
                    continue
        def _is_stale(nav_date: str | None) -> bool:
            if nav_date is None or newest_nav_date is None:
                return False
            try:
                d = datetime.strptime(nav_date, "%d-%b-%Y")
            except ValueError:
                return False
            return (newest_nav_date - d).days > 14
        terms = q.split()
        tigzig_meta: dict[int, dict[str, Any]] | None = None
        try:
            tigzig_meta = await get_tigzig_metadata().get_metadata()
            logger.debug("TigZig metadata loaded for search: %d schemes", len(tigzig_meta))
        except Exception as e:
            logger.warning(f"TigZig metadata fetch failed: {type(e).__name__}: {e}")
        matches: list[SchemeSearchResult] = []
        for s in schemes:
            haystack = " ".join(part for part in (s.scheme_name, s.amc or "", s.category or "", s.scheme_code) if part).lower()
            if all(term in haystack for term in terms):
                first_nav_date = None
                if tigzig_meta is not None:
                    try:
                        code_int = int(s.scheme_code)
                        if code_int in tigzig_meta:
                            first_nav_date = tigzig_meta[code_int].get("first_date")
                    except (ValueError, TypeError):
                        first_nav_date = None
                matches.append(SchemeSearchResult(
                    scheme_code=s.scheme_code,
                    scheme_name=s.scheme_name,
                    amc=s.amc or "",
                    category=s.category or "",
                    sub_category=s.sub_category,
                    nav_date=s.nav_date,
                    is_stale=_is_stale(s.nav_date),
                    first_nav_date=first_nav_date,
                    is_active=not _is_stale(s.nav_date),
                ))
        matches.sort(key=lambda r: (r.is_stale, (r.scheme_name or "").lower()))
        return matches[max(0, offset):max(0, offset) + max(0, limit)]

    async def get_all_schemes(self) -> list[MutualFund]:
        started = time.perf_counter()
        cached, expires = self._schemes_cache.get("all", (None, 0))
        if cached and time.time() < expires:
            logger.info("TIMING: get_all_schemes CACHE HIT | %.3f sec", time.perf_counter() - started)
            return cached
        logger.info("TIMING: get_all_schemes CACHE MISS")
        schemes_started = time.perf_counter()
        schemes = await self._get_all_schemes_from_amfi()
        schemes_elapsed = time.perf_counter() - schemes_started
        self._schemes_cache["all"] = (schemes, time.time() + self.cache_ttl)
        logger.info(
            "TIMING: get_all_schemes END | total=%.3f sec | load_parse=%.3f sec | schemes=%d",
            time.perf_counter() - started, schemes_elapsed, len(schemes),
        )
        return schemes

    async def _get_all_schemes_from_amfi(self) -> list[MutualFund]:
        total_started = time.perf_counter()
        text = await self.amfi.fetch_nav_all()
        fetch_elapsed = time.perf_counter() - total_started
        parse_started = time.perf_counter()
        schemes: list[MutualFund] = []
        current_category: str | None = None
        current_amc: str | None = None
        seen: set[str] = set()
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("Open Ended Schemes(") or stripped.startswith("Close Ended Schemes("):
                current_category = stripped.split("(")[1].rstrip(")") if "(" in stripped else stripped
                current_amc = None
                continue
            if stripped.startswith("Close Ended Schemes("):
                current_category = stripped
                continue
            if ";" not in stripped:
                if current_category and not stripped.startswith("Scheme Code"):
                    current_amc = stripped
                continue
            if stripped.startswith("Scheme Code"):
                continue
            parts = stripped.split(";")
            if len(parts) < 7:
                continue
            scheme_code = parts[0].strip()
            scheme_name = parts[3].strip()
            if not scheme_code or not scheme_name or scheme_code in seen:
                continue
            seen.add(scheme_code)
            try:
                nav = float(parts[6].strip())
            except (ValueError, IndexError):
                nav = None
            nav_date = parts[7].strip() if len(parts) > 7 else None
            schemes.append(MutualFund(
                scheme_code=scheme_code,
                scheme_name=scheme_name,
                amc=current_amc,
                category=current_category,
                nav=nav,
                nav_date=nav_date,
            ))
        parse_elapsed = time.perf_counter() - parse_started
        logger.info(
            "TIMING: _get_all_schemes_from_amfi END | total=%.3f sec | fetch=%.3f sec | parse=%.3f sec | bytes=%d | schemes=%d",
            time.perf_counter() - total_started, fetch_elapsed, parse_elapsed, len(text), len(schemes),
        )
        return schemes

    async def get_schemes_by_category(self, category: str) -> list[MutualFund]:
        schemes = await self.get_all_schemes()
        category_lower = category.lower()
        result = []
        for s in schemes:
            canonical = normalize_category(s.category)
            if canonical.lower() == category_lower:
                result.append(s)
        return result

    async def get_latest_nav(self, scheme_code: str) -> MutualFund:
        return await self.get_scheme(scheme_code)

    async def get_nav_history_tigzig(self, scheme_code: str, lookback_years: int | None = None) -> list[NAVRecord]:
        dataset = get_tigzig_dataset()
        start_date = None
        if lookback_years:
            end_date = datetime.now()
            start_date = (end_date - timedelta(days=int(lookback_years * 365.25))).strftime("%Y-%m-%d")
        try:
            nav_data = dataset.query_single_scheme(int(scheme_code), start_date=start_date)
            logger.info(f"TigZig single scheme {scheme_code}: {len(nav_data)} rows (start_date={start_date})")
            if nav_data:
                dates = [d["date"] for d in nav_data]
                logger.info(f"  first={min(dates)}, last={max(dates)}")
            return [NAVRecord(date=d["date"], nav=d["nav"]) for d in nav_data]
        except TigZigDatasetError as e:
            logger.warning(f"TigZig data unavailable for {scheme_code}: {e}")
            return []

    async def _get_nav_history_mfapi(self, scheme_code: str, lookback_years: int | None = None) -> list[NAVRecord]:
        start_date = None
        end_date = None
        if lookback_years:
            start_date, end_date = get_date_range_for_lookback(lookback_years)
        try:
            raw = await self.mfapi.fetch_nav_history(scheme_code, start_date=start_date, end_date=end_date)
        except MfapiError as e:
            raise MfapiError(f"MFAPI fallback failed for scheme {scheme_code}: {e}") from e
        records = normalize_nav_history(raw)
        logger.info("NAV history for %s: %d records via MFAPI (fallback)", scheme_code, len(records))
        return records

    async def get_underlying_funds(self) -> list[dict[str, Any]]:
        if self._underlying_funds_cache:
            funds, expires = self._underlying_funds_cache
            if time.time() < expires:
                return funds
        schemes = await self.get_all_schemes()
        grouper = FundGrouper()
        for scheme in schemes:
            grouper.add_scheme({
                "scheme_code": scheme.scheme_code,
                "scheme_name": scheme.scheme_name,
                "amc": scheme.amc,
                "category": scheme.category,
                "nav": scheme.nav,
                "nav_date": scheme.nav_date,
            })
        candidates = grouper.get_ranking_candidates()
        for candidate in candidates:
            raw_category = candidate.get("_canonical_category")
            candidate["_canonical_category"] = normalize_category(raw_category)
        self._underlying_funds_cache = (candidates, time.time() + self.cache_ttl)
        return candidates

    async def get_ranking_candidates_by_category(self, category: str) -> list[dict[str, Any]]:
        all_funds = await self.get_underlying_funds()
        category_lower = category.lower()
        return [f for f in all_funds if (f.get("_canonical_category") or "").lower() == category_lower]

    def get_fund_grouper(self) -> FundGrouper:
        return FundGrouper()

    async def get_scheme_variants(self, scheme_code: str) -> list[str]:
        underlying = await self.get_underlying_funds()
        target = str(scheme_code)
        for fund in underlying:
            if str(fund.get("scheme_code")) == target:
                return [str(c) for c in fund.get("_all_scheme_codes", [target])]
        return [target]
