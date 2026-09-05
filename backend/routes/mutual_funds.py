import asyncio
import os
import json
import copy
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from backend.config.settings import Settings
from backend.models.mutual_fund import (
    CategoryAnalysisResponse,
    CategoryMetricPercentile,
    FundDetailResponse,
    FundMetrics,
    MutualFund,
    NAVHistoryResponse,
    NAVRecord,
    RankingRequest,
    RollingReturnResponse,
    SchemeSearchResult,
)
from backend.services.mutual_funds.fetcher import MutualFundFetcher
from backend.services.mutual_funds.lookback import get_required_lookback_years
from backend.services.mutual_funds.ranking import RankingEngine
from backend.services.mutual_funds.category_normalizer import normalize_category
from backend.services.mutual_funds.cache import metrics_cache
from backend.services.mutual_funds.cache import get_category_analysis as get_cached_category_analysis, put_category_analysis as cache_put_category_analysis
from backend.services.mutual_funds.insight_payload import build_mutual_fund_insight_context
from backend.services.ai.groq import AIInsightService, InsightResponse
from backend.services.mutual_funds.calculator import MetricsCalculator
from backend.services.data.tigzig import get_tigzig_dataset, get_tigzig_metadata, initialize_tigzig, _get_memory_mb
from backend.services.data.mfapi import MfapiError
from backend.utils.logging import logger

router = APIRouter()
settings = Settings()
fetcher = MutualFundFetcher(settings=settings)


class MutualFundInsightsRequest(BaseModel):
    """Bounded context submitted by the Fund Details AI action."""

    selected_fund: dict[str, Any]
    ranking: dict[str, Any]
    user_preferences: dict[str, Any]
    category_analysis: dict[str, Any] | None = None
    peers: list[dict[str, Any]] | None = None


class MutualFundRankingInsightsRequest(BaseModel):
    """Bounded context submitted by the ranking-level AI action."""

    ranking_configuration: dict[str, Any]
    ranking_summary: dict[str, Any]
    top_funds: list[dict[str, Any]]
    bottom_funds: list[dict[str, Any]] | None = None


@router.on_event("startup")
async def startup_event():
    """Initialize TigZig dataset at startup with minimal memory usage.

    This startup handler does NOT load the Parquet dataset into memory.
    It only checks file existence and logs the file size.
    The dataset will be loaded on-demand during ranking requests.
    """
    mem_before = _get_memory_mb()
    logger.info(f"Starting up mutual fund service... (memory: {mem_before:.1f} MB)")

    try:
        # Only check if dataset file exists, do NOT load it into memory
        dataset = get_tigzig_dataset()
        if dataset.is_available:
            # Lightweight check - only read file size, not Parquet metadata
            file_size = os.path.getsize(dataset.dataset_path)
            logger.info(
                f"TigZig dataset available: {file_size / (1024 * 1024):.1f} MB on disk. "
                f"Will be loaded on-demand during ranking."
            )
        else:
            logger.warning("TigZig dataset not found - will download on first ranking request")

        mem_after = _get_memory_mb()
        logger.info(f"Startup complete (memory: {mem_before:.1f} -> {mem_after:.1f} MB)")

    except Exception as e:
        logger.error(f"TigZig initialization failed: {e}")


@router.get("/")
async def list_schemes(category: str | None = None) -> dict[str, Any]:
    if category:
        schemes = await fetcher.get_schemes_by_category(category)
    else:
        schemes = await fetcher.get_all_schemes()
    return {
        "count": len(schemes),
        "category": category,
        "schemes": [s.model_dump() for s in schemes],
    }


@router.get("/categories")
async def list_categories() -> dict[str, Any]:
    schemes = await fetcher.get_all_schemes()
    # Normalize categories and get unique canonical categories
    canonical_categories = set()
    for s in schemes:
        if s.category:
            canonical_categories.add(normalize_category(s.category))
    return {"categories": sorted(canonical_categories)}


@router.get("/search")
async def search_schemes(q: str) -> dict[str, Any]:
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required.")
    results = await fetcher.search_schemes(q)
    return {"query": q, "count": len(results), "results": [r.model_dump() for r in results]}


