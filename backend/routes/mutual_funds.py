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
from backend.services.mutual_funds.calculator import MetricsCalculator
from backend.services.mutual_funds.fetcher import MutualFundFetcher
from backend.services.mutual_funds.ranking import RankingEngine
from backend.utils.logging import logger

router = APIRouter()
settings = Settings()
fetcher = MutualFundFetcher(settings=settings)


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
    categories = sorted({s.category for s in schemes if s.category})
    return {"categories": categories}


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
    schemes = await fetcher.get_schemes_by_category(payload.category)
    schemes = schemes[:20]
    funds: list[FundMetrics] = []
    sem = asyncio.Semaphore(5)

    async def fetch_metrics(scheme):
        async with sem:
            try:
                navs = await fetcher.get_nav_history(scheme.scheme_code)
                calculator = MetricsCalculator(scheme_code=scheme.scheme_code, nav_records=navs)
                metrics = calculator.calculate()
                if metrics.data_points >= 2:
                    metrics.scheme_name = scheme.scheme_name
                    metrics.category = scheme.category
                    return metrics
            except Exception as e:
                logger.warning("Skipping scheme %s: %s", scheme.scheme_code, e)
            return None

    results = await asyncio.gather(*[fetch_metrics(s) for s in schemes])
    funds = [r for r in results if r is not None]

    engine = RankingEngine()
    criteria = [c.model_dump() for c in payload.criteria]
    rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=payload.auto_renormalize)
    return {"category": payload.category, "rankings": rankings}
