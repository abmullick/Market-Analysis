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
from backend.services.data.tigzig import get_tigzig_dataset, get_tigzig_metadata, initialize_tigzig
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
                value = fund.get("amc") or ""
                if f.values:
                    if op == "in":
                        if value not in f.values:
                            passes_all = False
                            break
                    elif op == "not_in":
                        if value in f.values:
                            passes_all = False
                            break
                continue

            if field == "aum_cr":
                value = fund_meta.get("aaum_cr_quarterly_avg")
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
                "category": payload.category,
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

    # Enrich rankings with metadata (AUM, first NAV date)
    metadata_service = get_tigzig_metadata()
    metadata = await metadata_service.get_metadata()
    for r in rankings:
        code = r.get("scheme_code")
        if code:
            try:
                fund_metadata = metadata_service.lookup(int(code))
            except (ValueError, TypeError):
                fund_metadata = None
            if fund_metadata:
                if fund_metadata.get("aaum_cr_quarterly_avg") is not None:
                    r["aum_cr"] = fund_metadata["aaum_cr_quarterly_avg"]
                    r["aum_quarter"] = fund_metadata.get("aaum_quarter")
                    r["aum_quarter_end"] = fund_metadata.get("aaum_quarter_end")
                if fund_metadata.get("first_date"):
                    r["first_nav_date"] = fund_metadata["first_date"]

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
            "screened_matching": screened_count,
        },
    }
