from typing import Any
import asyncio

from fastapi import APIRouter, HTTPException

from backend.services.data.stock_charts import yahoo_annual_prices

router = APIRouter()

BENCHMARKS: dict[str, dict[str, str]] = {
    "nifty50": {"label": "NIFTY 50", "symbol": "^NSEI"},
    "nifty500": {"label": "NIFTY 500", "symbol": "^CRSLDX"},
    "sensex": {"label": "BSE SENSEX", "symbol": "^BSESN"},
}


def _cagr(prices: list[dict[str, Any]], years: int) -> float | None:
    if len(prices) < 2:
        return None
    end = float(prices[-1]["close"])
    target_year = int(str(prices[-1]["date"])[:4]) - years
    starts = [p for p in prices if int(str(p["date"])[:4]) <= target_year]
    if not starts:
        return None
    start = float(starts[-1]["close"])
    actual_years = int(str(prices[-1]["date"])[:4]) - int(str(starts[-1]["date"])[:4])
    if start <= 0 or end <= 0 or actual_years <= 0:
        return None
    return ((end / start) ** (1 / actual_years) - 1) * 100


def _load_benchmarks() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, meta in BENCHMARKS.items():
        prices = yahoo_annual_prices(meta["symbol"], years=12)
        result[key] = {
            "label": meta["label"],
            "symbol": meta["symbol"],
            "available": bool(prices),
            "prices": prices,
            "cagr": {str(years): _cagr(prices, years) for years in (1, 3, 5, 10)},
        }
    return result


@router.get("/comparison")
async def get_stock_portfolio_benchmarks():
    try:
        return await asyncio.to_thread(_load_benchmarks)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Benchmark market data is temporarily unavailable") from exc