@router.get("/{scheme_code}", response_model=MutualFund)
async def get_scheme(scheme_code: str) -> MutualFund:
    return await fetcher.get_scheme(scheme_code)


@router.get("/{scheme_code}/nav", response_model=list[NAVRecord])
async def get_nav_history(scheme_code: str) -> list[NAVRecord]:
    try:
        return await fetcher.get_nav_history(scheme_code)
    except MfapiError as e:
        logger.error("MFAPI failure for /nav/%s: %s", scheme_code, e)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error for /nav/%s: %s", scheme_code, e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch NAV history: {str(e)}")


@router.get("/{scheme_code}/returns")
async def get_returns(scheme_code: str) -> dict[str, Any]:
    scheme = await fetcher.get_scheme(scheme_code)
    return {
        "scheme_code": scheme.scheme_code,
        "scheme_name": scheme.scheme_name,
        "returns": {
            "1Y": scheme.one_year_return,
            "3Y": scheme.three_year_return,
            "5Y": scheme.five_year_return,
        },
    }


@router.get("/{scheme_code}/allocation")
async def get_allocation(scheme_code: str) -> dict[str, Any]:
    scheme = await fetcher.get_scheme(scheme_code)
    return {
        "scheme_code": scheme.scheme_code,
        "scheme_name": scheme.scheme_name,
        "asset_allocation": scheme.asset_allocation or {},
        "top_holdings": scheme.top_holdings or [],
    }


@router.get("/{scheme_code}/metrics")
async def get_metrics(scheme_code: str) -> dict[str, Any]:
    navs = await fetcher.get_nav_history(scheme_code)
    calculator = MetricsCalculator(scheme_code=scheme_code, nav_records=navs)
    metrics = calculator.calculate()
    return metrics.model_dump()


