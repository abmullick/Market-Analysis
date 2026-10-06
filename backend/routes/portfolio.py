from typing import Any

import asyncio
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config.settings import Settings
from backend.models.portfolio import (
    PortfolioAnalysisRequest,
    PortfolioAnalysisResult,
    PortfolioWhatIfRequest,
    PortfolioWhatIfResult,
    StockOverlapRequest,
)
from backend.services.ai.groq import AIInsightService, InsightResponse
from backend.services.data.amfi_holdings import AmfiHoldingsService
from backend.services.portfolio.stock_overlap import compute_stock_overlap
from backend.services.mutual_funds.fetcher import MutualFundFetcher
from backend.services.portfolio.nav_batch import fetch_complete_nav_histories
from backend.services.portfolio.mf_analysis import (
    PortfolioAnalysisError,
    calculate_portfolio_analysis,
    validate_allocations,
)
from backend.services.portfolio.what_if import (
    compare_portfolio_results,
    validate_scenario_allocations,
)
from backend.services.data.benchmarks import build_benchmark_data
from backend.services.data.tigzig import get_tigzig_dataset
from backend.utils.logging import logger

router = APIRouter()

settings = Settings()
_fetcher: MutualFundFetcher | None = None

# Short-lived in-process cache for the deterministic current portfolio result.
# This specifically lets What-If reuse the result the user just viewed instead
# of recalculating the unchanged current allocation. The NAV cache lives in
# nav_batch.py and is shared by both endpoints in this process.
_portfolio_result_cache: dict[str, tuple[PortfolioAnalysisResult, float]] = {}
_PORTFOLIO_RESULT_CACHE_TTL_SECONDS = 300


class PortfolioInsightsRequest(BaseModel):
    """Bounded context submitted by the Portfolio Builder AI Insights action.

    Contains ONLY the compact, decision-useful portfolio context built
    client-side from the SAME deterministic portfolio-analysis result the UI
    rendered (fund selection/allocation + analysis summary). The AI service
    interprets these deterministic values; no financial calculations are
    performed server-side (mirrors the Mutual Fund AI Insights request model).
    """

    portfolio_input: dict[str, Any]
    portfolio_analysis: dict[str, Any]


def _get_fetcher() -> MutualFundFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = MutualFundFetcher(settings=settings)
    return _fetcher


def _portfolio_cache_key(funds: list[Any]) -> str:
    """Stable key for a portfolio's scheme/allocation combination."""
    pairs = sorted(
        (str(f.scheme_code).strip(), round(float(f.allocation), 8))
        for f in funds
    )
    return "|".join(f"{code}:{allocation:.8f}" for code, allocation in pairs)


def _get_cached_portfolio_result(key: str) -> PortfolioAnalysisResult | None:
    cached = _portfolio_result_cache.get(key)
    if cached is None:
        return None
    result, expires = cached
    if time.time() >= expires:
        _portfolio_result_cache.pop(key, None)
        return None
    # Never hand the cached mutable Pydantic object directly to a caller.
    return result.model_copy(deep=True)


def _put_cached_portfolio_result(key: str, result: PortfolioAnalysisResult) -> None:
    _portfolio_result_cache[key] = (
        result.model_copy(deep=True),
        time.time() + _PORTFOLIO_RESULT_CACHE_TTL_SECONDS,
    )


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
        fund["scheme_name"] = s.scheme_name
        fund["is_stale"] = _is_scheme_stale(s, schemes)


