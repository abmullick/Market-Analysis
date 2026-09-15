"""NSE Government-Security master adapter (WDM Securities Available for Trading).

Primary source (official, public):

    https://www.nseindia.com/all-reports-debt

The NSE WDM daily-reports endpoint publishes the current
"WDM-SEC-AVAILABLE-FOR-TRADE" file name and path. This adapter:

    1. retrieves the official WDM report metadata,
    2. locates the CURRENT securities-available-for-trading CSV,
    3. downloads the CSV through normal public HTTP access,
    4. parses it with a header-driven parser into ``NseRawRecord`` rows.

Only fields genuinely present in the CSV are populated; absent fields stay
``None`` per model convention. No values are invented. NSE is used here as a
MASTER-data provider (ISIN + reference fields); it does not duplicate CCIL
market logic.

Failure policy: any failure (metadata unavailable, report missing, download
failure, malformed CSV) yields an empty list so the Bond service layer can
continue with the working CCIL data path. No mock data is returned.

No paid API, no API key, no commercial data vendor, no CAPTCHA or
authentication bypass — legitimate public access only.
"""

from __future__ import annotations

import csv
import io
import re
import time
from threading import Lock
from typing import Any
from urllib.parse import urljoin

import httpx

from backend.config.settings import Settings
from backend.models.bonds import NseRawRecord
from backend.utils.logging import logger


# ---------------------------------------------------------------------------
# NSE official WDM source
# ---------------------------------------------------------------------------

_NSE_BASE = "https://www.nseindia.com"

# Official NSE WDM report metadata endpoint.
WDM_DAILY_REPORTS_URL = f"{_NSE_BASE}/api/daily-reports?key=WDM"

DEBT_MASTER_REPORT_TYPE = "debt-master"

# Browser-like request flow for the public NSE endpoint.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# Security master changes far less frequently than daily market observations:
# cache it in-process for 12h (independent of the Bond-service list TTL).
_MASTER_CACHE_TTL_SECONDS = 12 * 3600
_master_cache_lock = Lock()
_master_cache: dict[str, Any] = {"records": None, "expires": 0.0}