@router.get("/{scheme_code}/detail", response_model=FundDetailResponse)
async def get_fund_detail(scheme_code: str, response: Response = None) -> FundDetailResponse:
    """Get comprehensive fund detail including metrics, metadata, and allocation."""
    if response is not None:
        response.headers["Cache-Control"] = "private, max-age=300"
    try:
        scheme = await fetcher.get_scheme(scheme_code)
    except MfapiError as e:
        logger.error("MFAPI failure fetching scheme %s: %s", scheme_code, e)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error fetching scheme %s: %s", scheme_code, e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch fund details: {str(e)}")

    lookback_years = get_required_lookback_years([
        "1Y_return", "3Y_cagr", "5Y_cagr", "10Y_cagr",
        "sharpe_ratio", "sortino_ratio", "annualized_volatility",
        "maximum_drawdown", "downside_deviation", "consistency",
    ])

    metrics = await fetcher.get_or_compute_metrics(scheme_code, lookback_years)
    if metrics is None:
        raise HTTPException(
            status_code=502,
            detail="Insufficient data to compute fund metrics",
        )

    metadata_service = get_tigzig_metadata()
    metadata = await metadata_service.get_metadata()
    try:
        fund_metadata = metadata.get(int(scheme_code))
    except (ValueError, TypeError):
        fund_metadata = None

    nav = scheme.nav
    nav_date = scheme.nav_date

    first_nav_date = fund_metadata.get("first_date") if fund_metadata else None
    fund_age_years = None
    if first_nav_date:
        try:
            from datetime import datetime
            start = datetime.strptime(first_nav_date, "%Y-%m-%d")
            end = datetime.strptime(nav_date, "%Y-%m-%d") if nav_date else datetime.now()
            fund_age_years = (end - start).days / 365.25
        except (ValueError, TypeError):
            pass

    total_aum_cr = None
    total_aum_quarter = None
    total_aum_quarter_end = None
    if metadata:
        all_variants = await fetcher.get_scheme_variants(scheme_code)
        total_aum, total_quarter, total_quarter_end = _aggregate_total_aum(
            metadata, scheme_code, all_variants
        )
        if total_aum is not None:
            total_aum_cr = total_aum
            total_aum_quarter = total_quarter
            total_aum_quarter_end = total_quarter_end

    return FundDetailResponse(
        scheme_code=scheme.scheme_code,
        scheme_name=scheme.scheme_name,
        amc=scheme.amc,
        category=scheme.category,
        sub_category=scheme.sub_category,
        plan=_extract_plan(scheme.scheme_name),
        option=_extract_option(scheme.scheme_name),
        nav=nav,
        nav_date=nav_date,
        aum_cr=fund_metadata.get("aaum_cr_quarterly_avg") if fund_metadata else None,
        aum_quarter=fund_metadata.get("aaum_quarter") if fund_metadata else None,
        aum_quarter_end=fund_metadata.get("aaum_quarter_end") if fund_metadata else None,
        total_aum_cr=total_aum_cr,
        total_aum_quarter=total_aum_quarter,
        total_aum_quarter_end=total_aum_quarter_end,
        first_nav_date=first_nav_date,
        fund_age_years=fund_age_years,
        expense_ratio=scheme.expense_ratio,
        minimum_investment=scheme.minimum_investment,
        fund_manager=scheme.fund_manager,
        asset_allocation=scheme.asset_allocation,
        top_holdings=scheme.top_holdings,
        one_year_return=metrics.get("one_year_return"),
        three_year_cagr=metrics.get("three_year_cagr"),
        five_year_cagr=metrics.get("five_year_cagr"),
        ten_year_cagr=metrics.get("ten_year_cagr"),
        annualized_volatility=metrics.get("annualized_volatility"),
        one_year_volatility=metrics.get("one_year_volatility"),
        three_year_volatility=metrics.get("three_year_volatility"),
        five_year_volatility=metrics.get("five_year_volatility"),
        ten_year_volatility=metrics.get("ten_year_volatility"),
        sharpe_ratio=metrics.get("sharpe_ratio"),
        sortino_ratio=metrics.get("sortino_ratio"),
        maximum_drawdown=metrics.get("maximum_drawdown"),
        downside_deviation=metrics.get("downside_deviation"),
        rolling_return_consistency=metrics.get("rolling_return_consistency"),
        data_points=metrics.get("data_points", 0),
        data_start_date=metrics.get("data_start_date"),
        data_end_date=metrics.get("data_end_date"),
    )


@router.post("/{scheme_code}/insights", response_model=InsightResponse)
async def generate_mutual_fund_insights(
    scheme_code: str,
    payload: MutualFundInsightsRequest,
) -> InsightResponse:
    """Interpret the bounded Fund Details context with the configured AI service."""
    if not scheme_code.isdigit():
        raise HTTPException(status_code=404, detail="Fund not found")

    try:
        fund_detail = await get_fund_detail(scheme_code)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch fund detail for insights %s: %s", scheme_code, exc)
        raise HTTPException(status_code=500, detail="Failed to load fund details") from exc

    try:
        category_analysis = await get_category_analysis(scheme_code)
    except Exception as exc:
        logger.warning("Category analysis unavailable for insights %s: %s", scheme_code, exc)
        category_analysis = None

    # Validate the existing deterministic sources through the shared builder.
    # The frontend context remains the AI payload so it is not expanded here.
    build_mutual_fund_insight_context(
        fund_detail=fund_detail,
        category_analysis=category_analysis,
        user_preferences=payload.user_preferences,
    )

    try:
        return await AIInsightService(settings).generate_insights(
            data=payload.model_dump(exclude_unset=True),
            context="fund_analysis",
        )
    except RuntimeError as exc:
        logger.error("AI service unavailable for mutual fund %s: %s", scheme_code, exc)
        raise HTTPException(status_code=503, detail="The AI service is temporarily unavailable") from exc
    except Exception as exc:
        logger.error("Mutual fund insight generation failed for %s: %s", scheme_code, exc)
        raise HTTPException(status_code=503, detail="The AI service is temporarily unavailable") from exc


