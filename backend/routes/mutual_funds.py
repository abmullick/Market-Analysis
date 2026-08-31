import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.config.settings import Settings
from backend.models.mutual_fund import (
    FundMetrics,
    MutualFund,
    NAVRecord,
    RankingRequest,
    SchemeSearchResult,
)
from backend.services.mutual_funds.fetcher import MutualFundFetcher
from backend.services.mutual_funds.lookback import get_required_lookback_years
from backend.services.mutual_funds.ranking import RankingEngine
from backend.services.mutual_funds.category_normalizer import normalize_category
from backend.services.mutual_funds.cache import metrics_cache
from backend.services.data.tigzig import get_tigzig_dataset, initialize_tigzig
from backend.utils.logging import logger

router = APIRouter()
settings = Settings()
fetcher = MutualFundFetcher(settings=settings)


@router.on_event("startup")
async def startup_event():
    """Initialize TigZig dataset at startup."""
    logger.info("Starting up mutual fund service...")
    try:
        success = await initialize_tigzig()
        if success:
            dataset = get_tigzig_dataset()
            stats = dataset.stats
            logger.info(
                f"TigZig dataset ready: {stats.get('size_mb', 0):.1f} MB, "
                f"{stats.get('total_rows', 0):,} rows"
            )
        else:
            logger.error("TigZig dataset not available - ranking will use MFAPI fallback")
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
    return await fetcher.get_nav_history(scheme_code)


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


@router.post("/rank")
async def rank_funds(payload: RankingRequest) -> dict[str, Any]:
    import time as time_module

    total_start = time_module.time()

    # Get underlying funds (one per AMC + normalized name)
    underlying_funds = await fetcher.get_ranking_candidates_by_category(payload.category)
    fund_count = len(underlying_funds)
    logger.info("Found %d underlying funds in category: %s", fund_count, payload.category)

    if fund_count == 0:
        return {
            "category": payload.category,
            "rankings": [],
            "meta": {
                "underlying_funds": 0,
                "ranked": 0,
                "skipped": 0,
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

    logger.info(
        "Metrics calculated: %d/%d funds (%.1f%% success) in %.2f seconds",
        len(valid_metrics),
        fund_count,
        len(valid_metrics) / max(fund_count, 1) * 100,
        batch_time,
    )

    engine = RankingEngine()
    criteria = [c.model_dump() for c in payload.criteria]
    rankings = engine.rank(funds=valid_metrics, criteria=criteria, auto_renormalize=payload.auto_renormalize)

    total_time = time_module.time() - total_start
    logger.info(
        "Ranking complete: %d funds ranked in %.2f seconds (cache stats: %s)",
        len(rankings),
        total_time,
        metrics_cache.stats(),
    )

    return {
        "category": payload.category,
        "rankings": rankings,
        "meta": {
            "underlying_funds": fund_count,
            "ranked": len(rankings),
            "skipped": skipped_count,
            "tigzig_available": tigzig_available,
            "total_time_seconds": total_time,
        },
    }
