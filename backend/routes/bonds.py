"""Bond API routes.

Routes:
  GET  /api/bonds                    — list/search government bonds
  GET  /api/bonds/{isin}             — retrieve bond by ISIN
  GET  /api/bonds/{isin}/market      — retrieve market observation
  GET  /api/bonds/{isin}/analytics   — retrieve analytics

GET /api/bonds supports opt-in server-side sorting (sort_by/sort_dir) and an
opt-in pagination envelope (envelope=true → {items, total, limit, offset}).
The default response remains a plain JSON list for backward compatibility.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.models.bonds import (
    AnalyticsResult,
    Bond,
    BondListQuery,
    BondListResponse,
    InstrumentType,
)
from backend.services.bonds.bond_service import BondService


router = APIRouter(tags=["bonds"])

# Module-level service instance (shared across requests)
_bond_service: BondService | None = None


def get_bond_service() -> BondService:
    global _bond_service
    if _bond_service is None:
        _bond_service = BondService()
    return _bond_service


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
async def list_bonds(
    instrument_type: Optional[InstrumentType] = Query(
        None, description="Filter by instrument type (G-Sec, T-Bill, SDL)"
    ),
    issuer: Optional[str] = Query(
        None, description="Filter by issuer name (substring match)"
    ),
    search: Optional[str] = Query(
        None, description="Search across security name, ISIN, issuer"
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    sort_by: Optional[str] = Query(
        None,
        description=(
            "Optional sort field: maturity_date, market_ytm, clean_price, "
            "coupon_rate, security_name, instrument_type"
        ),
    ),
    sort_dir: Optional[str] = Query(
        None, description="Sort direction: asc (default) or desc"
    ),
    envelope: bool = Query(
        False,
        description=(
            "Return a {items, total, limit, offset} envelope. total counts "
            "ALL bonds matching the query (before limit/offset). Default "
            "response remains a plain JSON list (backward compatible)."
        ),
    ),
) -> list[Bond] | BondListResponse:
    """List government bonds (G-Secs, T-Bills, SDLs).

    Supports optional filtering by instrument type, issuer, and free-text
    search, plus opt-in server-side sorting and a paginated response
    envelope. Results are cached in-process.
    """
    service = get_bond_service()
    if envelope:
        return await service.list_bonds_page(
            instrument_type=instrument_type,
            issuer=issuer,
            search=search,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir or "asc",
        )
    return await service.list_bonds(
        instrument_type=instrument_type,
        issuer=issuer,
        search=search,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_dir=sort_dir or "asc",
    )


@router.get("/{isin}")
async def get_bond(
    isin: str,
) -> Bond:
    """Retrieve a single government bond by ISIN.

    Returns the normalized Bond record (master data + latest market
    observation + source metadata).
    """
    service = get_bond_service()
    bond = await service.get_bond_by_isin(isin)
    if bond is None:
        raise HTTPException(status_code=404, detail=f"Bond with ISIN {isin} not found")
    return bond


@router.get("/{isin}/market")
async def get_market_observation(
    isin: str,
) -> Bond:
    """Retrieve the market observation for a bond by ISIN.

    Returns the same normalized Bond record as GET /api/bonds/{isin},
    emphasizing the market-observation fields (price, YTM, bid/offer,
    traded value, data type, freshness).
    """
    service = get_bond_service()
    bond = await service.get_market_observation(isin)
    if bond is None:
        raise HTTPException(status_code=404, detail=f"Bond with ISIN {isin} not found")
    return bond


@router.get("/{isin}/analytics")
async def get_analytics(
    isin: str,
) -> AnalyticsResult:
    """Compute and return analytics for a bond by ISIN.

    Analytics include:
      - current_yield
      - calculated_ytm (independent calculation, separate from market_ytm)
      - market_ytm (source-reported YTM, retained for validation)
      - cash_flows
      - accrued_interest
      - macaulay_duration
      - modified_duration
      - convexity
      - dv01
    """
    service = get_bond_service()
    analytics = await service.get_analytics(isin)
    if analytics is None:
        raise HTTPException(status_code=404, detail=f"Bond with ISIN {isin} not found")
    return analytics
