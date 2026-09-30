from __future__ import annotations

import csv
import io
import time
from typing import Any

import curl_cffi.requests


NIFTY_TOTAL_MARKET_CSV = "https://www.niftyindices.com/IndexConstituent/ind_niftytotalmarketlist.csv"
CACHE_TTL_SECONDS = 24 * 60 * 60

_cache: dict[str, Any] = {"expires_at": 0.0, "stocks": []}


class NiftyUniverseError(Exception):
    """Raised when the official Nifty Total Market constituent file cannot be loaded."""


def _normalise_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not symbol:
        return ""
    return symbol if symbol.endswith(".NS") else f"{symbol}.NS"


def _first(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value:
            return value.strip()
    return ""


def _parse_csv(payload: bytes) -> list[dict[str, str]]:
    text = payload.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise NiftyUniverseError("Nifty Total Market CSV has no header")

    stocks: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in reader:
        symbol = _normalise_symbol(_first(row, "Symbol", "SYMBOL"))
        name = _first(row, "Company Name", "CompanyName", "COMPANY NAME", "Company")
        sector = _first(row, "Industry", "INDUSTRY", "Sector", "SECTOR")
        series = _first(row, "Series", "SERIES")
        isin = _first(row, "ISIN Code", "ISIN", "ISINCODE")

        if not symbol or not name or symbol in seen:
            continue

        # Nifty Total Market is an equity-stock universe. Keep only normal EQ
        # listings if the source happens to contain another series.
        if series and series.upper() not in {"EQ", "BE", "BZ"}:
            continue

        seen.add(symbol)
        stocks.append(
            {
                "symbol": symbol,
                "name": name,
                "sector": sector or "Other",
                "isin": isin,
            }
        )

    if not stocks:
        raise NiftyUniverseError("Nifty Total Market CSV contained no usable stocks")

    return stocks


def load_nifty_total_market(force_refresh: bool = False) -> list[dict[str, str]]:
    now = time.time()
    if not force_refresh and _cache["stocks"] and now < _cache["expires_at"]:
        return list(_cache["stocks"])

    session = curl_cffi.requests.Session(impersonate="chrome")
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/154.0.0.0 Safari/537.36"
            ),
            "Accept": "text/csv,text/plain,*/*",
            "Referer": "https://www.niftyindices.com/",
        }
    )

    try:
        response = session.get(NIFTY_TOTAL_MARKET_CSV, timeout=20)
        response.raise_for_status()
        stocks = _parse_csv(response.content)
    except Exception as exc:
        raise NiftyUniverseError(
            f"Unable to load the official Nifty Total Market constituent file: {exc}"
        ) from exc
    finally:
        session.close()

    _cache["stocks"] = stocks
    _cache["expires_at"] = now + CACHE_TTL_SECONDS
    return list(stocks)


def nifty_sectors() -> list[str]:
    return sorted({stock["sector"] for stock in load_nifty_total_market()})
