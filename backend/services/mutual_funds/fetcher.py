import time
from typing import Any

from backend.config.settings import Settings
from backend.models.mutual_fund import MutualFund, NAVRecord, SchemeSearchResult
from backend.services.data.amfi import AmfiClient
from backend.services.data.mfapi import MfapiClient
from backend.services.mutual_funds.normalizer import (
    normalize_nav_history,
    normalize_scheme,
    normalize_search_result,
)
from backend.utils.logging import logger


class MutualFundFetcher:
    def __init__(self, settings: Settings):
        self.mfapi = MfapiClient(settings=settings)
        self.amfi = AmfiClient(settings=settings)
        self.cache_ttl = settings.cache_ttl_seconds
        self._schemes_cache: dict[str, tuple[list[MutualFund], float]] = {}
        self._scheme_cache: dict[str, tuple[MutualFund, float]] = {}
        self._nav_cache: dict[str, tuple[list[NAVRecord], float]] = {}

    async def get_scheme(self, scheme_code: str) -> MutualFund:
        cached, expires = self._scheme_cache.get(scheme_code, (None, 0))
        if cached and time.time() < expires:
            logger.info("Returning cached scheme: %s", scheme_code)
            return cached

        raw = await self.mfapi.fetch_scheme(scheme_code)
        scheme = normalize_scheme(raw)
        self._scheme_cache[scheme_code] = (scheme, time.time() + self.cache_ttl)
        return scheme

    async def get_nav_history(self, scheme_code: str) -> list[NAVRecord]:
        cached, expires = self._nav_cache.get(scheme_code, (None, 0))
        if cached and time.time() < expires:
            logger.info("Returning cached NAV history: %s", scheme_code)
            return cached

        raw = await self.mfapi.fetch_nav_history(scheme_code)
        records = normalize_nav_history(raw)
        self._nav_cache[scheme_code] = (records, time.time() + self.cache_ttl)
        return records

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
        return [
            s for s in schemes
            if (s.category or "").lower() == category_lower
            or (s.sub_category or "").lower() == category_lower
        ]

    async def get_latest_nav(self, scheme_code: str) -> MutualFund:
        return await self.get_scheme(scheme_code)
