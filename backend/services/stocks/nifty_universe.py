from __future__ import annotations

import csv
import io
import time
from typing import Any

import curl_cffi.requests

# Official NSE Indices constituent file for Nifty Total Market.
# Nifty Total Market covers the broad NSE universe represented by Nifty 500
# plus Nifty Microcap 250; the constituent file is the source of symbols and
# NSE industry classification rather than a manually maintained list.
NIFTY_TOTAL_MARKET_CSV = "https://www.niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv"
NIFTY_TOTAL_MARKET_PAGE = "https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-total-market"
CACHE_TTL_SECONDS = 24 * 60 * 60
_cache: dict[str, Any] = {"expires_at": 0.0, "stocks": []}


class NiftyUniverseError(Exception):
    """Raised when the official Nifty Total Market constituent file cannot be loaded."""


def _normalise_key(value: str) -> str:
    """Normalise CSV headers so minor NSE formatting changes do not break parsing."""
    return " ".join(str(value).replace("\ufeff", "").strip().lower().split())


def _normalise_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    return symbol if symbol.endswith(".NS") else f"{symbol}.NS" if symbol else ""


def _first(row: dict[str, str], *names: str) -> str:
    wanted = {_normalise_key(name) for name in names}
    for key, value in row.items():
        if _normalise_key(key) in wanted and value is not None:
            value = str(value).strip()
            if value:
                return value
    return ""


def _parse_csv(payload: bytes) -> list[dict[str, str]]:
    # NSE has historically changed encoding/metadata around the actual header.
    # Try UTF-8 first, then UTF-16/Windows-1252 as defensive fallbacks.
    text = None
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            candidate = payload.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
        if "symbol" in candidate[:10000].lower() and "company" in candidate[:10000].lower():
            text = candidate
            break
    if text is None:
        text = payload.decode("utf-8-sig", errors="replace")

    sample = text[:4000]

    # NSE/CDN failures can return HTML or a bot-protection page with HTTP 200.
    # Never turn such a response into an apparently valid empty universe.
    lowered = sample.lower()
    if "<html" in lowered or "<!doctype" in lowered or "<script" in lowered:
        raise NiftyUniverseError(
            "Nifty Total Market endpoint returned HTML instead of the constituent CSV"
        )

    # Normally the first line is the CSV header. Be defensive about leading
    # blank/metadata lines by locating the line containing the required fields.
    lines = text.splitlines()
    header_index = None
    for index, line in enumerate(lines[:50]):
        normalized = _normalise_key(line.replace("\"", ""))
        if "symbol" in normalized and "company name" in normalized:
            header_index = index
            break

    if header_index is not None:
        text = "\n".join(lines[header_index:])

    # Nifty Total Market is an equity constituent file, so do not reject rows
    # based on the optional Series column. NSE has changed the values/format of
    # that column over time, and filtering on it can incorrectly produce zero
    # stocks even when the constituent rows are valid.
    try:
        reader = csv.DictReader(io.StringIO(text))
    except csv.Error as exc:
        raise NiftyUniverseError(f"Unable to parse Nifty Total Market CSV: {exc}") from exc

    if not reader.fieldnames:
        raise NiftyUniverseError("Nifty Total Market CSV has no header")

    headers = [_normalise_key(h) for h in reader.fieldnames if h is not None]
    header_text = ", ".join(headers)

    has_symbol = any(h in {"symbol", "stock symbol", "security symbol"} for h in headers)
    has_name = any(h in {"company name", "companyname", "company"} for h in headers)
    if not has_symbol or not has_name:
        raise NiftyUniverseError(
            "Nifty Total Market CSV has an unexpected header "
            f"(headers received: {header_text})"
        )

    stocks: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in reader:
        if not row:
            continue

        symbol = _normalise_symbol(
            _first(row, "Symbol", "Stock Symbol", "Security Symbol")
        )
        name = _first(row, "Company Name", "CompanyName", "Company")
        sector = _first(
            row,
            "Industry",
            "Industry / Sector",
            "Sector / Industry",
            "Sector",
        )
        isin = _first(row, "ISIN Code", "ISIN", "ISINCODE")

        if not symbol or not name or symbol in seen:
            continue

        seen.add(symbol)
        stocks.append({
            "symbol": symbol,
            "name": name,
            "sector": sector or "Other",
            "isin": isin,
        })

    if not stocks:
        raise NiftyUniverseError(
            "Nifty Total Market CSV contained no usable stocks "
            f"(headers received: {header_text})"
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
        "Referer": NIFTY_TOTAL_MARKET_PAGE,
    })

    try:
        response = session.get(NIFTY_TOTAL_MARKET_CSV, timeout=20)
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
    return sorted({stock["sector"] for stock in load_nifty_total_market()})
