from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/{symbol}")
async def get_stock(symbol: str):
    raise NotImplementedError("Stock endpoint not yet implemented.")


@router.get("/{symbol}/fundamentals")
async def get_fundamentals(symbol: str):
    raise NotImplementedError("Fundamentals endpoint not yet implemented.")
