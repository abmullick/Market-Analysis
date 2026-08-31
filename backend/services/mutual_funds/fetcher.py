import time
from datetime import datetime, timedelta
from typing import Any

from backend.config.settings import Settings
from backend.models.mutual_fund import MutualFund, NAVRecord, SchemeSearchResult
from backend.services.data.amfi import AmfiClient
from backend.services.data.mfapi import MfapiClient
from backend.services.mutual_funds.cache import metrics_cache
from backend.services.mutual_funds.lookback import (
    get_date_range_for_lookback,
    get_required_lookback_years,
)
from backend.services.mutual_funds.normalizer import (
    normalize_nav_history,
    normalize_scheme,
    normalize_search_result,
)
from backend.utils.logging import logger


from backend.services.data.tigzig import get_tigzig_dataset, TigZigDatasetError
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

        raw = await self.mfapi.fetch_nav_history(scheme_code, start_date=start_date, end_date=end_date)
        records = normalize_nav_history(raw)
        logger.info(
            "NAV history for %s: %d records (lookback=%s years)",
            scheme_code,
            len(records),
            lookback_years or "full",
        )
        return records

    async def get_metrics(
        self,
        scheme_code: str,
        scheme_name: str,
        criteria_names: list[str],
    ) -> dict[str, Any] | None:
        """Get calculated metrics, using cache when available."""
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
    ) -> list[dict[str, Any] | None]:
        """Get metrics for multiple funds using batch TigZig queries.

        Args:
            funds: List of fund dictionaries with '_representative_scheme_code' and '_canonical_fund_name'
            criteria_names: List of criterion names

        Returns:
            List of metric dictionaries (None for failed funds)
        """
        from backend.services.mutual_funds.calculator import MetricsCalculator
        from datetime import datetime, timedelta

        lookback_years = get_required_lookback_years(criteria_names)
        lookback_days = int(lookback_years * 365.25) + 90  # Add buffer
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        # Collect representative scheme codes
        scheme_codes = []
        code_to_fund = {}
        for fund in funds:
            code = int(fund["_representative_scheme_code"])
            scheme_codes.append(code)
            code_to_fund[code] = fund

        # Batch query TigZig
        dataset = get_tigzig_dataset()
        tigzig_results = {}
        fallback_codes = []

        if dataset.is_available:
            try:
                t0 = time.time()
                tigzig_results = dataset.query_nav(scheme_codes, start_date=start_date)
                query_time = time.time() - t0
                logger.info(
                    "Batch TigZig query: %d schemes, %.2f seconds",
                    len(scheme_codes),
                    query_time,
                )
            except TigZigDatasetError as e:
                logger.warning(f"Batch TigZig query failed: {e}")
                fallback_codes = scheme_codes
        else:
            fallback_codes = scheme_codes

        # Identify schemes that need fallback
        for code in scheme_codes:
            if code not in tigzig_results or not tigzig_results[code]:
                fallback_codes.append(code)

        # MFAPI fallback for missing schemes (with rate limiting)
        mfapi_fallback_count = 0
        max_fallback = min(len(fallback_codes), 50)  # Limit fallback requests

        if fallback_codes and mfapi_fallback_count < max_fallback:
            logger.info(f"MFAPI fallback for {len(fallback_codes)} schemes (max {max_fallback})")

            for code in fallback_codes[:max_fallback]:
                try:
                    navs = await self._get_nav_history_mfapi(str(code), lookback_years)
                    if navs:
                        tigzig_results[code] = [
                            {"date": r.date, "nav": r.nav} for r in navs
                        ]
                        mfapi_fallback_count += 1
                except Exception as e:
                    logger.debug(f"MFAPI fallback failed for {code}: {e}")

            if len(fallback_codes) > max_fallback:
                logger.warning(
                    f"Skipped {len(fallback_codes) - max_fallback} fallback requests (limit reached)"
                )

        # Calculate metrics for each fund
        results = []
        for fund in funds:
            code = int(fund["_representative_scheme_code"])
            fund_name = fund.get("_canonical_fund_name", fund.get("scheme_name", ""))

            # Check cache first
            cached = metrics_cache.get(str(code), lookback_years)
            if cached is not None:
                results.append(cached)
                continue

            nav_data = tigzig_results.get(code, [])
            if len(nav_data) < 2:
                logger.warning(f"Insufficient NAV data for {fund_name} ({code})")
                results.append(None)
                continue

            try:
                nav_records = [NAVRecord(date=d["date"], nav=d["nav"]) for d in nav_data]
                calculator = MetricsCalculator(scheme_code=str(code), nav_records=nav_records)
                metrics = calculator.calculate()

                result = metrics.model_dump()
                result["scheme_code"] = str(code)
                result["scheme_name"] = fund_name

                metrics_cache.put(str(code), lookback_years, result)
                results.append(result)
            except Exception as e:
                logger.warning(f"Metric calculation failed for {fund_name} ({code}): {e}")
                results.append(None)

        logger.info(
            f"Batch metrics: {len(funds)} funds, {sum(1 for r in results if r is not None)} successful, "
            f"{mfapi_fallback_count} MFAPI fallbacks"
        )

        return results

    async def search_schemes(self, query: str) -> list[SchemeSearchResult]:
        raw_list = await self.mfapi.search_schemes(query)
        return [normalize_search_result(item) for item in raw_list]

    async def get_all_schemes(self) -> list[MutualFund]:
        cached, expires = self._schemes_cache.get("all", (None, 0))
        if cached and time.time() < expires:
            logger.info("Returning cached schemes list")
            return cached

        try:
            raw = await self.mfapi.fetch_scheme("all")
            if isinstance(raw, list):
                schemes = [normalize_scheme(item) for item in raw]
            else:
                schemes = [normalize_scheme(raw)]
        except Exception as e:
            logger.warning("mfapi fetch_scheme('all') failed: %s — falling back to AMFI", e)
            schemes = await self._get_all_schemes_from_amfi()

        self._schemes_cache["all"] = (schemes, time.time() + self.cache_ttl)
        return schemes

    async def _get_all_schemes_from_amfi(self) -> list[MutualFund]:
        text = await self.amfi.fetch_nav_all()
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

    async def get_nav_history_tigzig(
        self,
        scheme_code: str,
        lookback_years: int | None = None,
    ) -> list[NAVRecord]:
        """Get NAV history from TigZig bulk dataset.

        Args:
            scheme_code: AMFI scheme code
            lookback_years: Optional lookback period in years

        Returns:
            List of NAVRecord objects
        """
        from datetime import datetime, timedelta

        dataset = get_tigzig_dataset()

        start_date = None
        if lookback_years:
            end_date = datetime.now()
            start_date = (end_date - timedelta(days=int(lookback_years * 365.25))).strftime("%Y-%m-%d")

        try:
            nav_data = dataset.query_single_scheme(int(scheme_code), start_date=start_date)
            return [NAVRecord(date=d["date"], nav=d["nav"]) for d in nav_data]
        except TigZigDatasetError as e:
            logger.warning(f"TigZig data unavailable for {scheme_code}: {e}")
            return []

    async def get_nav_history(
        self,
        scheme_code: str,
        lookback_years: int | None = None,
    ) -> list[NAVRecord]:
        """Get NAV history, using TigZig as primary source with MFAPI fallback.

        Args:
            scheme_code: AMFI scheme code
            lookback_years: Optional lookback period in years

        Returns:
            List of NAVRecord objects
        """
        # Try TigZig first
        dataset = get_tigzig_dataset()
        if dataset.is_available:
            result = await self.get_nav_history_tigzig(scheme_code, lookback_years)
            if result:
                return result
            logger.info(f"TigZig returned no data for {scheme_code}, falling back to MFAPI")

        # Fallback to MFAPI
        return await self._get_nav_history_mfapi(scheme_code, lookback_years)

    async def _get_nav_history_mfapi(
        self,
        scheme_code: str,
        lookback_years: int | None = None,
    ) -> list[NAVRecord]:
        """Get NAV history from MFAPI (fallback).

        Args:
            scheme_code: AMFI scheme code
            lookback_years: Optional lookback period in years

        Returns:
            List of NAVRecord objects
        """
        start_date = None
        end_date = None
        if lookback_years:
            start_date, end_date = get_date_range_for_lookback(lookback_years)

        raw = await self.mfapi.fetch_nav_history(scheme_code, start_date=start_date, end_date=end_date)
        records = normalize_nav_history(raw)
        logger.info(
            "NAV history for %s: %d records via MFAPI (fallback)",
            scheme_code,
            len(records),
        )
        return records

    async def get_underlying_funds(self) -> list[dict[str, Any]]:
        """Get all underlying funds with representative schemes.

        Returns:
            List of underlying fund dictionaries with traceability fields
        """
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

        # Add canonical category
        for candidate in candidates:
            raw_category = candidate.get("_canonical_category")
            candidate["_canonical_category"] = normalize_category(raw_category)

        self._underlying_funds_cache = (candidates, time.time() + self.cache_ttl)
        return candidates

    async def get_ranking_candidates_by_category(self, category: str) -> list[dict[str, Any]]:
        """Get ranking candidates for a specific category.

        Args:
            category: Canonical category name

        Returns:
            List of ranking candidate dictionaries
        """
        all_funds = await self.get_underlying_funds()
        category_lower = category.lower()

        return [
            f for f in all_funds
            if (f.get("_canonical_category") or "").lower() == category_lower
        ]

    def get_fund_grouper(self) -> FundGrouper:
        """Get a fresh FundGrouper instance.

        Returns:
            New FundGrouper instance
        """
        return FundGrouper()
