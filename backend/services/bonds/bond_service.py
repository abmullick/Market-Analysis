"""Bond service — the central orchestration layer for the Bond domain.

Responsibilities:
  - Retrieve data from providers (CCIL, NSE, RBI) and cache results.
  - Normalize provider raw records into the internal Bond model.
  - Serve analytics via the analytics engine.
  - Keep source-specific parsing out of the service layer.

The service uses in-process caching consistent with the existing project
pattern (see backend.services.mutual_funds.cache). No Redis or external
cache infrastructure is introduced.
"""

from __future__ import annotations

import re
import time
from datetime import date, datetime
from threading import Lock
from typing import Any, Optional

from backend.models.bonds import (
    AnalyticsResult,
    Bond,
    BondListQuery,
    CcilRawRecord,
    DataType,
    InstrumentType,
    NseRawRecord,
    RbiRawRecord,
)
from backend.services.bonds.bond_analytics import compute_analytics
from backend.services.bonds.bond_normalizer import (
    normalize_ccil_record,
    normalize_nse_record,
    normalize_rbi_record,
)
from backend.services.data.bonds.ccil import CcilClient
from backend.services.data.bonds.nse import NseClient
from backend.services.data.bonds.rbi import RbiClient
from backend.utils.logging import logger


# ---------------------------------------------------------------------------
# In-process cache (consistent with existing project pattern)
# ---------------------------------------------------------------------------

class BondCache:
    """Simple in-process cache for bond observations and analytics.

    Keys:
      - "list"        : list of all normalized bonds (from all sources)
      - "isin:<isin>" : normalized Bond for a specific ISIN
      - "analytics:<isin>" : AnalyticsResult for a specific ISIN
    """

    def __init__(self, ttl_seconds: int = 3600):
        self._ttl = ttl_seconds
        self._data: dict[str, tuple[Any, float]] = {}
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expires = entry
            if time.time() > expires:
                del self._data[key]
                self._misses += 1
                return None
            self._hits += 1
            return value

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = (value, time.time() + self._ttl)

    def invalidate(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._data.clear()
            elif key in self._data:
                del self._data[key]

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "size": len(self._data),
                "hits": self._hits,
                "misses": self._misses,
            }


# Module-level cache instance (shared across requests)
bond_cache = BondCache(ttl_seconds=3600)


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

