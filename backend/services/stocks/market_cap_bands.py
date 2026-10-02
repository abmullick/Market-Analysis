from __future__ import annotations

import csv
import io
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import curl_cffi.requests

CACHE_TTL_SECONDS = 24 * 60 * 60

# Official Nifty broad-market segment constituent files. The segment
# definitions are maintained by NSE Indices; the files are used only when a
# user explicitly selects a market-cap preset, never during normal page load.
SOURCES = {
    "large": "https://nsearchives.nseindia.com/content/indices/ind_nifty100list.csv",
    "mid": "https://nsearchives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
    "small": "https://nsearchives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
    "micro": "https://nsearchives.nseindia.com/content/indices/ind_niftymicrocap250_list.csv",
}

FALLBACK_SOURCES = {
    "large": "https://www.niftyindices.com/IndexConstituent/ind_nifty100list.csv",
    "mid": "https://www.niftyindices.com/IndexConstituent/ind_niftymidcap150list.csv",
    "small": "https://www.niftyindices.com/IndexConstituent/ind_niftysmallcap250list.csv",
    "micro": "https://www.niftyindices.com/IndexConstituent/ind_niftymicrocap250_list.csv",
}

_cache: dict[str, object] = {"expires_at": 0.0, "bands": {}}
_lock = Lock()


def _normalise_symbol(value: str) -> str:
    symbol = str(value or "").strip().upper()
    return symbol if symbol.endswith(".NS") else f"{symbol}.NS"


def _download(url: str) -> bytes:
    session = curl_cffi.requests.Session(impersonate="chrome")
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/154 Safari/537.36",
        "Accept": "text/csv,application/CSV,text/plain,*/*",
        "Referer": "https://www.niftyindices.com/",
    })
    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
        return response.content
    finally:
        session.close()


def _parse_symbols(payload: bytes) -> set[str]:
    text = payload.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return set()
    symbol_col = next((c for c in reader.fieldnames if str(c).strip().lower() in {"symbol", "stock symbol", "security symbol"}), None)
    if not symbol_col:
        return set()
    return {_normalise_symbol(row.get(symbol_col, "")) for row in reader if row.get(symbol_col)}


def _load_band(key: str) -> tuple[str, set[str]]:
    try:
        symbols = _parse_symbols(_download(SOURCES[key]))
        if symbols:
            return key, symbols
    except Exception:
        pass
    try:
        symbols = _parse_symbols(_download(FALLBACK_SOURCES[key]))
        return key, symbols
    except Exception:
        return key, set()


def load_market_cap_bands() -> dict[str, str]:
    now = time.time()
    if _cache["bands"] and now < float(_cache["expires_at"]):
        return dict(_cache["bands"])

    with _lock:
        now = time.time()
        if _cache["bands"] and now < float(_cache["expires_at"]):
            return dict(_cache["bands"])

        result: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            for key, symbols in pool.map(_load_band, SOURCES.keys()):
                for symbol in symbols:
                    result.setdefault(symbol, key)

        if not result:
            raise RuntimeError("Unable to load official Nifty market-cap constituent data")

        _cache["bands"] = result
        _cache["expires_at"] = now + CACHE_TTL_SECONDS
        return dict(result)
