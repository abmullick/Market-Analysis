from __future__ import annotations

import time
from typing import Any

import curl_cffi.requests


class LiquidityDataError(Exception):
    pass


_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/154.0.0.0 Safari/537.36"
)
_CACHE_TTL_SECONDS = 6 * 60 * 60
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def get_three_month_liquidity(symbol: str) -> dict[str, Any]:
    """Return three-month daily volume and average traded value for an NSE ticker."""
    symbol = symbol.strip().upper()
    cached = _CACHE.get(symbol)
    if cached and time.time() < cached[0]:
        return dict(cached[1])

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    session = curl_cffi.requests.Session(impersonate="chrome")
    session.headers.update({"User-Agent": _USER_AGENT, "Accept": "application/json"})
    try:
        response = session.get(url, params={"range": "3mo", "interval": "1d", "events": "history"}, timeout=20)
        response.raise_for_status()
        payload = response.json()
        result = (payload.get("chart", {}).get("result") or [None])[0]
        if not result:
            raise LiquidityDataError(f"No Yahoo chart data for {symbol}")
        quote = (result.get("indicators", {}).get("quote") or [{}])[0]
        volumes = quote.get("volume") or []
        closes = quote.get("close") or []
        observations = [(float(v), float(p)) for v, p in zip(volumes, closes) if v is not None and p is not None and v >= 0 and p > 0]
        if not observations:
            result_data = {"avg_daily_volume_3m": None, "avg_daily_traded_value_3m_cr": None, "trading_observations_3m": 0, "liquidity_market_data_source": "Yahoo Finance daily market volume/close"}
        else:
            avg_volume = sum(v for v, _ in observations) / len(observations)
            avg_traded_value = sum(v * p for v, p in observations) / len(observations) / 1e7
            result_data = {
                "avg_daily_volume_3m": avg_volume,
                "avg_daily_traded_value_3m_cr": avg_traded_value,
                "trading_observations_3m": len(observations),
                "liquidity_market_data_source": "Yahoo Finance daily market volume/close",
            }
        _CACHE[symbol] = (time.time() + _CACHE_TTL_SECONDS, result_data)
        return dict(result_data)
    except Exception as exc:
        raise LiquidityDataError(str(exc)) from exc
    finally:
        session.close()
