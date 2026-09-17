"""Bond service — the central orchestration layer for the Bond domain.

Responsibilities:
  - Retrieve data from providers (CCIL market observations, NSE Debt
    Instruments master, RBI) and cache results.
  - Normalize provider raw records into the internal Bond model.
  - Enrich CCIL Bonds with NSE master data (ISIN + reference fields)
    via the domain-layer matcher (backend.services.bonds.bond_enrichment).
  - Serve analytics via the analytics engine.
  - Keep source-specific parsing out of the service layer.

The service uses in-process caching consistent with the existing project
pattern (see backend.services.mutual_funds.cache). No Redis or external
cache infrastructure is introduced.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import date, datetime
from threading import Lock
from typing import Any, Optional, Union
from zoneinfo import ZoneInfo

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
from backend.services.bonds.bond_enrichment import enrich_ccil_bonds
from backend.services.bonds.bond_normalizer import (
    normalize_ccil_record,
    normalize_cdsl_corporate_primary_record,
    normalize_cdsl_corporate_secondary_record,
    normalize_rbi_record,
    parse_date as _parse_source_date,
)
from backend.services.data.bonds.ccil import CcilClient
from backend.services.data.bonds.corporate_cdsl import CdsCorporateBondClient
from backend.services.data.bonds.corporate_cdsl import fetch_detail_live
from backend.services.data.bonds.nse import NseClient
from backend.services.data.bonds.rbi import RbiClient
from backend.utils.logging import logger

# Timezone used to resolve "today" for date-defaulted corporate report
# requests (CDSL publishes reports on the Indian calendar).
_IST = ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------------------------
# In-process cache (consistent with existing project pattern)
# ---------------------------------------------------------------------------

class BondCache:
    """Simple in-process cache for bond observations and analytics.

    Keys:
      - "list"        : list of all normalized bonds (from all sources)
      - "isin:<isin>" : normalized Bond for a specific ISIN
      - "analytics:<isin>" : AnalyticsResult for a specific ISIN
      - "corporate:<date>" : consolidated corporate bonds (CDSL only)
      - "corporate-isin:<date>:<isin>" : corporate Bond for one ISIN
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
        self._cdsl: CdsCorporateBondClient | None = None

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

    def _get_cdsl(self) -> CdsCorporateBondClient:
        if self._cdsl is None:
            from backend.config.settings import Settings
            settings = Settings()
            self._cdsl = CdsCorporateBondClient(settings)
        return self._cdsl

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

        # CCIL (primary market observations)
        ccil_records: list[CcilRawRecord] = []
        try:
            ccil_records = await self._get_ccil().fetch_all()
        except Exception as exc:
            logger.warning("CCIL refresh failed: %s", exc)

        ccil_bonds: list[Bond] = []
        for raw in ccil_records:
            try:
                bond = normalize_ccil_record(raw)
                ccil_bonds.append(bond)
            except Exception as exc:
                logger.warning("CCIL normalization failed for %s: %s", raw.security_description, exc)

        # NSE Debt Instruments master (ISIN + reference-field enrichment).
        # NSE failure must not destroy the working CCIL path: enrichment
        # is best-effort and CCIL bonds survive with isin=None.
        nse_records: list[NseRawRecord] = []
        try:
            nse_records = await self._get_nse().fetch_all()
        except Exception as exc:
            logger.warning("NSE refresh failed: %s", exc)

        if nse_records:
            try:
                ccil_bonds = enrich_ccil_bonds(ccil_bonds, nse_records)
            except Exception as exc:
                logger.warning("NSE enrichment failed: %s", exc)

        bonds: list[Bond] = list(ccil_bonds)

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
        sort_by: Optional[str] = None,
        sort_dir: str = "asc",
    ) -> list[Bond]:
        """List normalized bonds, with optional filtering and sorting."""
        results = await self._filtered_bonds(instrument_type, issuer, search)
        results = _sort_bonds(results, sort_by, sort_dir)
        return results[offset: offset + limit]

    async def list_bonds_page(
        self,
        instrument_type: Optional[InstrumentType] = None,
        issuer: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: Optional[str] = None,
        sort_dir: str = "asc",
    ) -> dict:
        """List normalized bonds as a pagination envelope.

        Returns ``{"items", "total", "limit", "offset"}`` where ``total``
        counts every bond matching the filter/search BEFORE the limit and
        offset are applied — i.e. the full available universe for the query.
        """
        results = await self._filtered_bonds(instrument_type, issuer, search)
        total = len(results)
        results = _sort_bonds(results, sort_by, sort_dir)
        return {
            "items": results[offset: offset + limit],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def _filtered_bonds(
        self,
        instrument_type: Optional[InstrumentType] = None,
        issuer: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[Bond]:
        """Shared filter pipeline for both list endpoints."""
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

        return results


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

    # ------------------------------------------------------------------
    # Corporate bond pipeline (CDSL only — separate from government)
    # ------------------------------------------------------------------

    async def refresh_corporate_sources(
        self,
        trade_date: date | datetime | str | None = None,
    ) -> list[Bond]:
        """Retrieve CDSL corporate-bond reports, normalize, and cache.

        This is a completely separate retrieval path from
        ``refresh_all_sources()``: it touches ONLY the CDSL live transport
        (secondary + primary market reports). CCIL, NSE, RBI, and the
        government bond cache are never involved, so corporate data is
        loaded only when a corporate endpoint explicitly requests it.

        ``trade_date`` defaults to the current Indian calendar date.
        """
        resolved = _resolve_corporate_trade_date(trade_date)
        cache_key = f"corporate:{resolved.isoformat()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("Corporate bond list cache hit (%s)", cache_key)
            return cached

        logger.info("Refreshing corporate bond data from CDSL for %s", resolved)

        cdsl = self._get_cdsl()

        # The CDSL client is synchronous (browser transport); run the
        # blocking retrievals off the event loop.
        secondary_raw: list = []
        try:
            secondary_raw = await asyncio.to_thread(
                cdsl.fetch_secondary_live, resolved
            )
        except Exception as exc:
            logger.warning("CDSL secondary live retrieval failed: %s", exc)

        primary_raw: list = []
        try:
            primary_raw = await asyncio.to_thread(
                cdsl.fetch_primary_live, resolved
            )
        except Exception as exc:
            logger.warning("CDSL primary live retrieval failed: %s", exc)

        secondary_bonds: list[Bond] = []
        for raw in secondary_raw:
            try:
                bond = normalize_cdsl_corporate_secondary_record(raw)
                if bond is not None:
                    secondary_bonds.append(bond)
            except Exception as exc:
                logger.warning(
                    "CDSL secondary normalization failed for %s: %s",
                    raw.isin, exc,
                )

        primary_bonds: list[Bond] = []
        for raw in primary_raw:
            try:
                bond = normalize_cdsl_corporate_primary_record(raw)
                if bond is not None:
                    primary_bonds.append(bond)
            except Exception as exc:
                logger.warning(
                    "CDSL primary normalization failed for %s: %s",
                    raw.isin, exc,
                )

        # One normalized corporate Bond per ISIN: secondary rows become the
        # market-observation record, primary rows only fill master fields.
        consolidated = _consolidate_corporate_bonds(
            secondary_bonds, primary_bonds
        )

        # Do not cache a total provider failure for the full TTL: an empty
        # result means CDSL failed (or returned nothing), so the next
        # request should retry rather than serve emptiness for an hour.
        if not consolidated:
            logger.warning(
                "Corporate bond refresh produced no records "
                "(secondary=%d, primary=%d); not caching so a subsequent "
                "request can retry",
                len(secondary_bonds), len(primary_bonds),
            )
            return consolidated

        self._cache.put(cache_key, consolidated)
        logger.info(
            "Corporate bond list refreshed: %d bonds for %s "
            "(from %d secondary, %d primary raw rows)",
            len(consolidated), resolved,
            len(secondary_bonds), len(primary_bonds),
        )
        return consolidated

    async def list_corporate_bonds(
        self,
        issuer: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str | None = None,
        sort_dir: str = "asc",
        trade_date: date | datetime | str | None = None,
    ) -> list[Bond]:
        """List normalized corporate bonds, with optional filtering/sorting.

        Uses ONLY the corporate (CDSL) pipeline — never
        ``_filtered_bonds()``/``refresh_all_sources()``.
        """
        results = await self.refresh_corporate_sources(trade_date)
        results = _filter_corporate_bonds(results, issuer, search)
        results = _sort_bonds(results, sort_by, sort_dir)
        return results[offset: offset + limit]

    async def list_corporate_bonds_page(
        self,
        issuer: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str | None = None,
        sort_dir: str = "asc",
        trade_date: date | datetime | str | None = None,
    ) -> dict:
        """List corporate bonds as a pagination envelope.

        Same envelope shape as ``list_bonds_page()``: ``total`` counts every
        corporate bond matching the filter/search BEFORE limit/offset.
        """
        results = await self.refresh_corporate_sources(trade_date)
        results = _filter_corporate_bonds(results, issuer, search)
        total = len(results)
        results = _sort_bonds(results, sort_by, sort_dir)
        return {
            "items": results[offset: offset + limit],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_corporate_bond_by_isin(
        self,
        isin: str,
        trade_date: date | datetime | str | None = None,
    ) -> Optional[Bond]:
        """Retrieve a single corporate bond by ISIN (CDSL data only).

        Searches ONLY the corporate cached/live dataset; the government
        pipeline (``refresh_all_sources()``) is never invoked.
        """
        resolved = _resolve_corporate_trade_date(trade_date)
        cache_key = (
            f"corporate-isin:{resolved.isoformat()}:{isin.strip().upper()}"
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        all_corporate = await self.refresh_corporate_sources(resolved)
        for bond in all_corporate:
            if bond.isin and bond.isin.upper() == isin.strip().upper():
                self._cache.put(cache_key, bond)
                # Enrich with CDSL rich ISIN detail (on demand, cached separately).
                try:
                    rich = await self._get_corporate_rich_detail(bond.isin.upper())
                    if rich is not None:
                        bond = self._merge_rich_detail_into_bond(bond, rich)
                except Exception as exc:
                    logger.debug(
                        "CDSL rich detail enrichment skipped for %s: %s",
                        bond.isin,
                        exc,
                    )
                self._cache.put(cache_key, bond)
                return bond

        return None

    async def _get_corporate_rich_detail(
        self,
        isin_norm: str,
    ) -> Optional[Any]:
        """Fetch CDSL rich ISIN detail for *isin_norm*, cached separately.

        The rich detail is fetched on demand ONLY here (not during list
        refresh, pagination, or search). It is cached under
        ``corporate-detail:<ISIN>`` so repeated selection of the same ISIN
        does not hit CDSL again.
        """
        detail_cache_key = f"corporate-detail:{isin_norm}"
        cached = self._cache.get(detail_cache_key)
        if cached is not None:
            return cached

        try:
            rich = await asyncio.to_thread(fetch_detail_live, isin_norm)
            self._cache.put(detail_cache_key, rich)
            return rich
        except Exception as exc:
            logger.warning(
                "CDSL rich detail retrieval failed for %s: %s", isin_norm, exc
            )
            return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Fields a primary (issuance) record may contribute to the consolidated
# corporate Bond when the secondary market-observation row leaves them
# missing. Secondary values are NEVER overwritten (not even with None).
_CORPORATE_PRIMARY_ENRICH_FIELDS = (
    "issue_date",
    "issue_size",
    "issue_price",
    "mode_of_issuance",
    "issue_type",
    "issuer",
    "security_name",
    "maturity_date",
    "coupon_rate",
)


def _resolve_corporate_trade_date(
    trade_date: date | datetime | str | None,
) -> date:
    """Resolve the corporate report trade date to a calendar date.

    ``None`` defaults to the current Indian calendar date (Asia/Kolkata)
    rather than the naive server/UTC date. Strings are parsed with the
    shared source-date formats (``%d-%b-%Y``, ``%Y-%m-%d``, ...).
    Raises ``ValueError`` for unrecognised input.
    """
    if trade_date is None:
        return datetime.now(_IST).date()
    if isinstance(trade_date, datetime):
        return trade_date.date()
    if isinstance(trade_date, date):
        return trade_date
    parsed = _parse_source_date(str(trade_date))
    if parsed is None:
        raise ValueError(f"Unrecognised corporate trade date: {trade_date!r}")
    return parsed


def _pick_representative_secondary(secondary: list[Bond]) -> Optional[Bond]:
    """Select one representative secondary market observation.

    CDSL can publish multiple secondary rows for the same ISIN (different
    exchanges, multiple trades). Preference order:

        1. Most recent ``trade_date`` (missing ranks lowest)
        2. Greater ``trade_count``
        3. Greater ``traded_value``

    This only selects one representative observation — values are never
    aggregated or reinterpreted. The first row encountered wins remaining
    ties, keeping the result deterministic.
    """
    if not secondary:
        return None

    def _rank(bond: Bond):
        trade_day = bond.trade_date or date(1900, 1, 1)
        trade_count = bond.trade_count if bond.trade_count is not None else -1
        traded_value = (
            bond.traded_value if bond.traded_value is not None else float("-inf")
        )
        return (trade_day, trade_count, traded_value)

    return max((bond for bond in secondary if bond is not None), key=_rank)


def _is_missing_value(value: Any) -> bool:
    """True when a Bond field is absent (None or blank string)."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _consolidate_corporate_bonds(
    secondary_bonds: list[Bond],
    primary_bonds: list[Bond],
) -> list[Bond]:
    """Return ONE normalized corporate Bond per ISIN.

    CDSL publishes primary issuance rows and multiple secondary-market rows
    (e.g. per exchange) for the same ISIN. The secondary-market record is
    the market-observation record: one representative row is chosen per
    ISIN and its market fields (exchange, listing status, LTP, VWAP,
    weighted-average yield, trade count/value/date, credit rating) are
    preserved untouched. Primary (issuance) information only enriches the
    same ISIN where the secondary row leaves a master field missing:
    issue_date, issue_size, issue_price, mode_of_issuance, issue_type,
    issuer, security_name, maturity_date, coupon_rate. No valid value is
    ever overwritten, and no value is fabricated. ISINs present only in
    the primary report remain as reference (issuance) records.
    """
    by_isin_secondary: dict[str, list[Bond]] = {}
    for bond in secondary_bonds:
        if bond is None:
            continue
        key = (bond.isin or "").strip().upper()
        if not key:
            continue
        by_isin_secondary.setdefault(key, []).append(bond)

    by_isin_primary: dict[str, Bond] = {}
    for bond in primary_bonds:
        if bond is None:
            continue
        key = (bond.isin or "").strip().upper()
        if not key or key in by_isin_primary:
            continue
        by_isin_primary[key] = bond

    consolidated: list[Bond] = []
    for isin, rows in by_isin_secondary.items():
        representative = _pick_representative_secondary(rows)
        if representative is None:
            continue
        primary = by_isin_primary.get(isin)
        if primary is None:
            consolidated.append(representative)
            continue

        updates = {
            field: getattr(primary, field)
            for field in _CORPORATE_PRIMARY_ENRICH_FIELDS
            if _is_missing_value(getattr(representative, field))
            and getattr(primary, field) is not None
        }
        if updates:
            representative = representative.model_copy(update=updates)
        consolidated.append(representative)

    # Primary-only ISINs remain reference (issuance) records.
    for isin, primary in by_isin_primary.items():
        if isin not in by_isin_secondary:
            consolidated.append(primary)

    return consolidated


def _filter_corporate_bonds(
    bonds: list[Bond],
    issuer: Optional[str] = None,
    search: Optional[str] = None,
) -> list[Bond]:
    """Filter corporate bonds by issuer substring and free-text search.

    Search covers security_name, isin, issuer, and credit_rating.
    """
    results: list[Bond] = []
    for bond in bonds:
        if issuer:
            if not bond.issuer or issuer.lower() not in bond.issuer.lower():
                continue
        if search:
            haystack = " ".join(
                str(x)
                for x in [
                    bond.security_name,
                    bond.isin,
                    bond.issuer,
                    bond.credit_rating,
                ]
                if x
            ).lower()
            if search.lower() not in haystack:
                continue
        results.append(bond)
    return results


# Sort fields supported by GET /api/bonds (additive, opt-in via sort_by).
BOND_SORT_FIELDS = frozenset({
    "maturity_date",
    "market_ytm",
    "clean_price",
    "coupon_rate",
    "security_name",
    "instrument_type",
})


def _sort_value(bond: Bond, sort_by: str):
    """Extract a comparable sort value, or None when the field is absent.

    Only backend-normalized values are used — no derived/computed values.
    """
    if sort_by == "maturity_date":
        return bond.maturity_date
    if sort_by == "market_ytm":
        return bond.ytm
    if sort_by == "clean_price":
        # Clean price is the canonical quote; fall back to the raw
        # source-reported price only when clean is not published.
        return bond.clean_price if bond.clean_price is not None else bond.price
    if sort_by == "coupon_rate":
        return bond.coupon_rate
    if sort_by == "security_name":
        name = (bond.security_name or "").strip()
        return name.casefold() if name else None
    if sort_by == "instrument_type":
        return bond.instrument_type.value.casefold() if bond.instrument_type else None
    return None


def _sort_bonds(bonds: list[Bond], sort_by: Optional[str], sort_dir: str = "asc") -> list[Bond]:
    """Sort bonds by a supported field.

    Bonds whose sort field is missing are always placed last, regardless of
    direction. Invalid/unspecified sort fields return the input unchanged
    (provider priority order), preserving existing behavior. Ties are broken
    deterministically by security name.
    """
    if not sort_by or sort_by not in BOND_SORT_FIELDS:
        return bonds

    reverse = (sort_dir or "asc").lower() == "desc"

    present: list[tuple] = []
    absent: list[Bond] = []
    for bond in bonds:
        value = _sort_value(bond, sort_by)
        if value is None:
            absent.append(bond)
        else:
            present.append((value, (bond.security_name or "").casefold(), bond))

    present.sort(key=lambda triple: (triple[0], triple[1]), reverse=reverse)

    return [bond for _, _, bond in present] + absent


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


def _merge_rich_detail_into_bond(
    bond: Bond,
    rich: Any,
) -> Bond:
    """Merge CDSL rich ISIN detail into an existing consolidated corporate Bond."""
    if getattr(rich, "issuer_name", None) and not bond.issuer:
        bond.issuer = rich.issuer_name
    if getattr(rich, "security_description", None) and not bond.security_name:
        bond.security_name = rich.security_description
    if getattr(rich, "issuer_address", None):
        bond.issuer_address = rich.issuer_address
    if getattr(rich, "cin", None):
        bond.cin = rich.cin
    if getattr(rich, "lei", None):
        bond.lei = rich.lei
    if getattr(rich, "type_of_issuer", None) and not bond.issuer_type:
        bond.issuer_type = rich.type_of_issuer
    if getattr(rich, "nature_of_issuer", None) and not bond.issuer_sector:
        bond.issuer_sector = rich.nature_of_issuer
    if getattr(rich, "business_sector", None) and not bond.issuer_sector:
        bond.issuer_sector = rich.business_sector
    if getattr(rich, "instrument_type", None):
        if not bond.instrument_type or str(bond.instrument_type) == "UNKNOWN":
            bond.instrument_type = rich.instrument_type
    return bond


def _num(value: Any) -> Optional[float]:
    """Parse a numeric string or numeric value; return ``None`` for blanks."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s or s in ("-", "N/A", "NA", "n/a", "NaN", "nan", ""):
        return None
    try:
        return float(s.replace(",", ""))
    except (TypeError, ValueError):
        return None



def _parse_cdsl_or_none(raw: Any) -> Optional[date]:
    """Parse a CDSL date string (DD-Mon-YYYY or DD/MM/YYYY) into a date."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s in ("-", "N/A", "NA", "n/a", ""):
        return None
    from datetime import datetime as _dt

    for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return _dt.strptime(s, fmt).date()
        except ValueError:
            continue
    return None




def _clean_cdsl_text(raw: Any) -> Optional[str]:
    """Normalize a CDSL text value: None for blanks/dashes.

    Strips null bytes and unicode replacement characters (observed in source
    cells such as CRA names).
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip()
    else:
        s = str(raw).strip()
    if not s or s in ("-", "N/A", "NA", "n/a", ""):
        return None
    s = s.replace(chr(0), "").replace(chr(0xFFFD), "").strip()
    if not s or s in ("-", "N/A", "NA", "n/a", ""):
        return None
    return s



def _parse_coupon_frequency(raw: Any) -> Optional[int]:
    """Parse a CDSL frequency string like 'Once a Year' into an int."""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if not s:
        return None
    if "once" in s and "year" in s:
        return 1
    if "twice" in s and "year" in s:
        return 2
    if "quarter" in s:
        return 4
    if "monthly" in s:
        return 12
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def _parse_day_count_convention(raw: Any) -> DayCountConvention:
    """Map a CDSL day-count string to a DayCountConvention enum."""
    if raw is None:
        return DayCountConvention.UNKNOWN
    s = str(raw).strip().upper()
    mapping = {
        "ACTUAL/ACTUAL": DayCountConvention.ACT_ACT,
        "ACT/ACT": DayCountConvention.ACT_ACT,
        "ACTUAL/365": DayCountConvention.ACT_365,
        "ACT/365": DayCountConvention.ACT_365,
        "ACTUAL/360": DayCountConvention.ACT_360,
        "ACT/360": DayCountConvention.ACT_360,
        "30/360": DayCountConvention.THIRTY_360,
    }
    return mapping.get(s, DayCountConvention.UNKNOWN)
