from typing import Any

from fastapi import APIRouter, HTTPException

from backend.config.settings import Settings
from backend.models.portfolio import PortfolioAnalysisRequest, PortfolioAnalysisResult
from backend.services.mutual_funds.fetcher import MutualFundFetcher
from backend.services.portfolio.mf_analysis import (
    PortfolioAnalysisError,
    calculate_portfolio_analysis,
    validate_allocations,
)
from backend.services.data.tigzig import get_tigzig_dataset
from backend.utils.logging import logger

router = APIRouter()

settings = Settings()
_fetcher: MutualFundFetcher | None = None


def _get_fetcher() -> MutualFundFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = MutualFundFetcher(settings=settings)
    return _fetcher


async def _enrich_with_scheme_metadata(
    fetcher: MutualFundFetcher, funds: list[dict[str, Any]]
) -> None:
    """Add AMC/category/is_stale metadata to each fund dict (in place).

    Uses the same cached AMFI universe as fund search — no extra network
    calls. Funds without a matching AMFI entry simply keep None/False defaults.
    """
    try:
        schemes = await fetcher.get_all_schemes()
    except Exception as e:
        logger.warning("Could not load AMFI universe for metadata enrichment: %s", e)
        return

    by_code: dict[str, Any] = {s.scheme_code: s for s in schemes}
    for fund in funds:
        s = by_code.get(fund["scheme_code"])
        if s is None:
            continue
        fund["amc"] = s.amc or None
        fund["category"] = s.category or None
        fund["is_stale"] = _is_scheme_stale(s, schemes)


def _is_scheme_stale(s: Any, schemes: list[Any]) -> bool:
    """True if the scheme's last NAV date lags the universe's newest by >14 days.

    Mirrors the stale/retired convention used by fund search: AMFI-reported
    last-NAV dates, with a 14-day grace window for weekends/holidays.
    """
    from datetime import datetime

    if not s.nav_date:
        return False
    try:
        scheme_date = datetime.strptime(s.nav_date, "%d-%b-%Y")
    except ValueError:
        return False

    newest: datetime | None = None
    for other in schemes:
        if other.nav_date:
            try:
                d = datetime.strptime(other.nav_date, "%d-%b-%Y")
                if newest is None or d > newest:
                    newest = d
            except ValueError:
                continue
    if newest is None:
        return False
    return (newest - scheme_date).days > 14


@router.post("/upload")
async def upload_portfolio():
    raise NotImplementedError("Portfolio upload not yet implemented.")


@router.get("/analysis")
async def get_portfolio_analysis():
    raise NotImplementedError("Portfolio analysis not yet implemented.")


@router.post("/mutual-fund-analysis", response_model=PortfolioAnalysisResult)
async def analyze_mutual_fund_portfolio(request: PortfolioAnalysisRequest) -> PortfolioAnalysisResult:
    """Analyze an allocation-based mutual-fund portfolio.

    Accepts only scheme codes + allocations (the client-side Portfolio
    Builder state). NAV histories are fetched server-side (TigZig batch path
    with MFAPI fallback), each unique scheme fetched at most once per request.
    No portfolio state is persisted.
    """
    try:
        # Validate allocations BEFORE any NAV fetching.
        validate_allocations([f.model_dump() for f in request.funds])

        # Ensure the TigZig bulk dataset (complete NAV history) is available.
        # Without this, the request silently falls back to MFAPI, whose per-scheme
        # history can be stale/partial (e.g. 106253 ends 2017-04-25), truncating
        # the portfolio's common period. ensure_dataset downloads once and is a
        # no-op afterwards; no new cache infrastructure.
        dataset = get_tigzig_dataset()
        if not dataset.is_available:
            try:
                await dataset.ensure_dataset()
            except Exception as e:
                logger.warning("TigZig dataset initialization failed (%s); using MFAPI fallback", e)

        # Fetch each unique fund's COMPLETE NAV history once for this request
        # (lookback_years=None → no date-window clipping; the common period is
        # derived dynamically from the full available histories).
        funds_with_navs: list[dict[str, Any]] = []
        fetcher = _get_fetcher()
        for fund in request.funds:
            code = fund.scheme_code.strip()
            navs = await fetcher.get_nav_history(code, lookback_years=None)
            funds_with_navs.append(
                {"scheme_code": code, "allocation": fund.allocation, "navs": navs}
            )

        # Enrich with AMC/category/stale metadata from the cached AMFI universe
        # (no extra network calls — uses the same cache as fund search) so the
        # Health Score Fund Mix + legacy-confidence components can run.
        await _enrich_with_scheme_metadata(fetcher, funds_with_navs)

        return calculate_portfolio_analysis(funds_with_navs)
    except PortfolioAnalysisError as e:
        logger.info("Portfolio analysis rejected (%s): %s", e.code, e.message)
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})
    except Exception as e:
        logger.warning("Portfolio analysis failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Failed to analyze portfolio: {e}")
