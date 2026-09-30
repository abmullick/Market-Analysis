from fastapi import APIRouter, HTTPException

from backend.config.settings import Settings
from backend.services.data.fundamentals import get_stock_analysis
from backend.services.data.yahoo import YahooFinanceClient, YahooFinanceError

router = APIRouter()
client = YahooFinanceClient(Settings())


@router.get("/{symbol}")
async def get_stock(symbol: str):
    try:
        return get_stock_analysis(client, symbol)
    except YahooFinanceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}/fundamentals")
async def get_fundamentals(symbol: str):
    try:
        return get_stock_analysis(client, symbol)["fundamentals"]
    except YahooFinanceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
