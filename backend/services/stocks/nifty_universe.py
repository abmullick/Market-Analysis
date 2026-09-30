from __future__ import annotations

import csv
import io
import time
from typing import Any

import curl_cffi.requests

# NSE Indices currently exposes the Nifty Total Market constituent file
# using this filename. Keep this URL aligned with the link published on
# the official Nifty Total Market page rather than maintaining a local
# symbol list.
NIFTY_TOTAL_MARKET_CSV = "https://www.niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv"
CACHE_TTL_SECONDS = 24 * 60 * 60
_cache: dict[str, Any] = {"expires_at": 0.0, "stocks": []}


class NiftyUniverseError(Exception):
    """Raised when the official Nifty Total Market constituent file cannot be loaded."""


def _normalise_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    return symbol if symbol.endswith(".NS") else f"{symbol}.NS" if symbol else ""


def _first(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value:
            return value.strip()
    return ""


def _parse_csv(payload: bytes) -> list[dict[str, str]]:
    text = payload.decode("utf-8-sig", errors="replace")

    # If the endpoint returns an HTML error/challenge page instead of the
    # CSV, fail with a useful message instead of reporting an empty universe.
    if "<html" in text[:1000].lower() or "<!doctype" in text[:1000].lower():
        raise NiftyUniverseError(
            "Nifty Total Market endpoint returned HTML instead of the constituent CSV"
        )

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise NiftyUniverseError("Nifty Total Market CSV has no header")

    # Normalize header whitespace/BOM/case so small changes in NSE's CSV
    # formatting do not make the entire universe disappear.
    normalized_rows: list[dict[str, str]] = []
    for row in reader:
        normalized_rows.append({
            str(key).strip(): (value or "").strip()
            for key, value in row.items()
            if key is not None
        })

    stocks: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in normalized_rows:
        symbol = _normalise_symbol(
            _first(row, "Symbol", "SYMBOL", "Symbol ")
        )
        name = _first(
            row,
            "Company Name",
            "CompanyName",
            "COMPANY NAME",
            "Company",
        )
        sector = _first(
            row,
            "Industry",
            "INDUSTRY",
            "Sector",
            "SECTOR",
        )
        series = _first(row, "Series", "SERIES")
        isin = _first(row, "ISIN Code", "ISIN", "ISINCODE")

        if not symbol or not name or symbol in seen:
            continue

        if series and series.upper() not in {"EQ", "BE", "BZ"}:
            continue

        seen.add(symbol)
        stocks.append({
            "symbol": symbol,
            "name": name,
            "sector": sector or "Other",
            "isin": isin,
        })

    if not stocks:
        headers = ", ".join(reader.fieldnames or [])
        raise NiftyUniverseError(
            "Nifty Total Market CSV contained no usable stocks "
            f"(headers received: {headers})"
        )

    return stocks


def load_nifty_total_market(force_refresh: bool = False) -> list[dict[str, str]]:
    now = time.time()
    if not force_refresh and _cache["stocks"] and now < _cache["expires_at"]:
        return list(_cache["stocks"])

    session = curl_cffi.requests.Session(impersonate="chrome")
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/154.0.0.0 Safari/537.36"
        ),
        "Accept": "text/csv,text/plain,application/octet-stream,*/*",
        "Referer": "https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-total-market",
    })

    try:
        response = session.get(
            NIFTY_TOTAL_MARKET_CSV,
            timeout=20,
        )
        response.raise_for_status()
        stocks = _parse_csv(response.content)
    except NiftyUniverseError:
        raise
    except Exception as exc:
        raise NiftyUniverseError(
            "Unable to load the official Nifty Total Market constituent file: "
            f"{exc}"
        ) from exc
    finally:
        session.close()

    _cache["stocks"] = stocks
    _cache["expires_at"] = now + CACHE_TTL_SECONDS
    return list(stocks)


def nifty_sectors() -> list[str]:
    return sorted({
        stock["sector"]
        for stock in load_nifty_total_market()
    })