@router.post("/ranking-insights", response_model=InsightResponse)
async def generate_mutual_fund_ranking_insights(
    payload: MutualFundRankingInsightsRequest,
) -> InsightResponse:
    """Interpret the bounded deterministic ranking context with the AI service."""
    try:
        return await AIInsightService(settings).generate_insights(
            data=payload.model_dump(exclude_unset=True),
            context="ranking_summary",
            focus="holistic interpretation of the supplied ranking drivers, trade-offs, risks, and opportunities",
        )
    except RuntimeError as exc:
        logger.error("AI service unavailable for mutual fund ranking insights: %s", exc)
        raise HTTPException(status_code=503, detail="The AI service is temporarily unavailable") from exc
    except Exception as exc:
        logger.error("Mutual fund ranking insight generation failed: %s", exc)
        raise HTTPException(status_code=503, detail="The AI service is temporarily unavailable") from exc


@router.get("/{scheme_code}/category-analysis", response_model=CategoryAnalysisResponse)
async def get_category_analysis(scheme_code: str) -> CategoryAnalysisResponse:
    """Get category-relative analysis for a fund.

    Returns percentile ranks for the selected fund against its category peers
    for all available metrics.
    """
    try:
        detail = await get_fund_detail(scheme_code)
    except Exception as e:
        logger.error("Failed to fetch fund detail for category analysis %s: %s", scheme_code, e)
        raise HTTPException(status_code=502, detail=f"Failed to fetch fund detail: {str(e)}")

    category = detail.category
    if not category:
        raise HTTPException(status_code=400, detail="Fund has no category information")

    normalized_category = normalize_category(category)

    cached = get_cached_category_analysis(normalized_category)
    if cached:
        return CategoryAnalysisResponse(
            scheme_code=scheme_code,
            scheme_name=detail.scheme_name,
            category=category,
            metrics=[CategoryMetricPercentile(**m) for m in cached.get("metrics", [])],
        )

    engine = RankingEngine()
    criteria = [{"name": name, "weight": 1.0} for name in engine.CRITERIA.keys()]

    try:
        funds = await fetcher.get_ranking_candidates_by_category(normalized_category)
    except Exception as e:
        logger.error("Failed to fetch category funds for %s: %s", scheme_code, e)
        raise HTTPException(status_code=502, detail=f"Failed to fetch category funds: {str(e)}")

    valid_funds = []
    for f in funds:
        scheme_code_val = f.get("scheme_code") if isinstance(f, dict) else getattr(f, "scheme_code", None)
        if str(scheme_code_val) == str(scheme_code):
            continue
        valid_funds.append(f)

    if len(valid_funds) < 1:
        raise HTTPException(status_code=422, detail="Insufficient category data for percentile calculation")

    selected_fund_entry = None
    for f in funds:
        if str(f.get("scheme_code")) == str(scheme_code):
            selected_fund_entry = f
            break

    all_funds_for_metrics = valid_funds[:]
    if selected_fund_entry:
        all_funds_for_metrics.append(selected_fund_entry)

    metrics = await fetcher.get_metrics_batch(all_funds_for_metrics, [c["name"] for c in criteria])
    metrics_map = {}
    for f, m in zip(all_funds_for_metrics, metrics):
        if m:
            merged = dict(f)
            merged.update(m)
            metrics_map[str(f.get("scheme_code"))] = merged

    valid_with_metrics = [v for v in metrics_map.values() if v]
    if len(valid_with_metrics) < 2:
        raise HTTPException(status_code=422, detail="Insufficient category data with valid metrics")

    selected_fund = metrics_map.get(str(scheme_code), {})
    all_funds = [selected_fund] + [f for f in valid_with_metrics if str(f.get("scheme_code")) != str(scheme_code)]
    percentiles = engine.calculate_percentiles(all_funds, criteria)

    metric_percentiles = []
    for p in percentiles:
        if str(p.get("scheme_code")) != str(scheme_code):
            continue
        metric_percentiles.append(CategoryMetricPercentile(
            metric=p["metric"],
            label=p["label"],
            fund_value=p.get("fund_value"),
            percentile=p.get("percentile"),
            category_count=p.get("category_count", 0),
            higher_is_better=p.get("higher_is_better", True),
            rank=p.get("rank"),
        ))

    response = CategoryAnalysisResponse(
        scheme_code=scheme_code,
        scheme_name=detail.scheme_name,
        category=category,
        metrics=metric_percentiles,
    )

    cache_put_category_analysis(normalized_category, response.model_dump())
    return response


