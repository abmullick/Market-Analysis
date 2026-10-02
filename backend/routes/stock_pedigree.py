import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.services.data.screener import ScreenerFinanceClient, ScreenerFinanceError
from backend.services.data.stock_pedigree import build_stock_pedigree

router = APIRouter()
client = ScreenerFinanceClient()


@router.get("/pedigree/compare")
async def compare_stock_pedigree(
    symbols: Optional[list[str]] = Query(default=None),
):
    requested = symbols or []
    cleaned = []
    for symbol in requested:
        value = symbol.strip().upper()
        if value and value not in cleaned:
            cleaned.append(value)
    if not cleaned or len(cleaned) > 4:
        raise HTTPException(status_code=400, detail="Provide between 1 and 4 stock symbols.")

    def build_all() -> tuple[list[dict], list[dict]]:
        results = []
        errors = []
        for symbol in cleaned:
            try:
                results.append(build_stock_pedigree(client, symbol))
            except ScreenerFinanceError as exc:
                errors.append({"symbol": symbol, "error": str(exc)})
        return results, errors

    results, errors = await asyncio.to_thread(build_all)
    if not results and errors:
        raise HTTPException(status_code=502, detail=errors[0]["error"])
    return {"stocks": results, "errors": errors}


@router.get("/pedigree/{symbol}")
async def stock_pedigree(symbol: str):
    try:
        return await asyncio.to_thread(build_stock_pedigree, client, symbol)
    except ScreenerFinanceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
