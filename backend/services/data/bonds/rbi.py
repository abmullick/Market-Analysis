"""RBI / DBIE reference adapter.

Use RBI / DBIE for:
  - Government-security reference data
  - T-Bill auction/reference yields
  - Government-security historical validation
  - State Government borrowing/reference information
  - Government-security market reference series

Do NOT use RBI as the primary daily individual-security market-price
source. RBI is reference / validation / history only.

No paid API, no API key, no commercial data vendor.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from backend.config.settings import Settings
from backend.models.bonds import RbiRawRecord
from backend.utils.logging import logger


# ---------------------------------------------------------------------------
# RBI / DBIE reference endpoints (illustrative / research-based)
# ---------------------------------------------------------------------------

# RBI publishes government-securities reference data via DBIE and the
# RBI statistical releases. Conceptual endpoints:
#
#   https://dbie.rbi.org.in/
#   https://www.rbi.org.in/Scripts/quarterly_overview.aspx
#
# The exact URLs and formats may change without notice. These are
# research-based conceptual endpoints; the adapter is structured so
# they can be updated in one place without touching the rest of the
# bond layer.
#
# IMPORTANT: These endpoints are NOT called during automated tests.
# Tests use mocked responses instead.

_RBI_REFERENCES = [
    ("gsec-reference", "https://dbie.rbi.org.in/market/reference/gsec"),
    ("tbill-auction", "https://dbie.rbi.org.in/market/reference/tbill-auction"),
    ("sdl-reference", "https://dbie.rbi.org.in/market/reference/sdl"),
    ("zcyc-reference", "https://dbie.rbi.org.in/market/reference/zcyc"),
    ("state-borrowing", "https://dbie.rbi.org.in/market/reference/state-borrowing"),
]


class RbiClient:
    """Client for RBI / DBIE reference data."""

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

    async def fetch_gsec_reference(self) -> list[RbiRawRecord]:
        return await self._fetch_reference("gsec-reference")

    async def fetch_tbill_auction_reference(self) -> list[RbiRawRecord]:
        return await self._fetch_reference("tbill-auction")

    async def fetch_sdl_reference(self) -> list[RbiRawRecord]:
        return await self._fetch_reference("sdl-reference")

    async def fetch_zcyc_reference(self) -> list[RbiRawRecord]:
        return await self._fetch_reference("zcyc-reference")

    async def fetch_state_borrowing_reference(self) -> list[RbiRawRecord]:
        return await self._fetch_reference("state-borrowing")

    async def fetch_all(self) -> list[RbiRawRecord]:
        """Fetch all RBI reference families and return combined raw records."""
        records: list[RbiRawRecord] = []
        for name, _ in _RBI_REFERENCES:
            try:
                rows = await self._fetch_reference(name)
                records.extend(rows)
            except Exception as exc:
                logger.warning("RBI reference fetch failed (%s): %s", name, exc)
        return records

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_reference(self, series: str) -> list[RbiRawRecord]:
        """Fetch one RBI reference series and normalize rows.

        Returns an empty list if the fetch fails, so the bond layer can
        continue with other sources.
        """
        url = dict(_RBI_REFERENCES).get(series, "")
        logger.info("RBI fetch series=%s url=%s", series, url)
        try:
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()
            text = response.text
        except Exception as exc:
            logger.warning("RBI series=%s fetch failed: %s", series, exc)
            return []

        return _parse_rbi_reference(text, series)


# ---------------------------------------------------------------------------
# Parsing helpers (source-specific, internal to this module)
# ---------------------------------------------------------------------------

def _parse_rbi_reference(html: str, series: str) -> list[RbiRawRecord]:
    """Parse an RBI / DBIE reference page into RbiRawRecord rows.

    This is a minimal illustrative parser. Real RBI pages may use HTML
    tables or downloadable CSV/XLS payloads. The parser below demonstrates
    how raw fields map to the internal model; it is designed to be
    replaced / enhanced as the actual report structure is confirmed.
    """
    records: list[RbiRawRecord] = []

    text = re.sub(r"[\s\r\n]+", " ", html)

    row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
    cell_pattern = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)

    for match in row_pattern.finditer(text):
        row_html = match.group(1)
        cells = [c.group(1).strip() for c in cell_pattern.finditer(row_html)]
        if not cells:
            continue

        rec = _normalize_rbi_row(cells, series)
        if rec is not None:
            records.append(rec)

    logger.info("RBI parsed series=%s rows=%d", series, len(records))
    return records


def _normalize_rbi_row(cells: list[str], series: str) -> RbiRawRecord | None:
    """Normalize one RBI reference row into a RbiRawRecord.

    Column layout depends on the series. The parser uses a best-effort
    mapping: if the row looks like data (has at least a series identifier
    or security description), it is normalized; otherwise it is skipped.
    """
    if not cells:
        return None

    series_val = _clean(cells[0]) if len(cells) > 0 else ""
    desc = _clean(cells[1]) if len(cells) > 1 else ""

    if not series_val and not desc:
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

    rec = RbiRawRecord(
        series=series_val,
        security_description=desc,
        isin=at(2) if _looks_like_isin(at(2)) else "",
        instrument_type=at(3) if at(3) else "",
        maturity_date=at(4) if _looks_like_date(at(4)) else "",
        coupon_rate=try_float(at(5)),
        issue_date=at(6) if _looks_like_date(at(6)) else "",
        auction_yield=try_float(at(7)),
        reference_yield=try_float(at(8)),
        state_borrowing_ref=try_float(at(9)),
        as_of=at(10) if _looks_like_date(at(10)) else "",
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
