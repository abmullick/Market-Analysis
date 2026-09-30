from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.config.settings import Settings
from backend.services.data.fundamentals import get_stock_analysis
from backend.services.data.yahoo import YahooFinanceClient, YahooFinanceError
from backend.services.stocks.universe import list_stocks, sectors

router = APIRouter()
client = YahooFinanceClient(Settings())


@router.get("/universe")
async def get_stock_universe(
    sector: Optional[str] = Query(default=None),
    query: Optional[str] = Query(default=None),
    min_market_cap_cr: Optional[float] = Query(default=None, ge=0),
    max_market_cap_cr: Optional[float] = Query(default=None, ge=0),
    min_pe: Optional[float] = Query(default=None, ge=0),
    max_pe: Optional[float] = Query(default=None, gt=0),
    min_roe: Optional[float] = Query(default=None),
    max_roe: Optional[float] = Query(default=None),
):
    """Return stocks for the selection screen, optionally filtered by sector and fundamental ranges."""
    if not sector:
        return {"sectors": sectors(), "stocks": [], "count": 0}
    try:
        return list_stocks(
            client,
            sector=sector,
            query=query,
            min_market_cap_cr=min_market_cap_cr,
            max_market_cap_cr=max_market_cap_cr,
            min_pe=min_pe,
            max_pe=max_pe,
            min_roe=min_roe,
            max_roe=max_roe,
        )
    except YahooFinanceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}/fundamentals")
async def get_fundamentals(symbol: str):
    try:
        return get_stock_analysis(client, symbol)["fundamentals"]
    except YahooFinanceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}")
async def get_stock(symbol: str):
    try:
        return get_stock_analysis(client, symbol)
    except YahooFinanceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
