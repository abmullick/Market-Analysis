from fastapi import APIRouter, HTTPException

from backend.config.settings import Settings
from backend.services.data.fundamentals import build_analysis
from backend.services.data.yahoo import YahooFinanceClient, YahooFinanceError

router = APIRouter()
_client = YahooFinanceClient(Settings())


def _load(symbol: str) -> dict:
    try:
        return build_analysis(_client, symbol)
    except YahooFinanceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Stock analysis failed: {exc}") from exc


@router.get("/{symbol}")
async def get_stock(symbol: str):
    return _load(symbol)


@router.get("/{symbol}/fundamentals")
async def get_fundamentals(symbol: str):
    return _load(symbol)["fundamentals"]
