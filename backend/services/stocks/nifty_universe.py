from __future__ import annotations

import csv
import io
import time
from typing import Any

import curl_cffi.requests


# NSE publishes the complete Nifty Total Market constituent file directly.
# This is the preferred source because it already contains the combined
# Nifty 500 + Nifty Microcap 250 universe and the current NSE industry
# classification. The two component files are retained only as fallbacks.
NIFTY_TOTAL_MARKET_SOURCES = (
    (
        "https://nsearchives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv",
        "NSE Nifty Total Market constituent CSV",
    ),
    (
        "https://www.niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv",
        "NSE Indices Nifty Total Market constituent CSV",
    ),
)

NIFTY_TOTAL_MARKET_COMPONENT_SOURCES = (
    (
        "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
        "NSE Nifty 500 constituent CSV",
    ),
    (
        "https://nsearchives.nseindia.com/content/indices/ind_niftymicrocap250_list.csv",
        "NSE Nifty Microcap 250 constituent CSV",
    ),
)

NIFTY_TOTAL_MARKET_COMPONENT_FALLBACK_SOURCES = (
    "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
    "https://www.niftyindices.com/IndexConstituent/ind_niftymicrocap250_list.csv",
)

NIFTY_TOTAL_MARKET_PAGE = (
    "https://www.niftyindices.com/indices/equity/broad-based-indices/"
    "nifty-total-market"
)
NSE_INDICES_PAGE = "https://www.nseindia.com/static/products-services/indices-nifty-total-market-index"
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
    if not payload:
        raise NiftyUniverseError("Constituent endpoint returned an empty response")

    text = _decode_payload(payload).lstrip("\ufeff\r\n \t")
    sample = text[:5000].lower()
    if "<html" in sample or "<!doctype" in sample or "<script" in sample:
        raise NiftyUniverseError("Constituent endpoint returned HTML instead of CSV")

    # NSE's CSVs normally start with the header, but tolerate a small amount
    # of metadata before it so a future file-format change does not empty the
    # universe silently.
    lines = text.splitlines()
    header_index: int | None = None
    for index, line in enumerate(lines[:100]):
        normalized = _normalise_key(line.replace('"', ""))
        if "symbol" in normalized and ("company" in normalized or "industry" in normalized):
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
        "Industry / Sector Name",
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

        # NSE has historically used placeholder rows in some constituent
        # files. Do not expose those as selectable stocks.
        if symbol in {".NS", "DUMMYALCAR.NS"}:
            continue
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
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": NIFTY_TOTAL_MARKET_PAGE,
    })
    try:
        # Warming the NSE session is harmless for the archive host and helps
        # when the server is routed through NSE's web protection layer.
        if "nseindia.com" in url:
            try:
                session.get(NSE_INDICES_PAGE, timeout=15)
            except Exception:
                pass

        last_error: Exception | None = None
        for _ in range(2):
            try:
                response = session.get(url, timeout=30)
                response.raise_for_status()
                return response.content
            except Exception as exc:
                last_error = exc
                time.sleep(0.5)
        assert last_error is not None
        raise last_error
    finally:
        session.close()


def _load_direct_total_market() -> list[dict[str, str]]:
    errors: list[str] = []
    for url, label in NIFTY_TOTAL_MARKET_SOURCES:
        try:
            stocks = _parse_csv(_download(url))
            if len(stocks) < 500:
                raise NiftyUniverseError(
                    f"only {len(stocks)} usable stocks were parsed; refusing an incomplete universe"
                )
            return stocks
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    raise NiftyUniverseError(" | ".join(errors))


def _load_from_component_sources() -> list[dict[str, str]]:
    errors: list[str] = []

    # Fallback 1: NSE's official Nifty 500 + Nifty Microcap 250 files.
    try:
        combined: list[dict[str, str]] = []
        for url, label in NIFTY_TOTAL_MARKET_COMPONENT_SOURCES:
            try:
                combined.extend(_parse_csv(_download(url)))
            except Exception as exc:
                raise NiftyUniverseError(f"{label}: {exc}") from exc

        deduped = {item["symbol"]: item for item in combined}
        if len(deduped) >= 500:
            return list(deduped.values())
        raise NiftyUniverseError(f"only {len(deduped)} usable stocks were parsed")
    except Exception as exc:
        errors.append(str(exc))

    # Fallback 2: NSE Indices versions of the same two official files.
    try:
        combined = []
        for url in NIFTY_TOTAL_MARKET_COMPONENT_FALLBACK_SOURCES:
            combined.extend(_parse_csv(_download(url)))
        deduped = {item["symbol"]: item for item in combined}
        if len(deduped) >= 500:
            return list(deduped.values())
        raise NiftyUniverseError(f"only {len(deduped)} usable stocks were parsed")
    except Exception as exc:
        errors.append(str(exc))

    raise NiftyUniverseError(" | ".join(errors))


def _load_from_sources() -> list[dict[str, str]]:
    try:
        return _load_direct_total_market()
    except Exception as direct_error:
        try:
            return _load_from_component_sources()
        except Exception as component_error:
            raise NiftyUniverseError(
                "Unable to load official Nifty Total Market constituents. "
                f"Direct total-market sources failed: {direct_error}. "
                f"Component sources failed: {component_error}"
            ) from component_error


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
