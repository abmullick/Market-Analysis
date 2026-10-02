from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import time
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.services.stocks.nifty_universe import (
    NiftyUniverseError,
    _download,
    _normalise_symbol,
    _parse_csv,
)

router = APIRouter()

# NSE Indices defines the broad-cap segments by these index families:
# Large = Nifty 100, Mid = Nifty Midcap 150, Small = Nifty Smallcap 250,
# Micro = Nifty Microcap 250. These are index classifications, not a daily
# market-cap calculation, and therefore do not require 755 Screener requests.
CAP_SOURCES = {
    "large": (
        "https://nsearchives.nseindia.com/content/indices/ind_nifty100list.csv",
        "Nifty 100",
    ),
    "mid": (
        "https://nsearchives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
        "Nifty Midcap 150",
    ),
    "small": (
        "https://nsearchives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
        "Nifty Smallcap 250",
    ),
    "micro": (
        "https://nsearchives.nseindia.com/content/indices/ind_niftymicrocap250_list.csv",
        "Nifty Microcap 250",
    ),
}

CAP_LABELS = {
    "large": "Large Cap",
    "mid": "Mid Cap",
    "small": "Small Cap",
    "micro": "Micro Cap",
}

_cache: dict[str, Any] = {"expires_at": 0.0, "bands": {}}
CACHE_TTL_SECONDS = 24 * 60 * 60


def _load_one(item: tuple[str, str]) -> tuple[str, list[dict[str, str]]]:
    key = next(k for k, value in CAP_SOURCES.items() if value == item)
    url, label = item
    try:
        rows = _parse_csv(_download(url))
        return key, rows
    except Exception as exc:
        raise NiftyUniverseError(f"{label}: {exc}") from exc


def _build_bands() -> dict[str, str]:
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_load_one, CAP_SOURCES.values()))

    bands: dict[str, str] = {}
    # The official segments are intended to be disjoint. Keep the explicit
    # precedence as a guard against an unexpected duplicate in a source file.
    for key in ("large", "mid", "small", "micro"):
        _, rows = next(result for result in results if result[0] == key)
        for row in rows:
            symbol = _normalise_symbol(str(row.get("symbol") or ""))
            if symbol and symbol not in bands:
                bands[symbol] = key
    return bands


@router.get("/market-cap-bands")
def get_market_cap_bands():
    now = time.time()
    if _cache["bands"] and now < _cache["expires_at"]:
        bands = _cache["bands"]
    else:
        try:
            bands = _build_bands()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        _cache["bands"] = bands
        _cache["expires_at"] = now + CACHE_TTL_SECONDS

    return {
        "bands": bands,
        "labels": CAP_LABELS,
        "count": len(bands),
        "source": "NSE Indices broad-market index classification",
        "method": "Nifty 100 / Nifty Midcap 150 / Nifty Smallcap 250 / Nifty Microcap 250 membership",
        "cache_ttl_hours": 24,
    }
