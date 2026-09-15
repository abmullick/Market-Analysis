"""CCIL public market data adapter.

CCIL publishes Market Watch pages with separate sections for:
  - Central Government Market Watch
  - State Government Market Watch
  - T-Bills Market Watch

The adapter fetches the published HTML/CSV and normalizes rows into
internal CcilRawRecord objects. It does NOT expose CCIL field names to
the rest of the application.

NOTE: This is an experimental/illustrative adapter. CCIL market-data
pages are human-facing and may change without notice. In production this
would be validated against the actual published structure.

No paid API, no API key, no commercial data vendor.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx

from backend.config.settings import Settings
from backend.models.bonds import CcilRawRecord
from backend.utils.logging import logger


# ---------------------------------------------------------------------------
# CCIL public market-watch endpoints (illustrative / research-based)
# ---------------------------------------------------------------------------

# CCIL publishes market watch pages under the www.ccilindia.com domain.
# The exact URLs and HTML structure may change; these are research-based
# starting points for the Central / State / T-Bills sections.
#
# IMPORTANT: These endpoints are NOT called during automated tests.
# Tests use mocked responses instead.

_CCIL_BASE = "https://www.ccilindia.com"

# These are the conceptual market-watch sections. Actual path/query may
# differ; the adapter is structured so the endpoints can be updated in
# one place without touching the rest of the bond layer.
CENTRAL_MARKET_WATCH_URL = "https://www.ccilindia.com/market/watch/central-government"
STATE_MARKET_WATCH_URL = "https://www.ccilindia.com/market/watch/state-government"
TBILL_MARKET_WATCH_URL = "https://www.ccilindia.com/market/watch/t-bills"


class CcilClient:
    """Client for CCIL public market-watch data.

    Retrieves raw rows and normalizes them into CcilRawRecord objects.
    Parsing is source-specific and stays inside this module.
    """

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

    async def fetch_central_market_watch(self) -> list[CcilRawRecord]:
        """Fetch Central Government Market Watch rows."""
        return await self._fetch_section(
            "central",
            CENTRAL_MARKET_WATCH_URL,
            has_offer_amount=True,
            has_tta=True,
        )

    async def fetch_state_market_watch(self) -> list[CcilRawRecord]:
        """Fetch State Government Market Watch rows."""
        return await self._fetch_section(
            "state",
            STATE_MARKET_WATCH_URL,
            has_offer_amount=True,
            has_tta=True,
        )

    async def fetch_tbill_market_watch(self) -> list[CcilRawRecord]:
        """Fetch T-Bills Market Watch rows."""
        return await self._fetch_section(
            "tbills",
            TBILL_MARKET_WATCH_URL,
            has_offer_amount=False,
            has_tta=True,
        )

    async def fetch_all(self) -> list[CcilRawRecord]:
        """Fetch all three CCIL sections and return combined raw records."""
        records: list[CcilRawRecord] = []
        for fetch in (
            self.fetch_central_market_watch,
            self.fetch_state_market_watch,
            self.fetch_tbill_market_watch,
        ):
            try:
                rows = await fetch()
                records.extend(rows)
            except Exception as exc:
                logger.warning("CCIL section fetch failed (%s): %s", fetch.__name__, exc)
        return records

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_section(
        self,
        section: str,
        url: str,
        has_offer_amount: bool,
        has_tta: bool,
    ) -> list[CcilRawRecord]:
        """Fetch one CCIL market-watch section and normalize rows.

        This is a placeholder for the real parsing logic. The structure
        below documents the expected raw fields and how they map to
        CcilRawRecord.

        In a real deployment this would:
          1. GET the URL
          2. Parse the HTML table / CSV payload
          3. Normalize each row into a CcilRawRecord

        For now we return an empty list and log the attempt, so the
        application can start without external connectivity.
        """
        logger.info("CCIL fetch section=%s url=%s", section, url)
        try:
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()
            text = response.text
        except Exception as exc:
            logger.warning("CCIL section=%s fetch failed: %s", section, exc)
            return []

        return _parse_ccil_section(text, section, has_offer_amount, has_tta)


# ---------------------------------------------------------------------------
# Parsing helpers (source-specific, internal to this module)
# ---------------------------------------------------------------------------

def _parse_ccil_section(
    html: str,
    section: str,
    has_offer_amount: bool,
    has_tta: bool,
) -> list[CcilRawRecord]:
    """Parse CCIL market-watch HTML into CcilRawRecord rows.

    This is a minimal illustrative parser. Real CCIL pages use an HTML
    table; the parser below demonstrates how raw fields map to the
    internal model. It intentionally does NOT guarantee successful
    parsing of live pages — it is designed to be replaced / enhanced
    as the actual page structure is confirmed.

    Central/State published fields:
      Security Description, Maturity Date, Bid Amount, Bid Yield,
      Bid Price, Offer Price, Offer Yield, Offer Amount, LTP, LTY,
      LTA, TTA

    T-Bills published fields:
      Security Description, Maturity Date, Bid Price, Bid Yield,
      Offer Yield, Offer Price, Offer Amount, LTP, LTY, LTA, TTA
    """
    records: list[CcilRawRecord] = []

    # Basic sanitization: collapse whitespace
    text = re.sub(r"[\s\r\n]+", " ", html)

    # Attempt to find table rows. This is illustrative — real selectors
    # depend on the actual CCIL page structure.
    row_pattern = re.compile(
        r"<tr[^>]*>(.*?)</tr>",
        re.IGNORECASE | re.DOTALL,
    )
    cell_pattern = re.compile(
        r"<t[dh][^>]*>(.*?)</t[dh]>",
        re.IGNORECASE | re.DOTALL,
    )

    for match in row_pattern.finditer(text):
        row_html = match.group(1)
        cells = [c.group(1).strip() for c in cell_pattern.finditer(row_html)]
        if not cells:
            continue

        rec = _normalize_ccil_row(cells, section, has_offer_amount, has_tta)
        if rec is not None:
            records.append(rec)

    logger.info(
        "CCIL parsed section=%s rows=%d",
        section,
        len(records),
    )
    return records


def _normalize_ccil_row(
    cells: list[str],
    section: str,
    has_offer_amount: bool,
    has_tta: bool,
) -> CcilRawRecord | None:
    """Normalize one CCIL table row into a CcilRawRecord.

    Expected column layout (illustrative; actual order may differ):

    Central/State:
      0 Security Description
      1 Maturity Date
      2 Bid Amount
      3 Bid Yield
      4 Bid Price
      5 Offer Price
      6 Offer Yield
      7 Offer Amount   (present when has_offer_amount)
      8 LTP
      9 LTY
      10 LTA
      11 TTA          (present when has_tta)

    T-Bills:
      0 Security Description
      1 Maturity Date
      2 Bid Price
      3 Bid Yield
      4 Offer Yield
      5 Offer Price
      6 Offer Amount
      7 LTP
      8 LTY
      9 LTA
      10 TTA
    """
    # Skip header rows that don't look like data
    if not cells:
        return None

    # Heuristic: a data row should have a recognizable maturity date in
    # one of the date-like columns. If we can't find anything resembling
    # a security description + date, skip the row.
    desc = _clean(cells[0]) if len(cells) > 0 else ""
    if not desc or len(desc) < 3:
        return None

    def at(idx: int) -> str:
        return _clean(cells[idx]) if idx < len(cells) else ""

    def try_float(val: str) -> str:
        """Return the raw string if it looks numeric, else empty."""
        v = val.strip()
        if not v:
            return ""
        # Strip common symbols
        v = v.replace("\xa0", " ").strip()
        if re.fullmatch(r"[\d.,\-\+eE%]+ ?, ?[\d.,]+?", v):
            return v
        return ""

    rec = CcilRawRecord(
        section=section,
        security_description=desc,
        maturity_date=at(1),
        bid_amount=try_float(at(2)) if section != "tbills" else "",
        bid_yield=_parse_yield(at(3) if section != "tbills" else at(3)),
        bid_price=_parse_price(at(4) if section != "tbills" else at(2)),
        offer_price=_parse_price(at(5) if section != "tbills" else at(5)),
        offer_yield=_parse_yield(at(6) if section != "tbills" else at(4)),
        offer_amount=try_float(at(7)) if has_offer_amount else "",
        ltp=_parse_price(at(8) if section != "tbills" else at(7)),
        lty=_parse_yield(at(9) if section != "tbills" else at(8)),
        lta=try_float(at(10) if section != "tbills" else at(9)),
        tta=try_float(at(11)) if has_tta else "",
        isin="",
        coupon_rate="",
        security_name=desc,
    )
    return rec


def _clean(text: str) -> str:
    """Minimal cell cleanup: decode entities, collapse spaces."""
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_price(text: str) -> str:
    """Return a price-like string if recognizable, else empty."""
    v = _clean(text)
    if not v:
        return ""
    # Allow values like 98.50, 100, 99.95, etc.
    if re.fullmatch(r"\d+(\.\d+)?", v):
        return v
    return ""


def _parse_yield(text: str) -> str:
    """Return a yield-like string if recognizable, else empty."""
    v = _clean(text)
    if not v:
        return ""
    # Strip trailing %
    v = v.replace("%", "").strip()
    if re.fullmatch(r"-?\d+(\.\d+)?", v):
        return v
    return ""
