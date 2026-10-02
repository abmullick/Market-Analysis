from __future__ import annotations

from threading import Lock
import time
from typing import Any

from backend.services.stocks.nifty_universe import load_nifty_total_market

CACHE_TTL_SECONDS = 24 * 60 * 60
_lock = Lock()
_cache: dict[str, Any] = {"expires_at": 0.0, "stocks": []}


def load_fast_nifty_total_market() -> list[dict[str, str]]:
    now = time.time()
    if _cache["stocks"] and now < _cache["expires_at"]:
        return list(_cache["stocks"])

    # Coalesce concurrent page-load requests. Without this guard, the core
    # selector and enhancement modules can both download the NSE universe at
    # the same time, making Ctrl+R appear to hang.
    with _lock:
        now = time.time()
        if _cache["stocks"] and now < _cache["expires_at"]:
            return list(_cache["stocks"])
        stocks = load_nifty_total_market()
        _cache["stocks"] = stocks
        _cache["expires_at"] = now + CACHE_TTL_SECONDS
        return list(stocks)
