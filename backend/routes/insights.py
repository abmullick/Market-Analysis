from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.post("/stock")
async def generate_stock_insights(payload: dict[str, Any]):
    raise NotImplementedError("Insights endpoint not yet implemented.")


@router.post("/portfolio")
async def generate_portfolio_insights(payload: dict[str, Any]):
    raise NotImplementedError("Portfolio insights endpoint not yet implemented.")
