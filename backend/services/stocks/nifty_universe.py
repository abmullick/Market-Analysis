from __future__ import annotations

import csv
import io
import time
from typing import Any

import curl_cffi.requests


# Nifty Total Market is defined as Nifty 500 + Nifty Microcap 250.
# Prefer NSE's published archive files; keep the NSE Indices URLs as a
# fallback because the latter can return HTML/blocked responses depending on
# the network path used by the application server.
NIFTY_TOTAL_MARKET_SOURCES = (
    (
        "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
        "NSE Nifty 500 constituent CSV",
    ),
    (
        "https://nsearchives.nseindia.com/content/indices/ind_niftymicrocap250_list.csv",
        "NSE Nifty Microcap 250 constituent CSV",
    ),
)
NIFTY_TOTAL_MARKET_FALLBACK_SOURCES = (
    "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
    "https://www.niftyindices.com/IndexConstituent/ind_niftymicrocap250_list.csv",
)
NIFTY_TOTAL_MARKET_PAGE = (
    "https://www.niftyindices.com/indices/equity/broad-based-indices/"
    "nifty-total-market"
)
CACHE_TTL_SECONDS = 24 * 60 * 60

_cache: dict[str, Any] = {"expires_at": 0.0, "stocks": []}


class NiftyUniverseError(Exception):
    """Raised when official Nifty constituent data cannot be loaded."""


def _normalise_key(value: str) -> str:
    return " ".join(str(value).replace("\ufeff", "").strip().lower().split())


def _normalise_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not symbol:
        return ""
    return symbol if symbol.endswith(".NS") else f"{symbol}.NS"


def _find_column(fieldnames: list[str], *candidates: str) -> str | None:
    wanted = {_normalise_key(candidate) for candidate in candidates}
    for fieldname in fieldnames:
        if _normalise_key(fieldname) in wanted:
            return fieldname
    return None


def _decode_payload(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            text = payload.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
        if "\x00" not in text:
            return text
    return payload.decode("utf-8-sig", errors="replace")


def _parse_csv(payload: bytes) -> list[dict[str, str]]:
    text = _decode_payload(payload)
    sample = text[:5000].lower()
    if "<html" in sample or "<!doctype" in sample or "<script" in sample:
        raise NiftyUniverseError("Constituent endpoint returned HTML instead of CSV")

    lines = text.splitlines()
    header_index: int | None = None
    for index, line in enumerate(lines[:100]):
        normalized = _normalise_key(line.replace('"', ""))
        if "symbol" in normalized and "company" in normalized:
            header_index = index
            break

    if header_index is not None and header_index > 0:
        text = "\n".join(lines[header_index:])

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise NiftyUniverseError("Constituent data has no CSV header")

    fieldnames = list(reader.fieldnames)
    symbol_col = _find_column(fieldnames, "Symbol", "Stock Symbol", "Security Symbol")
    name_col = _find_column(fieldnames, "Company Name", "CompanyName", "Company")
    industry_col = _find_column(
        fieldnames,
        "Industry",
        "Sector",
        "Industry / Sector",
        "Sector / Industry",
    )
    isin_col = _find_column(fieldnames, "ISIN Code", "ISIN", "ISINCODE")

    if not symbol_col or not name_col:
        raise NiftyUniverseError(
            "Constituent data has an unexpected header: " + ", ".join(fieldnames)
        )

    stocks: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in reader:
        if not row:
            continue
        symbol = _normalise_symbol(str(row.get(symbol_col) or ""))
        name = str(row.get(name_col) or "").strip()
        sector = str(row.get(industry_col) or "").strip() if industry_col else ""
        isin = str(row.get(isin_col) or "").strip() if isin_col else ""
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
            "Constituent CSV contained no usable stocks "
            f"(headers received: {', '.join(fieldnames)})"
        )
    return stocks


def _download(url: str) -> bytes:
    session = curl_cffi.requests.Session(impersonate="chrome")
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/154.0.0.0 Safari/537.36"
        ),
        "Accept": "text/csv,application/CSV,application/octet-stream,text/plain,*/*",
        "Referer": NIFTY_TOTAL_MARKET_PAGE,
    })
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    finally:
        session.close()


def _load_from_sources() -> list[dict[str, str]]:
    errors: list[str] = []

    # First try the two NSE archive files. Together they are the official
    # 750-stock Nifty Total Market universe.
    try:
        combined: list[dict[str, str]] = []
        for url, label in NIFTY_TOTAL_MARKET_SOURCES:
            try:
                combined.extend(_parse_csv(_download(url)))
            except Exception as exc:
                raise NiftyUniverseError(f"{label}: {exc}") from exc

        deduped: dict[str, dict[str, str]] = {item["symbol"]: item for item in combined}
        if deduped:
            return list(deduped.values())
        raise NiftyUniverseError("NSE constituent files produced no stocks")
    except Exception as exc:
        errors.append(str(exc))

    # Fallback: the same two constituent files from NSE Indices.
    try:
        combined = []
        for url in NIFTY_TOTAL_MARKET_FALLBACK_SOURCES:
            combined.extend(_parse_csv(_download(url)))
        deduped = {item["symbol"]: item for item in combined}
        if deduped:
            return list(deduped.values())
        raise NiftyUniverseError("NSE Indices files produced no stocks")
    except Exception as exc:
        errors.append(str(exc))

    raise NiftyUniverseError("Unable to load official Nifty Total Market constituents: " + " | ".join(errors))


def load_nifty_total_market(force_refresh: bool = False) -> list[dict[str, str]]:
    now = time.time()
    if not force_refresh and _cache["stocks"] and now < _cache["expires_at"]:
        return list(_cache["stocks"])

    stocks = _load_from_sources()
    _cache["stocks"] = stocks
    _cache["expires_at"] = now + CACHE_TTL_SECONDS
    return list(stocks)


def nifty_sectors() -> list[str]:
    return sorted({stock["sector"] for stock in load_nifty_total_market()})
