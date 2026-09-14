from typing import Any

import asyncio

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
        # Scheme name is used for user-facing warnings (e.g. zero-allocation
        # exclusions) instead of an unexplained scheme code.
        fund["scheme_name"] = s.scheme_name
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

        result = calculate_portfolio_analysis(funds_with_navs)

        # Additive Portfolio-vs-Benchmark comparison (Phase 2E). Runs off the
        # portfolio growth series; a failure only downgrades the comparison and
        # never breaks the existing portfolio analysis.
        try:
            result.benchmark_data = await asyncio.to_thread(
                build_benchmark_data, result.series
            )
        except Exception as e:
            logger.warning("Portfolio benchmark comparison failed: %s", e)
            result.benchmark_data = None

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
    """Interpret the bounded Portfolio Builder context with the configured AI service.

    The compact deterministic context (fund selection/allocation + portfolio
    analysis summary) is built client-side from the SAME result object the UI
    rendered and is interpreted as a mutual-fund PORTFOLIO via the
    ``portfolio_builder`` context. Nothing is re-computed here — the AI layer
    only interprets the deterministic values supplied in the payload.
    """
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
    """Compute stock overlap across the supplied funds' AMFI holdings.

    Holdings are fetched only for the supplied funds via the existing
    AmfiHoldingsService (default/hardcoded quarter) and passed directly
    to compute_stock_overlap(). No new AMFI scraping logic.
    """
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

    Runs the SAME allocation-based analysis engine twice — once for the
    current allocation (``request.funds``), once for the alternative
    ``scenario_allocations`` — over ONE shared NAV fetch, so both sides use
    identical historical data, date-alignment, and methodology. The scenario
    is purely computational: nothing is persisted and the caller's actual
    portfolio state is never modified.
    """
    try:
        # Validate both sides before any NAV fetching.
        validate_allocations([f.model_dump() for f in request.funds])
        fund_codes = [f.scheme_code.strip() for f in request.funds]
        validate_scenario_allocations(
            fund_codes,
            [a.model_dump() for a in request.scenario_allocations],
        )

        dataset = get_tigzig_dataset()
        if not dataset.is_available:
            try:
                await dataset.ensure_dataset()
            except Exception as e:
                logger.warning("TigZig dataset initialization failed (%s); using MFAPI fallback", e)

        # One NAV fetch per unique fund, reused for BOTH the current and
        # scenario analysis — no second data-retrieval pipeline.
        fetcher = _get_fetcher()
        funds_with_navs: list[dict[str, Any]] = []
        for fund in request.funds:
            code = fund.scheme_code.strip()
            navs = await fetcher.get_nav_history(code, lookback_years=None)
            funds_with_navs.append(
                {"scheme_code": code, "allocation": fund.allocation, "navs": navs}
            )
        await _enrich_with_scheme_metadata(fetcher, funds_with_navs)

        current_result = calculate_portfolio_analysis(funds_with_navs)

        scenario_alloc_by_code = {
            a.scheme_code.strip(): a.allocation for a in request.scenario_allocations
        }
        scenario_funds_with_navs = [
            {**fund, "allocation": scenario_alloc_by_code[fund["scheme_code"]]}
            for fund in funds_with_navs
        ]
        scenario_result = calculate_portfolio_analysis(scenario_funds_with_navs)

        # Same benchmark methodology as the main endpoint, run for both sides;
        # a failure only omits the benchmark comparison, never the metrics.
        for result in (current_result, scenario_result):
            try:
                result.benchmark_data = await asyncio.to_thread(
                    build_benchmark_data, result.series
                )
            except Exception as e:
                logger.warning("What-If benchmark comparison failed: %s", e)
                result.benchmark_data = None

        return compare_portfolio_results(current_result, scenario_result)
    except PortfolioAnalysisError as e:
        logger.info("What-If analysis rejected (%s): %s", e.code, e.message)
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})
    except Exception as e:
        logger.warning("What-If analysis failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Failed to analyze what-if scenario: {e}")
