"""NSE public debt-report adapter.

NSE publishes several public reports relevant to Government Securities:
  - Approved list of GSEC and TBILL
  - WDM Securities available for trading
  - WDM Security-wise Trades Data
  - WDM Historical Security-wise Price Volume Data
  - Accrued Interest
  - WDM ZCYC (zero-coupon yield curve)

This adapter is used primarily for:
  - security master / reference data
  - secondary-market trade/price validation
  - accrued-interest validation
  - yield-curve / reference data where useful

It does NOT duplicate CCIL logic. The adapter normalizes raw rows into
NseRawRecord objects; the Bond domain layer converts those into the
normalized Bond model.

No paid API, no API key, no commercial data vendor.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from backend.config.settings import Settings
from backend.models.bonds import NseRawRecord
from backend.utils.logging import logger


# ---------------------------------------------------------------------------
# NSE public debt-report endpoints (illustrative / research-based)
# ---------------------------------------------------------------------------

# NSE publishes debt-segment reports under:
#   https://www.nseindia.com/market-data/equities-marketing
# and related WDM / debt-report pages.
#
# The exact URLs and file formats may change without notice. These are
# research-based conceptual endpoints; the adapter is structured so they
# can be updated in one place without touching the rest of the bond layer.
#
# IMPORTANT: These endpoints are NOT called during automated tests.
# Tests use mocked responses instead.

_NSE_BASE = "https://www.nseindia.com"

# Report families (conceptual)
GSEC_APPROVED_LIST_URL = "https://www.nseindia.com/market-data/gsec-approved-list"
TBILL_APPROVED_LIST_URL = "https://www.nseindia.com/market-data/tbill-approved-list"
WDM_TRADES_URL = "https://www.nseindia.com/market-data/wdm-trades"
WDM_HISTORICAL_URL = "https://www.nseindia.com/market-data/wdm-historical"
ACCRUED_INTEREST_URL = "https://www.nseindia.com/market-data/accrued-interest"
WDM_ZCYC_URL = "https://www.nseindia.com/market-data/wdm-zcyw"


class NseClient:
    """Client for NSE public debt-report data."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def fetch_gsec_approved_list(self) -> list[NseRawRecord]:
        """Fetch approved list of GSEC securities."""
        return await self._fetch_report(
            "gsec-list",
            GSEC_APPROVED_LIST_URL,
        )

    async def fetch_tbill_approved_list(self) -> list[NseRawRecord]:
        """Fetch approved list of TBILL securities."""
        return await self._fetch_report(
            "tbill-list",
            TBILL_APPROVED_LIST_URL,
        )

    async def fetch_wdm_trades(self) -> list[NseRawRecord]:
        """Fetch WDM security-wise trades data."""
        return await self._fetch_report(
            "trades",
            WDM_TRADES_URL,
        )

    async def fetch_wdm_historical(self) -> list[NseRawRecord]:
        """Fetch WDM historical security-wise price volume data."""
        return await self._fetch_report(
            "historical",
            WDM_HISTORICAL_URL,
        )

    async def fetch_accrued_interest(self) -> list[NseRawRecord]:
        """Fetch accrued interest report."""
        return await self._fetch_report(
            "accrued-interest",
            ACCRUED_INTEREST_URL,
        )

    async def fetch_zcyc(self) -> list[NseRawRecord]:
        """Fetch WDM zero-coupon yield curve (ZCYC) reference data."""
        return await self._fetch_report(
            "zcyc",
            WDM_ZCYC_URL,
        )

    async def fetch_all(self) -> list[NseRawRecord]:
        """Fetch all NSE debt-report families and return combined raw records."""
        records: list[NseRawRecord] = []
        for fetch in (
            self.fetch_gsec_approved_list,
            self.fetch_tbill_approved_list,
            self.fetch_wdm_trades,
            self.fetch_wdm_historical,
            self.fetch_accrued_interest,
            self.fetch_zcyc,
        ):
            try:
                rows = await fetch()
                records.extend(rows)
            except Exception as exc:
                logger.warning("NSE report fetch failed (%s): %s", fetch.__name__, exc)
        return records

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_report(
        self,
        report_type: str,
        url: str,
    ) -> list[NseRawRecord]:
        """Fetch one NSE report and normalize rows.

        Returns an empty list if the fetch fails, so the bond layer can
        continue with other sources.
        """
        logger.info("NSE fetch report=%s url=%s", report_type, url)
        try:
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()
            text = response.text
        except Exception as exc:
            logger.warning("NSE report=%s fetch failed: %s", report_type, exc)
            return []

        return _parse_nse_report(text, report_type)


# ---------------------------------------------------------------------------
# Parsing helpers (source-specific, internal to this module)
# ---------------------------------------------------------------------------

def _parse_nse_report(html: str, report_type: str) -> list[NseRawRecord]:
    """Parse an NSE debt report page into NseRawRecord rows.

    This is a minimal illustrative parser. Real NSE pages may use HTML
    tables or downloadable CSV/XLS payloads. The parser below demonstrates
    how raw fields map to the internal model; it is designed to be
    replaced / enhanced as the actual report structure is confirmed.
    """
    records: list[NseRawRecord] = []

    text = re.sub(r"[\s\r\n]+", " ", html)

    row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
    cell_pattern = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)

    for match in row_pattern.finditer(text):
        row_html = match.group(1)
        cells = [c.group(1).strip() for c in cell_pattern.finditer(row_html)]
        if not cells:
            continue

        rec = _normalize_nse_row(cells, report_type)
        if rec is not None:
            records.append(rec)

    logger.info("NSE parsed report=%s rows=%d", report_type, len(records))
    return records


def _normalize_nse_row(cells: list[str], report_type: str) -> NseRawRecord | None:
    """Normalize one NSE report row into a NseRawRecord.

    Column layout depends on the report family. The parser uses a
    best-effort mapping: if the row looks like data (has at least a
    security description and something resembling a date or ISIN), it
    is normalized; otherwise it is skipped.
    """
    if not cells:
        return None

    desc = _clean(cells[0]) if len(cells) > 0 else ""
    if not desc or len(desc) < 3:
        return None

    def at(idx: int) -> str:
        return _clean(cells[idx]) if idx < len(cells) else ""

    def try_float(val: str) -> str:
        v = _clean(val)
        if not v:
            return ""
        if re.fullmatch(r"-?\d+(\.\d+)?", v):
            return v
        return ""

    rec = NseRawRecord(
        report_type=report_type,
        security_description=desc,
        isin=at(1) if _looks_like_isin(at(1)) else "",
        maturity_date=at(2) if _looks_like_date(at(2)) else "",
        coupon_rate=try_float(at(3)),
        price=try_float(at(4)),
        yield_pct=try_float(at(5)),
        traded_value=try_float(at(6)),
        traded_quantity=try_float(at(7)),
        trade_date=at(8) if _looks_like_date(at(8)) else "",
        accrued_interest=try_float(at(9)),
        zcyc=try_float(at(10)),
    )
    return rec


def _looks_like_isin(text: str) -> bool:
    """Heuristic: ISINs are 12-character alphanumeric codes."""
    v = _clean(text)
    return bool(re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", v))


def _looks_like_date(text: str) -> bool:
    """Heuristic: resembles a date string."""
    v = _clean(text)
    return bool(re.fullmatch(r"\d{2}-[A-Za-z]{3}-\d{4}", v)) or bool(
        re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)
    )


def _clean(text: str) -> str:
    """Minimal cell cleanup."""
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