@router.get("/{scheme_code}/nav-history", response_model=NAVHistoryResponse)
async def get_nav_history_chart(scheme_code: str, years: int = 10, response: Response = None) -> NAVHistoryResponse:
    """Get NAV history for charting."""
    if response is not None:
        response.headers["Cache-Control"] = "private, max-age=300"
    try:
        scheme = await fetcher.get_scheme(scheme_code)
        navs = await fetcher.get_nav_history(scheme_code, lookback_years=years)
    except MfapiError as e:
        logger.error("MFAPI failure for /nav-history/%s: %s", scheme_code, e)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error for /nav-history/%s: %s", scheme_code, e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch NAV history: {str(e)}")

    dates = [n.date for n in navs]
    nav_values = [n.nav for n in navs]

    return NAVHistoryResponse(
        scheme_code=scheme_code,
        scheme_name=scheme.scheme_name,
        dates=dates,
        navs=nav_values,
    )


@router.get("/{scheme_code}/rolling-returns", response_model=RollingReturnResponse)
async def get_rolling_returns(scheme_code: str, years: int = 3) -> RollingReturnResponse:
    """Get rolling return time series for charting."""
    try:
        scheme = await fetcher.get_scheme(scheme_code)
        lookback = max(years, 10)
        navs = await fetcher.get_nav_history(scheme_code, lookback_years=lookback)
    except MfapiError as e:
        logger.error("MFAPI failure for /rolling-returns/%s: %s", scheme_code, e)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error for /rolling-returns/%s: %s", scheme_code, e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch rolling returns: {str(e)}")

    calculator = MetricsCalculator(scheme_code=scheme_code, nav_records=navs)
    result = calculator.get_rolling_returns_series(years)

    return RollingReturnResponse(
        scheme_code=scheme_code,
        scheme_name=scheme.scheme_name,
        period_years=years,
        dates=result["dates"],
        returns=result["returns"],
        summary=result["summary"],
        insufficient_history=result["insufficient_history"],
    )


def _extract_plan(scheme_name: str) -> str | None:
    """Extract plan type from scheme name."""
    if not scheme_name:
        return None
    name_lower = scheme_name.lower()
    if "direct" in name_lower:
        return "Direct"
    elif "regular" in name_lower:
        return "Regular"
    return None


def _extract_option(scheme_name: str) -> str | None:
    """Extract option type from scheme name."""
    if not scheme_name:
        return None
    name_lower = scheme_name.lower()
    if "growth" in name_lower:
        return "Growth"
    elif "idcw" in name_lower or "dividend" in name_lower:
        return "IDCW"
    return None


def _aggregate_total_aum(
    metadata: dict[int, dict[str, Any]],
    scheme_code: str,
    all_scheme_codes: list[str] | None = None,
) -> tuple[float | None, str | None, str | None]:
    """Aggregate AUM across all plan/option variants of the same underlying scheme.

    Uses the provided metadata dict (loaded once at the top of the request) for
    in-process lookups so each call within a single request reuses the same
    already-loaded snapshot rather than going through the global service.

    Args:
        metadata: In-process metadata snapshot keyed by scheme_code (int).
        scheme_code: The representative scheme code.
        all_scheme_codes: Optional list of all scheme codes in the same fund group.

    Returns:
        Tuple of (total_aum_cr, quarter, quarter_end)
    """
    if all_scheme_codes is None:
        all_scheme_codes = [str(scheme_code)]

    seen = set()
    unique_codes = []
    for code in all_scheme_codes:
        normalized = str(code)
        if normalized not in seen:
            seen.add(normalized)
            unique_codes.append(normalized)

    total_aum = 0.0
    quarters: list[str] = []
    quarter_ends: list[str] = []

    for code in unique_codes:
        try:
            meta = metadata.get(int(code))
        except (ValueError, TypeError):
            meta = None
        if not meta:
            continue
        aum = meta.get("aaum_cr_quarterly_avg")
        if aum is not None:
            try:
                total_aum += float(aum)
            except (TypeError, ValueError):
                pass
            quarter = meta.get("aaum_quarter")
            quarter_end = meta.get("aaum_quarter_end")
            if quarter:
                quarters.append(quarter)
            if quarter_end:
                quarter_ends.append(quarter_end)

    if total_aum <= 0 and not quarters:
        return None, None, None

    common_quarter = quarters[0] if quarters else None
    common_quarter_end = quarter_ends[0] if quarter_ends else None

    return total_aum, common_quarter, common_quarter_end


