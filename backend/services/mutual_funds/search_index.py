"""Fast in-memory mutual-fund search optimization.

The existing portfolio-builder search is intentionally kept functionally
identical: it still searches the complete AMFI universe and returns the same
SchemeSearchResult fields and ordering.  This module only moves expensive
work out of the per-keystroke search path by caching the normalized search
text, newest NAV date, stale status, and TigZig first-NAV metadata.
"""

import time
from datetime import datetime
from typing import Any

from backend.models.mutual_fund import SchemeSearchResult
from backend.services.data.tigzig import get_tigzig_metadata
from backend.utils.logging import logger


def _parse_amfi_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d-%b-%Y")
    except (TypeError, ValueError):
        return None


def install_search_optimization() -> None:
    """Patch MutualFundFetcher.search_schemes with a cached-index version.

    The patch is installed once from the mutual_funds package __init__.py.
    Keeping it here avoids changing the large fetcher implementation while
    allowing the search path to be optimized independently.
    """
    from backend.services.mutual_funds.fetcher import MutualFundFetcher

    if getattr(MutualFundFetcher, "_fast_search_installed", False):
        return

    async def fast_search_schemes(
        self: Any,
        query: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SchemeSearchResult]:
        q = (query or "").strip().lower()
        if not q:
            return []

        started = time.perf_counter()
        schemes = await self.get_all_schemes()
        schemes_expires = self._schemes_cache.get("all", (None, 0))[1]

        index = getattr(self, "_fast_search_index", None)
        index_expires = getattr(self, "_fast_search_index_expires", 0)

        if index is None or index_expires != schemes_expires:
            build_started = time.perf_counter()

            newest_nav_date: datetime | None = None
            entries: list[tuple[Any, str, bool]] = []
            for scheme in schemes:
                nav_date = _parse_amfi_date(scheme.nav_date)
                if nav_date and (newest_nav_date is None or nav_date > newest_nav_date):
                    newest_nav_date = nav_date

                haystack = " ".join(
                    part
                    for part in (
                        scheme.scheme_name,
                        scheme.amc or "",
                        scheme.category or "",
                        scheme.scheme_code,
                    )
                    if part
                ).lower()
                entries.append((scheme, haystack, False))

            # Stale status is calculated once per AMFI cache lifetime rather
            # than on every keystroke.
            stale_entries: list[tuple[Any, str, bool]] = []
            for scheme, haystack, _ in entries:
                parsed = _parse_amfi_date(scheme.nav_date)
                is_stale = bool(
                    parsed is not None
                    and newest_nav_date is not None
                    and (newest_nav_date - parsed).days > 14
                )
                stale_entries.append((scheme, haystack, is_stale))

            tigzig_meta: dict[int, dict[str, Any]] = {}
            try:
                tigzig_meta = await get_tigzig_metadata().get_metadata()
                logger.debug(
                    "Fast search index: TigZig metadata loaded for %d schemes",
                    len(tigzig_meta),
                )
            except Exception as exc:
                logger.warning(
                    "Fast search index: TigZig metadata unavailable: %s: %s",
                    type(exc).__name__,
                    exc,
                )

            first_dates: dict[str, str | None] = {}
            for scheme, _, _ in stale_entries:
                try:
                    meta = tigzig_meta.get(int(scheme.scheme_code))
                    first_dates[scheme.scheme_code] = meta.get("first_date") if meta else None
                except (TypeError, ValueError):
                    first_dates[scheme.scheme_code] = None

            index = (stale_entries, first_dates)
            self._fast_search_index = index
            self._fast_search_index_expires = schemes_expires
            logger.info(
                "TIMING: fast search index BUILD | schemes=%d | %.3f sec",
                len(schemes),
                time.perf_counter() - build_started,
            )

        entries, first_dates = index
        terms = q.split()
        matches: list[SchemeSearchResult] = []

        # The complete AMFI universe is still searched. The optimization is
        # that all expensive normalization, date parsing and TigZig metadata
        # lookup happened once when the index was built.
        for scheme, haystack, is_stale in entries:
            if not all(term in haystack for term in terms):
                continue
            matches.append(
                SchemeSearchResult(
                    scheme_code=scheme.scheme_code,
                    scheme_name=scheme.scheme_name,
                    amc=scheme.amc or "",
                    category=scheme.category or "",
                    sub_category=scheme.sub_category,
                    nav_date=scheme.nav_date,
                    is_stale=is_stale,
                    first_nav_date=first_dates.get(scheme.scheme_code),
                    is_active=not is_stale,
                )
            )

        matches.sort(key=lambda result: (result.is_stale, (result.scheme_name or "").lower()))
        paged = matches[max(0, offset):max(0, offset) + max(0, limit)]

        logger.info(
            "TIMING: fast search | query=%r | matches=%d | returned=%d | %.3f sec",
            q,
            len(matches),
            len(paged),
            time.perf_counter() - started,
        )
        return paged

    MutualFundFetcher.search_schemes = fast_search_schemes
    MutualFundFetcher._fast_search_installed = True
    logger.info("Mutual-fund fast search optimization installed")