def _is_scheme_stale(s: Any, schemes: list[Any]) -> bool:
    """True if the scheme's last NAV date lags the universe's newest by >14 days."""
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

    NAV retrieval uses one TigZig bulk query for all selected schemes, with
    concurrent per-scheme fallback only when the bulk result is insufficient.
    Successful complete histories are cached briefly so a subsequent What-If
    request does not download the same NAV data again.
    """
    try:
        validate_allocations([f.model_dump() for f in request.funds])

        dataset = get_tigzig_dataset()
        if not dataset.is_available:
            try:
                await dataset.ensure_dataset()
            except Exception as e:
                logger.warning("TigZig dataset initialization failed (%s); using MFAPI fallback", e)

        fetcher = _get_fetcher()
        fund_codes = [fund.scheme_code.strip() for fund in request.funds]
        nav_by_code = await fetch_complete_nav_histories(fetcher, fund_codes)

        funds_with_navs: list[dict[str, Any]] = []
        for fund in request.funds:
            code = fund.scheme_code.strip()
            navs = nav_by_code.get(code, [])
            if len(navs) < 2:
                raise PortfolioAnalysisError(
                    "INSUFFICIENT_NAV_DATA",
                    f"Insufficient NAV history for scheme {code}.",
                )
            funds_with_navs.append(
                {"scheme_code": code, "allocation": fund.allocation, "navs": navs}
            )

        await _enrich_with_scheme_metadata(fetcher, funds_with_navs)

        calc_started = time.perf_counter()
        result = calculate_portfolio_analysis(funds_with_navs)
        logger.info(
            "TIMING: portfolio calculation | funds=%d | %.3f sec",
            len(funds_with_navs),
            time.perf_counter() - calc_started,
        )

        try:
            benchmark_started = time.perf_counter()
            result.benchmark_data = await asyncio.to_thread(
                build_benchmark_data, result.series
            )
            logger.info(
                "TIMING: portfolio benchmark | %.3f sec",
                time.perf_counter() - benchmark_started,
            )
        except Exception as e:
            logger.warning("Portfolio benchmark comparison failed: %s", e)
            result.benchmark_data = None

        _put_cached_portfolio_result(_portfolio_cache_key(request.funds), result)
        return result
    except PortfolioAnalysisError as e:
        logger.info("Portfolio analysis rejected (%s): %s", e.code, e.message)
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})
    except Exception as e:
        logger.warning("Portfolio analysis failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Failed to analyze portfolio: {e}")


@router.post("/mutual-fund-analysis/insights", response_model=InsightResponse)
async def generate_mutual_fund_portfolio_insights(
    payload: PortfolioInsightsRequest,
) -> InsightResponse:
    """Interpret the bounded Portfolio Builder context with the configured AI service."""
    try:
        return await AIInsightService(settings).generate_insights(
            data=payload.model_dump(exclude_unset=True),
            context="portfolio_builder",
            focus=(
                "concise portfolio-specific interpretation: strongest aspects of the portfolio, "
                "important risks and concentration/diversification issues, notable performance/risk "
                "trade-offs, the single most important KPI for this portfolio, and practical points "
                "the investor should review. Do not invent fund characteristics or market facts not "
                "present in the supplied context."
            ),
        )
    except RuntimeError as exc:
        logger.error("AI service unavailable for portfolio insights: %s", exc)
        raise HTTPException(status_code=503, detail="The AI service is temporarily unavailable") from exc
    except Exception as exc:
        logger.error("Portfolio insight generation failed: %s", exc)
        raise HTTPException(status_code=503, detail="The AI service is temporarily unavailable") from exc


@router.post("/stock-overlap")
async def stock_overlap(request: StockOverlapRequest) -> dict[str, Any]:
    """Compute stock overlap across the supplied funds' AMFI holdings."""
    if not request.funds:
        raise HTTPException(status_code=400, detail="funds must not be empty")
    try:
        fetcher = _get_fetcher()
        funds: list[dict[str, Any]] = [
            {"scheme_code": f.scheme_code.strip(),
             "scheme_name": f.scheme_name,
             "allocation": f.allocation}
            for f in request.funds
        ]
        await _enrich_with_scheme_metadata(fetcher, funds)
        holdings = await AmfiHoldingsService().fetch_holdings(funds)
        if not holdings.holdings:
            from backend.services.data.boi_holdings import BoiHoldingsAdapter
            try:
                fallback = await BoiHoldingsAdapter().fetch_holdings(funds)
            except Exception as exc:
                logger.warning("BOI fallback holdings failed: %s", exc)
                fallback = None
            if fallback is not None and fallback.holdings:
                holdings = fallback
        return compute_stock_overlap(funds, holdings.holdings)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Stock overlap failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Failed to compute stock overlap: {e}")