def _apply_screening_filters(
    funds: list[dict[str, Any]],
    filters: list,
    metadata: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply screening filters to underlying funds before ranking."""
    if not filters:
        return funds

    filtered = []
    for fund in funds:
        code = int(fund.get("_representative_scheme_code", 0))
        fund_meta = metadata.get(code, {})

        passes_all = True
        for f in filters:
            field = f.field
            op = f.operator

            if field == "amc":
                value = (fund.get("amc") or "").lower()
                if f.values:
                    if op == "in":
                        if not any(term.lower() in value for term in f.values):
                            passes_all = False
                            break
                    elif op == "not_in":
                        if any(term.lower() in value for term in f.values):
                            passes_all = False
                            break
                continue

            if field == "aum_cr":
                all_codes = fund.get("_all_scheme_codes") or [str(code)]
                total_aum, _, _ = _aggregate_total_aum(metadata, str(code), all_codes)
                value = total_aum
            elif field == "first_nav_date":
                value = fund_meta.get("first_date")
            elif field == "scheme_name":
                value = fund.get("scheme_name") or ""
                if f.values:
                    if op == "in":
                        if not any(v.lower() in value.lower() for v in f.values):
                            passes_all = False
                            break
                    continue
                continue
            else:
                continue

            if value is None:
                passes_all = False
                break

            if op == "gt" and not (value > f.value):
                passes_all = False
                break
            elif op == "gte" and not (value >= f.value):
                passes_all = False
                break
            elif op == "lt" and not (value < f.value):
                passes_all = False
                break
            elif op == "lte" and not (value <= f.value):
                passes_all = False
                break
            elif op == "between":
                if f.value_min is not None and value < f.value_min:
                    passes_all = False
                    break
                if f.value_max is not None and value > f.value_max:
                    passes_all = False
                    break

        if passes_all:
            filtered.append(fund)

    return filtered


@router.post("/rank")
async def rank_funds(payload: RankingRequest) -> dict[str, Any]:
    import time as time_module

    total_start = time_module.time()

    # Get underlying funds for all selected categories
    categories = payload.category if isinstance(payload.category, list) else [payload.category]
    categories = [c for c in categories if c]  # Remove empty strings

    if not categories:
        return {
            "category": categories,
            "categories_count": 0,
            "rankings": [],
            "meta": {
                "underlying_funds": 0,
                "ranked": 0,
                "skipped": 0,
            },
        }

    # Collect funds from all categories, deduplicating by scheme code
    underlying_funds = []
    seen_codes = set()
    for cat in categories:
        cat_funds = await fetcher.get_ranking_candidates_by_category(cat)
        for fund in cat_funds:
            code = fund.get("_representative_scheme_code")
            if code and code not in seen_codes:
                seen_codes.add(code)
                underlying_funds.append(fund)

    fund_count = len(underlying_funds)
    logger.info(
        "Found %d underlying funds across %d categories: %s",
        fund_count, len(categories), categories
    )

    if fund_count == 0:
        return {
            "category": categories,
            "categories_count": len(categories),
            "rankings": [],
            "meta": {
                "underlying_funds": 0,
                "ranked": 0,
                "skipped": 0,
            },
        }

    # Apply screening filters before metric calculation
    screened_count = fund_count
    if payload.screening_filters:
        metadata_service = get_tigzig_metadata()
        metadata = await metadata_service.get_metadata()
        underlying_funds = _apply_screening_filters(
            underlying_funds, payload.screening_filters, metadata
        )
        screened_count = len(underlying_funds)
        logger.info("After screening: %d funds match filters", screened_count)

        if not underlying_funds:
            return {
                "category": categories,
                "categories_count": len(categories),
                "rankings": [],
                "meta": {
                    "underlying_funds": fund_count,
                    "ranked": 0,
                    "skipped": fund_count,
                    "screened_matching": 0,
                },
            }

    criteria_names = [c.name for c in payload.criteria]
    lookback_years = get_required_lookback_years(criteria_names)
    logger.info("Required lookback: %d years (criteria: %s)", lookback_years, criteria_names)

    # Check TigZig availability
    dataset = get_tigzig_dataset()
    tigzig_available = dataset.is_available
    logger.info(f"TigZig dataset available: {tigzig_available}")

    # Use batch metrics for efficiency
    t0 = time_module.time()
    metrics_list = await fetcher.get_metrics_batch(underlying_funds, criteria_names)
    batch_time = time_module.time() - t0

    # Filter out None results
    valid_metrics = [m for m in metrics_list if m is not None]
    skipped_count = fund_count - len(valid_metrics)

    scheme_variants = {}
    for fund in underlying_funds:
        code = fund.get("_representative_scheme_code")
        if code:
            scheme_variants[str(code)] = fund.get("_all_scheme_codes") or [str(code)]

    logger.info(
        "Metrics calculated: %d/%d funds (%.1f%% success) in %.2f seconds",
        len(valid_metrics),
        fund_count,
        len(valid_metrics) / max(fund_count, 1) * 100,
        batch_time,
    )

    engine = RankingEngine()
    criteria = [c.model_dump() for c in payload.criteria]
    try:
        rankings = engine.rank(funds=valid_metrics, criteria=criteria, auto_renormalize=payload.auto_renormalize)
    except ValueError as e:
        logger.warning("Ranking validation error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    # Enrich rankings with metadata (AUM, first NAV date) using the in-memory
    # metadata snapshot already loaded for this request. Avoids repeated
    # per-fund service-method calls and the int() conversion overhead.
    metadata_service = get_tigzig_metadata()
    metadata = await metadata_service.get_metadata()
    for r in rankings:
        code = r.get("scheme_code")
        if code:
            try:
                fund_metadata = metadata.get(int(code))
            except (ValueError, TypeError):
                fund_metadata = None
            if fund_metadata:
                if fund_metadata.get("aaum_cr_quarterly_avg") is not None:
                    r["aum_cr"] = fund_metadata["aaum_cr_quarterly_avg"]
                    r["aum_quarter"] = fund_metadata.get("aaum_quarter")
                    r["aum_quarter_end"] = fund_metadata.get("aaum_quarter_end")
                if fund_metadata.get("first_date"):
                    r["first_nav_date"] = fund_metadata["first_date"]

            all_codes = scheme_variants.get(str(code)) or [str(code)]
            total_aum, total_quarter, total_quarter_end = _aggregate_total_aum(
                metadata, code, all_codes
            )
            if total_aum is not None:
                r["total_aum_cr"] = total_aum
                r["total_aum_quarter"] = total_quarter
                r["total_aum_quarter_end"] = total_quarter_end

    total_time = time_module.time() - total_start
    logger.info(
        "Ranking complete: %d funds ranked in %.2f seconds (cache stats: %s)",
        len(rankings),
        total_time,
        metrics_cache.stats(),
    )

    return {
        "category": categories,
        "categories_count": len(categories),
        "rankings": rankings,
        "meta": {
            "underlying_funds": fund_count,
            "ranked": len(rankings),
            "skipped": skipped_count,
            "tigzig_available": tigzig_available,
            "total_time_seconds": total_time,
            "screened_matching": screened_count,
        },
    }