class BondService:
    """Central Bond service.

    Usage:
        service = BondService(settings)
        bonds = await service.list_bonds()
        bond = await service.get_bond_by_isin(isin)
        analytics = await service.get_analytics(isin)
    """

    def __init__(self, ttl_seconds: int = 3600):
        self._cache = bond_cache
        self._ttl = ttl_seconds
        self._ccil: CcilClient | None = None
        self._nse: NseClient | None = None
        self._rbi: RbiClient | None = None

    # ------------------------------------------------------------------
    # Provider lazy initialization
    # ------------------------------------------------------------------

    def _get_ccil(self) -> CcilClient:
        if self._ccil is None:
            from backend.config.settings import Settings
            settings = Settings()
            self._ccil = CcilClient(settings)
        return self._ccil

    def _get_nse(self) -> NseClient:
        if self._nse is None:
            from backend.config.settings import Settings
            settings = Settings()
            self._nse = NseClient(settings)
        return self._nse

    def _get_rbi(self) -> RbiClient:
        if self._rbi is None:
            from backend.config.settings import Settings
            settings = Settings()
            self._rbi = RbiClient(settings)
        return self._rbi

    # ------------------------------------------------------------------
    # Retrieval + normalization
    # ------------------------------------------------------------------

    async def refresh_all_sources(self) -> list[Bond]:
        """Retrieve from all providers, normalize, and cache the result.

        Returns the combined list of normalized Bond records.
        """
        cache_key = "list"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("Bond list cache hit")
            return cached

        logger.info("Refreshing bond data from all sources")
        bonds: list[Bond] = []

        # CCIL (primary market observations)
        ccil_records: list[CcilRawRecord] = []
        try:
            ccil_records = await self._get_ccil().fetch_all()
        except Exception as exc:
            logger.warning("CCIL refresh failed: %s", exc)

        for raw in ccil_records:
            try:
                bond = normalize_ccil_record(raw)
                bonds.append(bond)
            except Exception as exc:
                logger.warning("CCIL normalization failed for %s: %s", raw.security_description, exc)

        # NSE (secondary validation / reference)
        nse_records: list[NseRawRecord] = []
        try:
            nse_records = await self._get_nse().fetch_all()
        except Exception as exc:
            logger.warning("NSE refresh failed: %s", exc)

        for raw in nse_records:
            try:
                bond = normalize_nse_record(raw)
                if bond is not None:
                    bonds.append(bond)
            except Exception as exc:
                logger.warning("NSE normalization failed: %s", exc)

        # RBI (reference / validation / history)
        rbi_records: list[RbiRawRecord] = []
        try:
            rbi_records = await self._get_rbi().fetch_all()
        except Exception as exc:
            logger.warning("RBI refresh failed: %s", exc)

        for raw in rbi_records:
            try:
                bond = normalize_rbi_record(raw)
                if bond is not None:
                    bonds.append(bond)
            except Exception as exc:
                logger.warning("RBI normalization failed: %s", exc)

        # De-duplicate by identity (ISIN when published, otherwise the
        # security description — see _deduplicate_bonds).
        deduped = _deduplicate_bonds(bonds)

        # Do not cache a total provider failure for the full TTL: an empty
        # result means every source failed (or returned nothing), so the
        # next request should retry rather than serve emptiness for an hour.
        if not deduped:
            logger.warning(
                "Bond refresh produced no records (CCIL=%d, NSE=%d, RBI=%d); "
                "not caching so a subsequent request can retry",
                len(ccil_records), len(nse_records), len(rbi_records),
            )
            return deduped

        self._cache.put(cache_key, deduped)
        logger.info("Bond list refreshed: %d bonds (from %d raw CCIL, %d NSE, %d RBI)",
                     len(deduped), len(ccil_records), len(nse_records), len(rbi_records))
        return deduped

    async def list_bonds(
        self,
        instrument_type: Optional[InstrumentType] = None,
        issuer: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Bond]:
        """List normalized bonds, with optional filtering."""
        all_bonds = await self.refresh_all_sources()

        results: list[Bond] = []
        for bond in all_bonds:
            if instrument_type is not None and bond.instrument_type != instrument_type:
                continue
            if issuer and bond.issuer:
                if issuer.lower() not in bond.issuer.lower():
                    continue
            if search:
                haystack = " ".join(
                    str(x) for x in [bond.security_name, bond.isin, bond.issuer] if x
                ).lower()
                if search.lower() not in haystack:
                    continue
            results.append(bond)

        return results[offset: offset + limit]

    async def get_bond_by_isin(self, isin: str) -> Optional[Bond]:
        """Retrieve a single normalized bond by ISIN."""
        cache_key = f"isin:{isin}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        all_bonds = await self.refresh_all_sources()
        for bond in all_bonds:
            if bond.isin and bond.isin.upper() == isin.upper():
                self._cache.put(cache_key, bond)
                return bond

        # If not found in combined list, try direct provider lookup
        # (fallback — normally ISINs come from the combined list)
        return None

    async def get_market_observation(self, isin: str) -> Optional[Bond]:
        """Retrieve market observation for a bond by ISIN.

        This is effectively the same as get_bond_by_isin for now, since
        the Bond model carries both master and market data.
        """
        return await self.get_bond_by_isin(isin)

    async def get_analytics(self, isin: str) -> Optional[AnalyticsResult]:
        """Compute analytics for a bond by ISIN."""
        cache_key = f"analytics:{isin}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        bond = await self.get_bond_by_isin(isin)
        if bond is None:
            return None

        analytics = compute_analytics(bond)
        self._cache.put(cache_key, analytics)
        return analytics


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _deduplicate_bonds(bonds: list[Bond]) -> list[Bond]:
    """Deduplicate bonds by identity, preferring primary (traded) observations.

    Identity is the ISIN when the source publishes one. CCIL Market Watch
    does NOT publish an ISIN, so ISIN-less observations are keyed on the
    normalized security description instead of being dropped. The CCIL
    security description is thereby preserved as a stable source
    identifier for a future NSE security-master enrichment step (which
    will supply the real ISIN).

    Priority:
      1. CCIL traded
      2. NSE traded
      3. CCIL indicative
      4. RBI reference
      5. Others
    """
    by_key: dict[str, Bond] = {}
    for bond in bonds:
        key = _bond_identity(bond)
        if key is None:
            continue
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = bond
            continue

        # Prefer higher-priority data types
        if _data_type_priority(bond) > _data_type_priority(existing):
            by_key[key] = bond
        elif _data_type_priority(bond) == _data_type_priority(existing):
            # If same priority, prefer more recent
            b_date = bond.trade_date or bond.as_of or date(1900, 1, 1)
            e_date = existing.trade_date or existing.as_of or date(1900, 1, 1)
            if b_date > e_date:
                by_key[key] = bond

    return list(by_key.values())


def _bond_identity(bond: Bond) -> Optional[str]:
    """Return a stable deduplication key for a bond.

    ``isin:<ISIN>`` when the source publishes an ISIN, otherwise
    ``name:<normalized security description>``. Sources that publish no
    ISIN (CCIL Market Watch) therefore survive deduplication instead of
    being silently discarded.
    """
    if bond.isin:
        return f"isin:{bond.isin.strip().upper()}"
    name = re.sub(r"\s+", " ", (bond.security_name or "").strip()).upper()
    if not name:
        return None
    return f"name:{name}"


def _data_type_priority(bond: Bond) -> int:
    """Return a numeric priority for a bond's data type.

    Higher = preferred.
    """
    dt = bond.data_type
    mapping = {
        DataType.TRADED: 4,
        DataType.INDICATIVE: 3,
        DataType.MTM: 2,
        DataType.REFERENCE: 1,
        DataType.AUCTION: 2,
        DataType.HISTORICAL: 0,
        DataType.UNKNOWN: -1,
    }
    return mapping.get(dt, 0)