@router.post("/mutual-fund-analysis/what-if", response_model=PortfolioWhatIfResult)
async def analyze_mutual_fund_portfolio_what_if(
    request: PortfolioWhatIfRequest,
) -> PortfolioWhatIfResult:
    """Run a temporary What-If allocation scenario for the current funds.

    Reuses the current portfolio result when the user has just analyzed the
    same allocation. NAV histories are also reused from the shared short-lived
    batch cache. Only the scenario calculation is then required, followed by
    the existing benchmark comparison for the scenario.
    """
    try:
        validate_allocations([f.model_dump() for f in request.funds])
        fund_codes = [f.scheme_code.strip() for f in request.funds]
        validate_scenario_allocations(
            fund_codes,
            [a.model_dump() for a in request.scenario_allocations],
        )

        fetcher = _get_fetcher()
        current_key = _portfolio_cache_key(request.funds)
        current_result = _get_cached_portfolio_result(current_key)

        if current_result is not None:
            logger.info("TIMING: What-If current result CACHE HIT")
            funds_with_navs = None
        else:
            logger.info("TIMING: What-If current result CACHE MISS")
            dataset = get_tigzig_dataset()
            if not dataset.is_available:
                try:
                    await dataset.ensure_dataset()
                except Exception as e:
                    logger.warning("TigZig dataset initialization failed (%s); using MFAPI fallback", e)

            nav_by_code = await fetch_complete_nav_histories(fetcher, fund_codes)
            funds_with_navs = []
            for fund in request.funds:
                code = fund.scheme_code.strip()
                navs = nav_by_code.get(code, [])
                if len(navs) < 2:
                    raise PortfolioAnalysisError(
                        "INSUFFICIENT_NAV_DATA",
                        f"Insufficient NAV history for scheme {code}.",
                    )
                funds_with_navs.append(
                    {"scheme_code": code, "allocation": fund.allocation, "navs": navs}
                )
            await _enrich_with_scheme_metadata(fetcher, funds_with_navs)
            current_result = calculate_portfolio_analysis(funds_with_navs)
            try:
                current_result.benchmark_data = await asyncio.to_thread(
                    build_benchmark_data, current_result.series
                )
            except Exception as e:
                logger.warning("What-If current benchmark comparison failed: %s", e)
                current_result.benchmark_data = None
            _put_cached_portfolio_result(current_key, current_result)

        if funds_with_navs is None:
            # The current result cache intentionally stores only the calculated
            # result, not the potentially large NAV histories. If NAVs are still
            # in the dedicated NAV cache, this retrieval is a cache hit and does
            # not issue a new TigZig batch query.
            nav_by_code = await fetch_complete_nav_histories(fetcher, fund_codes)
            funds_with_navs = []
            for fund in request.funds:
                code = fund.scheme_code.strip()
                navs = nav_by_code.get(code, [])
                if len(navs) < 2:
                    raise PortfolioAnalysisError(
                        "INSUFFICIENT_NAV_DATA",
                        f"Insufficient NAV history for scheme {code}.",
                    )
                funds_with_navs.append(
                    {"scheme_code": code, "allocation": fund.allocation, "navs": navs}
                )
            await _enrich_with_scheme_metadata(fetcher, funds_with_navs)

        scenario_alloc_by_code = {
            a.scheme_code.strip(): a.allocation for a in request.scenario_allocations
        }
        scenario_funds_with_navs = [
            {**fund, "allocation": scenario_alloc_by_code[fund["scheme_code"]]}
            for fund in funds_with_navs
        ]
        scenario_started = time.perf_counter()
        scenario_result = calculate_portfolio_analysis(scenario_funds_with_navs)
        logger.info(
            "TIMING: What-If scenario calculation | funds=%d | %.3f sec",
            len(scenario_funds_with_navs),
            time.perf_counter() - scenario_started,
        )

        try:
            scenario_result.benchmark_data = await asyncio.to_thread(
                build_benchmark_data, scenario_result.series
            )
        except Exception as e:
            logger.warning("What-If benchmark comparison failed: %s", e)
            scenario_result.benchmark_data = None

        return compare_portfolio_results(current_result, scenario_result)
    except PortfolioAnalysisError as e:
        logger.info("What-If analysis rejected (%s): %s", e.code, e.message)
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})
    except Exception as e:
        logger.warning("What-If analysis failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Failed to analyze what-if scenario: {e}")