class NseClient:
    """Client for the NSE WDM securities master.

    Flow:
        NSE WDM daily-reports API
            -> current WDM-SEC-AVAILABLE-FOR-TRADE report
            -> CSV download
            -> header-driven parse
            -> NseRawRecord rows

    The module also keeps a 12h in-process master cache so the Bond
    service does not re-download the master for every request.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers=_HEADERS,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def fetch_debt_master(self) -> list[NseRawRecord]:
        """Fetch the NSE WDM securities master (cached 12h, graceful on failure)."""
        cached = _get_cached_master()
        if cached is not None:
            return list(cached)

        records: list[NseRawRecord] = []

        try:
            client = await self._get_client()

            # 1. Load official NSE WDM report metadata.
            reports = await client.get(
                WDM_DAILY_REPORTS_URL,
                headers={**_HEADERS, "Accept": "application/json"},
            )
            reports.raise_for_status()
            report_json = reports.json()

            # 2. Locate the current WDM securities-available-for-trading file.
            csv_url = None

            for report in report_json.get("CurrentDay", []):
                if report.get("fileKey") != "WDM-SEC-AVAILABLE-FOR-TRADE":
                    continue

                file_path = (report.get("filePath") or "").strip()
                file_name = (report.get("fileActlName") or "").strip()

                if file_path and file_name:
                    csv_url = urljoin(file_path, file_name)

                break

            if not csv_url:
                logger.warning(
                    "NSE WDM securities-available-for-trading file not found"
                )
                return []

            # 3. Download the current WDM securities master.
            logger.info("NSE fetch debt-master url=%s", csv_url)

            resp = await client.get(
                csv_url,
                headers={**_HEADERS, "Accept": "text/csv,*/*;q=0.8"},
            )
            resp.raise_for_status()

            records = parse_debt_instruments_csv(resp.text)

        except Exception as exc:
            logger.warning("NSE debt-master fetch failed: %s", exc)
            return []

        _put_cached_master(records)
        return list(records)

    async def fetch_all(self) -> list[NseRawRecord]:
        """Return the NSE security-master records (master-only provider)."""
        try:
            return await self.fetch_debt_master()
        except Exception as exc:
            logger.warning("NSE master fetch failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Master cache
# ---------------------------------------------------------------------------


def _get_cached_master() -> list[NseRawRecord] | None:
    with _master_cache_lock:
        if (
            _master_cache["records"] is not None
            and time.time() < _master_cache["expires"]
        ):
            return list(_master_cache["records"])
        return None


def _put_cached_master(records: list[NseRawRecord]) -> None:
    with _master_cache_lock:
        _master_cache["records"] = list(records)
        _master_cache["expires"] = time.time() + _MASTER_CACHE_TTL_SECONDS


def clear_master_cache() -> None:
    """Reset the in-process NSE master cache."""
    with _master_cache_lock:
        _master_cache["records"] = None
        _master_cache["expires"] = 0.0


# ---------------------------------------------------------------------------
# Header-driven CSV parsing
# ---------------------------------------------------------------------------

_HEADER_ALIASES: dict[str, list[str]] = {
    "isin": [
        "isin",
        "isinno",
        "isincode",
    ],
    "security_description": [
        "securitydescription",
        "securitydesc",
        "securityname",
        "descriptionofsecurity",
        "security",
        "scripname",
        "symbol",
        "nameofsecurity",
        "securitydetails",
    ],
    "issuer": [
        "issuer",
        "issuername",
        "issuerdescription",
        "issuertype",
    ],
    "maturity_date": [
        "maturitydate",
        "maturity",
        "redemptiondate",
        "maturityredemptiondate",
        "dateofmaturity",
        "matdate",
    ],
    "issue_date": [
        "issuedate",
        "dateofissue",
        "allotmentdate",
    ],
    "coupon_rate": [
        "couponrate",
        "coupon",
        "couponpct",
        "couponpercent",
        "interestrate",
        "rateofinterest",
        "couponratepct",
        "issuename",
    ],
    "coupon_frequency": [
        "couponfrequency",
        "frequency",
        "couponfreq",
        "cpnfreq",
    ],
    "face_value": [
        "facevalue",
        "face",
        "parvalue",
        "nominalvalue",
    ],
    "instrument_type": [
        "instrument",
        "instrumenttype",
        "securitytype",
        "typeofsecurity",
        "series",
        "segment",
        "securityseries",
        "sectype",
    ],
    "listing_status": [
        "status",
        "listingstatus",
        "tradingstatus",
        "listing",
    ],
}


def _normalize_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _header_index(headers: list[str], field: str) -> int | None:
    normed = [_normalize_header(h) for h in headers]

    for alias in _HEADER_ALIASES.get(field, []):
        if alias in normed:
            return normed.index(alias)

    return None


def parse_debt_instruments_csv(csv_text: str) -> list[NseRawRecord]:
    """Parse the NSE WDM securities-available-for-trading CSV."""
    records: list[NseRawRecord] = []

    if not csv_text or not csv_text.strip():
        logger.warning("NSE debt-master CSV is empty")
        return records

    text = csv_text.lstrip("\ufeff")

    try:
        reader = csv.reader(io.StringIO(text))
        rows = [
            row
            for row in reader
            if any((cell or "").strip() for cell in row)
        ]
    except Exception as exc:
        logger.warning("NSE debt-master CSV parse failed: %s", exc)
        return []

    if not rows:
        return records

    header_idx: int | None = None

    # The WDM CSV normally has the header on the first row, but retain the
    # existing defensive search across the first few rows.
    for i, row in enumerate(rows[:5]):
        normed = {_normalize_header(cell) for cell in row}

        if (
            "isin" in normed
            or "isinno" in normed
            or "isincode" in normed
        ):
            header_idx = i
            break

    if header_idx is None:
        logger.warning("NSE debt-master CSV headers not recognised")
        return records

    headers = [cell.strip() for cell in rows[header_idx]]
    idx = {
        field: _header_index(headers, field)
        for field in _HEADER_ALIASES
    }

    for row in rows[header_idx + 1 :]:
        rec = _normalize_master_row(row, idx)

        if rec is not None:
            records.append(rec)

    logger.info("NSE parsed debt-master rows=%d", len(records))
    return records


def _normalize_master_row(
    row: list[str],
    idx: dict[str, int | None],
) -> NseRawRecord | None:
    def at(field: str) -> str:
        i = idx.get(field)

        if i is None or i >= len(row):
            return ""

        return _clean(row[i])

    isin = at("isin")
    desc = at("security_description")

    if not desc or len(desc) < 2:
        return None

    if not _looks_like_isin(isin):
        return None

    return NseRawRecord(
        report_type=DEBT_MASTER_REPORT_TYPE,
        security_description=desc,
        isin=isin.upper(),
        maturity_date=at("maturity_date") or None,
        coupon_rate=at("coupon_rate") or None,
        issue_date=at("issue_date") or None,
        coupon_frequency=at("coupon_frequency") or None,
        face_value=at("face_value") or None,
        issuer=at("issuer") or None,
        instrument_type=at("instrument_type") or None,
        listing_status=at("listing_status") or None,
    )


def _looks_like_isin(text: str | None) -> bool:
    """Heuristic: ISINs are 12-character alphanumeric codes."""
    value = _clean(text)

    return bool(
        re.fullmatch(
            r"[A-Z]{2}[A-Z0-9]{9}[0-9]",
            value,
        )
    )


def _clean(text: str | None) -> str:
    """Minimal cell cleanup."""
    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text