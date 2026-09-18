"""CDSL Corporate Bond Market Data Adapter.

Parses the two real CDSL corporate-bond CSV exports that are already inspected:

    - PrimaryMarketTradeData.csv
        ISIN, Temporary Isin, Issuer Name, Issue Description, Issue Type,
        Issue Size (In Cr.), Issue Price (Rs.), Issue Date, Date of Maturity,
        Coupon Rate (%), Mode of Issuance

    - SecondaryMarketTradeData.csv
        Exchange, Trade Date, ISIN, Listed/Unlisted security, Issuer name,
        Issue Description, Coupon(%), Maturity Date, Credit Rating,
        Number of Trades, Total Trade Value (Rs. Lakhs), Last Traded Price
        (in Rs.), weighted Average price (VWAP), Weighted Average Yield,
        Remark

Public parsing surface is CSV/text/path-based. Live retrieval uses an
isolated Playwright (headless Chromium) transport: the report page is an
ASP.NET WebForms postback driven by client-side JavaScript, so direct HTTP
requests do not reliably return the report. The browser transport drives the
page's own controls (no ``__VIEWSTATE`` reverse engineering, no CAPTCHA
automation). HTML table rows are mapped onto the same raw models and reuse
the same cleaning/date-normalisation conventions as the CSV parsers; the
CSV defect-repair logic is not applied to HTML rows (the rendered table
already has structured cells).

Raw records use the source models defined in ``backend.models.bonds``:

    - CdslCorporateBondPrimaryRawRecord
    - CdslCorporateBondSecondaryRawRecord
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import urllib.parse
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import requests

from bs4 import BeautifulSoup

from backend.config.settings import Settings
from backend.models.bonds import (
    CdslCashFlowEvent,
    CdslCorporateBondPrimaryRawRecord,
    CdslCorporateBondSecondaryRawRecord,
    CdslRatingRecord,
    CdslRichCorporateDetail,
)


log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Parsing exceptions and helpers
# ---------------------------------------------------------------------------


class CdsCorporateBondParseError(Exception):
    """Raised when a CDSL corporate-bond CSV cannot be parsed safely."""


class CdsCorporateBondLiveError(Exception):
    """Raised when a live CDSL report retrieval via the browser fails.

    This is distinct from "the report table genuinely contains no rows"
    (which is signalled by an empty result list). A live error means the
    browser/page interaction itself failed — e.g. the report page could not
    be opened, the search could not be submitted, or the expected result
    table was not present in the rendered document.
    """


# CDSL corporate-bond report page. Live retrieval uses a real Chromium
# browser (Playwright) because direct HTTP requests do not reliably return
# the report: the page is an ASP.NET WebForms postback driven by
# client-side JavaScript.
CDSL_REPORT_URL = "https://www.cdslindia.com/corporatebond/CorporateBondReports.aspx"

# Default timeout for CDSL rich-detail HTTP requests (seconds).
HTTP_TIMEOUT = 30


def _clean(s: Optional[str]) -> Optional[str]:
    """Return trimmed text or ``None`` for blank/None inputs."""
    if s is None:
        return None
    t = s.strip()
    return t or None


# Source sentinel values CDSL uses for "no data" in optional text columns.
_SENTINELS = {"-", "--", "N/A", "NA", "n/a", "nan", "NaN", "NIL", "Nil"}


def _clean_field(s: Optional[str]) -> Optional[str]:
    """Trim and normalize optional textual source fields.

    Blank values and CDSL "no data" sentinels (``-``, ``N/A`` …) become
    ``None``; everything else is preserved verbatim.
    """
    t = _clean(s)
    if t is None:
        return None
    return None if t in _SENTINELS else t


def _num(s: Optional[str]) -> Optional[float]:
    """Parse a numeric string, returning ``None`` for blanks/invalid values."""
    if not s:
        return None
    t = s.strip()
    if not t or t in ("-", "N/A", "NA", "n/a", "NaN", "nan"):
        return None
    try:
        return float(t.replace(",", ""))
    except (TypeError, ValueError):
        return None


def _parse_date(s: Optional[str]) -> Optional[str]:
    """Preserve a DD-Mon-YYYY date string if it looks valid, else ``None``.

    Values are returned as strings so raw records retain source semantics.
    """
    if not s:
        return None
    t = s.strip()
    if not t or t in ("-", "N/A", "NA", "n/a"):
        return None
    import re as _re
    m = _re.match(r"^(\d{1,2})-([A-Za-z]{3})-(\d{4})$", t)
    if not m:
        return None
    day, mon, year = m.groups()
    months = {
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
    }
    try:
        mnum = months[mon.upper()]
        d = int(day)
        y = int(year)
        import calendar as _cal
        if not (1 <= d <= _cal.monthrange(y, mnum)[1]):
            return None
    except (KeyError, ValueError):
        return None
    return t


class _CdslSearchRetryableError(Exception):
    """Internal signal: one CDSL search attempt failed; the caller retries."""


def _verify_report_heading(page: Any, market_type: str, hidden_date: str) -> None:
    """Verify the rendered CDSL report heading matches the requested date.

    The server echoes the effective report date in ``#tradedata`` (e.g.
    ``"Secondary Market Trade Data For 17-Sep-2026"``). Comparison uses
    whitespace/case normalization. A missing or mismatched heading means
    the page does not prove it shows the requested report, so rows must
    not be scraped: raises ``_CdslSearchRetryableError`` for one retry.
    """
    fragment = (
        "Secondary Market Trade Data For"
        if market_type.upper() == "S"
        else "Primary Issuance Data For"
    )
    try:
        region_text = page.locator("#tradedata").inner_text(timeout=15_000) or ""
    except Exception:
        region_text = ""
    if not region_text:
        try:
            region_text = page.locator("body").inner_text(timeout=15_000) or ""
        except Exception:
            region_text = ""
    expected = _normalize_heading_text(f"{fragment} {hidden_date}")
    if not _normalize_heading_text(region_text) or expected not in (
        _normalize_heading_text(region_text)
    ):
        raise _CdslSearchRetryableError(
            f"CDSL report heading did not confirm {hidden_date}; "
            "refusing to scrape unverified rows."
        )


def _normalize_heading_text(raw: Any) -> str:
    """Normalize a CDSL report heading for date comparison.

    Collapses whitespace and lowercases so ``"Secondary Market Trade Data
    For  17-Sep-2026"`` matches ``"secondary market trade data for
    17-sep-2026"``.
    """
    if raw is None:
        return ""
    return re.sub(r"\s+", " ", str(raw)).strip().lower()


def _report_heading_matches_date(heading: Any, hidden_date: str) -> bool:
    """Return True when ``heading`` references ``hidden_date`` (DD-Mon-YYYY)."""
    normalized_heading = _normalize_heading_text(heading)
    normalized_date = _normalize_heading_text(hidden_date)
    return bool(normalized_heading) and normalized_date in normalized_heading


def _cdsl_date_strings(
    trade_date: Union[date, datetime, str],
) -> Tuple[str, str]:
    """Convert ``trade_date`` to the CDSL report page's date strings.

    Returns ``(display_date, hidden_date)``:

        display_date  e.g. ``"September 16, 2026"``  -> ``#idtradedate``
        hidden_date   e.g. ``"16-Sep-2026"``         -> ``#idhdndate``

    Accepts ``datetime.date``, ``datetime.datetime`` or a string in
    ``YYYY-MM-DD``, ``DD-Mon-YYYY`` or ``DD-MM-YYYY`` form.
    """
    if isinstance(trade_date, datetime):
        d: date = trade_date.date()
    elif isinstance(trade_date, date):
        d = trade_date
    else:
        t = str(trade_date).strip()
        parsed: Optional[datetime] = None
        for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y"):
            try:
                parsed = datetime.strptime(t, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            raise ValueError(f"Unrecognised CDSL trade date: {trade_date!r}")
        d = parsed.date()

    display_date = f"{d.strftime('%B')} {d.day}, {d.year}"
    hidden_date = f"{d.day:02d}-{d.strftime('%b')}-{d.year}"
    return display_date, hidden_date

# ---------------------------------------------------------------------------
# Primary CSV parser
# ---------------------------------------------------------------------------

_PRIMARY_HEADER = [
    "ISIN",
    "Temporary Isin",
    "Issuer Name",
    "Issue Description",
    "Issue Type",
    "Issue Size (In Cr.)",
    "Issue Price (Rs.)",
    "Issue Date",
    "Date of Maturity",
    "Coupon Rate (%)",
    "Mode of Issuance",
]


def parse_primary_csv(content: str) -> List[CdslCorporateBondPrimaryRawRecord]:
    """Parse ``PrimaryMarketTradeData.csv`` text and return raw records.

    Blank rows are ignored. Unknown/extra columns are tolerated. Values are
    preserved as source strings.
    """
    if not content:
        return []

    text = content
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")

    reader = csv.reader(io.StringIO(text), skipinitialspace=True)
    rows: List[List[str]] = []
    header: Optional[List[str]] = None

    for raw in reader:
        if not raw:
            continue
        first = _clean(raw[0]) if raw else None
        if first is None:
            continue
        if header is None:
            norm = [c.strip() for c in raw]
            header = norm
            if len(header) < 4:
                raise CdsCorporateBondParseError(
                    "Primary CSV header is too short to parse"
                )
            continue

        rows.append(raw)

    if header is None:
        return []

    idx: Dict[str, int] = {}
    for expected in _PRIMARY_HEADER:
        for pos, name in enumerate(header):
            if name.strip().lower() == expected.lower():
                idx[expected] = pos
                break

    def _col(name: str, default: str = "") -> str:
        pos = idx.get(name)
        if pos is None:
            return default
        try:
            return raw_row[pos] if pos < len(raw_row) else default
        except Exception:
            return default

    out: List[CdslCorporateBondPrimaryRawRecord] = []
    for raw_row in rows:
        if not raw_row:
            continue
        isin = _clean(_col("ISIN"))
        if not isin:
            continue
        temporary_isin = _clean(_col("Temporary Isin"))
        issuer_name = _clean(_col("Issuer Name"))
        issue_description = _clean(_col("Issue Description"))
        issue_type = _clean_field(_col("Issue Type"))
        issue_size_raw = _clean(_col("Issue Size (In Cr.)"))
        issue_price_raw = _clean(_col("Issue Price (Rs.)"))
        issue_date = _parse_date(_clean(_col("Issue Date")))
        maturity_date = _parse_date(_clean(_col("Date of Maturity")))
        coupon_rate_raw = _clean(_col("Coupon Rate (%)"))
        mode_of_issuance = _clean_field(_col("Mode of Issuance"))

        out.append(
            CdslCorporateBondPrimaryRawRecord(
                isin=isin,
                temporary_isin=temporary_isin,
                issuer_name=issuer_name,
                issue_description=issue_description,
                issue_type=issue_type,
                issue_size_raw=issue_size_raw,
                issue_price_raw=issue_price_raw,
                issue_date=issue_date,
                maturity_date=maturity_date,
                coupon_rate_raw=coupon_rate_raw,
                mode_of_issuance=mode_of_issuance,
            )
        )

    return out


def load_primary_from_path(path: str) -> List[CdslCorporateBondPrimaryRawRecord]:
    """Load and parse a local ``PrimaryMarketTradeData.csv`` file."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Primary CSV not found: {path}")
    raw = p.read_text(encoding="utf-8", errors="replace")
    return parse_primary_csv(raw)

# ---------------------------------------------------------------------------
# Secondary CSV parser (with defective-row repair)
# ---------------------------------------------------------------------------

_SECONDARY_HEADER = [
    "Exchange",
    "Trade Date",
    "ISIN",
    "Listed/Unlisted security",
    "Issuer name",
    "Issue Description",
    "Coupon(%)",
    "Maturity Date",
    "Credit Rating",
    "Number of Trades",
    "Total Trade Value (Rs. Lakhs)",
    "Last Traded Price (in Rs.)",
    "weighted Average price (VWAP)",
    "Weighted Average Yield",
    "Remark",
]


def _repair_secondary_row(fields: Sequence[str]) -> Optional[List[str]]:
    """Repair a secondary CSV row that parsed to 16 fields instead of 15.

    The known observed defect is an unquoted thousands-separator comma inside
    ``Total Trade Value (Rs. Lakhs)``. When a row parses to more than 15
    fields, we attempt to collapse the surplus back into the trade-value
    field without shifting LTP / VWAP / Weighted Average Yield / Remark.
    """
    if len(fields) == 15:
        return list(fields)

    if len(fields) < 15:
        return None

    # The trailing columns are always presentation-stable:
    #   [-4] Last Traded Price, [-3] VWAP, [-2] Weighted Average Yield,
    #   [-1] Remark. The trade-value column sits immediately before them, so
    #   any surplus fields to its right (outside the tail) are merged into it.
    total_expected = len(_SECONDARY_HEADER)
    surplus = len(fields) - total_expected
    if surplus <= 0:
        return None

    nv_index = None
    for i, name in enumerate(_SECONDARY_HEADER):
        if name == "Total Trade Value (Rs. Lakhs)":
            nv_index = i
            break

    if nv_index is None:
        return None

    after = list(fields[len(fields) - 4 :])

    merged_value = ",".join([
        _clean(f) or ""
        for f in (fields[nv_index : len(fields) - 4])
    ])

    # Guard: only accept the repair when it is unambiguously a split numeric
    # trade value. This prevents a stray comma elsewhere in the row from
    # silently shifting LTP / VWAP / Weighted Average Yield / Remark.
    if _num(merged_value) is None:
        return None
    if _num(_clean(after[0]) if after else None) is None:
        return None

    repaired: List[str] = []
    for i in range(nv_index):
        repaired.append(fields[i])
    repaired.append(merged_value)
    repaired.extend(after)

    if len(repaired) != total_expected:
        return None

    return repaired


def parse_secondary_csv(content: str) -> List[CdslCorporateBondSecondaryRawRecord]:
    """Parse ``SecondaryMarketTradeData.csv`` text and return raw records.

    Handles the observed defect where ``Total Trade Value (Rs. Lakhs)``
    contains an unquoted comma, producing 16 fields instead of 15.
    """
    if not content:
        return []

    text = content
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")

    reader = csv.reader(io.StringIO(text), skipinitialspace=True)
    rows: List[List[str]] = []
    header: Optional[List[str]] = None

    for raw in reader:
        if not raw:
            continue
        first = _clean(raw[0]) if raw else None
        if first is None:
            continue
        if header is None:
            norm = [c.strip() for c in raw]
            header = norm
            if len(header) < 8:
                raise CdsCorporateBondParseError(
                    "Secondary CSV header is too short to parse"
                )
            continue
        rows.append(list(raw))

    if header is None:
        return []

    idx: Dict[str, int] = {}
    for expected in _SECONDARY_HEADER:
        for pos, name in enumerate(header):
            if name.strip().lower() == expected.lower():
                idx[expected] = pos
                break

    def _col(name: str, default: str = "") -> str:
        pos = idx.get(name)
        if pos is None:
            return default
        try:
            return repaired_row[pos] if pos < len(repaired_row) else default
        except Exception:
            return default

    out: List[CdslCorporateBondSecondaryRawRecord] = []
    for raw_row in rows:
        if not raw_row:
            continue
        repaired = _repair_secondary_row(raw_row)
        if repaired is None:
            log.warning("Dropping malformed secondary CSV row: %s", raw_row)
            continue
        repaired_row = repaired

        isin = _clean(_col("ISIN"))
        if not isin:
            continue

        exchange = _clean_field(_col("Exchange"))
        trade_date = _parse_date(_clean(_col("Trade Date")))
        listed_unlisted = _clean_field(_col("Listed/Unlisted security"))
        issuer_name = _clean_field(_col("Issuer name"))
        issue_description = _clean_field(_col("Issue Description"))
        coupon_rate_raw = _clean_field(_col("Coupon(%)"))
        maturity_date = _parse_date(_clean(_col("Maturity Date")))
        credit_rating_raw = _clean_field(_col("Credit Rating"))
        number_of_trades = _clean(_col("Number of Trades"))
        total_trade_value_raw = _clean(_col("Total Trade Value (Rs. Lakhs)"))
        last_traded_price_raw = _clean(_col("Last Traded Price (in Rs.)"))
        vwap_raw = _clean(_col("weighted Average price (VWAP)"))
        weighted_average_yield_raw = _clean(_col("Weighted Average Yield"))
        remark = _clean_field(_col("Remark"))

        out.append(
            CdslCorporateBondSecondaryRawRecord(
                exchange=exchange,
                trade_date=trade_date,
                isin=isin,
                listed_unlisted=listed_unlisted,
                issuer_name=issuer_name,
                issue_description=issue_description,
                coupon_rate_raw=coupon_rate_raw,
                maturity_date=maturity_date,
                credit_rating_raw=credit_rating_raw,
                number_of_trades=number_of_trades,
                total_trade_value_raw=total_trade_value_raw,
                last_traded_price_raw=last_traded_price_raw,
                vwap_raw=vwap_raw,
                weighted_average_yield_raw=weighted_average_yield_raw,
                remark=remark,
            )
        )

    return out


def load_secondary_from_path(path: str) -> List[CdslCorporateBondSecondaryRawRecord]:
    """Load and parse a local ``SecondaryMarketTradeData.csv`` file."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Secondary CSV not found: {path}")
    raw = p.read_text(encoding="utf-8", errors="replace")
    return parse_secondary_csv(raw)


# ---------------------------------------------------------------------------
# HTML row -> raw record mapping (live browser transport)
# ---------------------------------------------------------------------------

# One extracted table cell: {"text": trimmed cell text,
# "anchor": text of the first <a> inside the cell, or None}.
HtmlCell = Dict[str, Optional[str]]


def _cell(
    cells: Sequence[HtmlCell],
    index: int,
    key: str = "text",
) -> Optional[str]:
    """Return ``cells[index][key]`` or ``None`` when out of range."""
    if index < 0 or index >= len(cells):
        return None
    return cells[index].get(key)


def _isin_from_cell(cells: Sequence[HtmlCell], index: int) -> Optional[str]:
    """Extract the ISIN text from an anchor-bearing CDSL table cell.

    CDSL renders the ISIN as an ``<a>`` element; the anchor text is
    preferred, falling back to the plain cell text.
    """
    return _clean(_cell(cells, index, "anchor") or _cell(cells, index, "text"))


def map_secondary_html_row(
    cells: Sequence[HtmlCell],
) -> Optional[CdslCorporateBondSecondaryRawRecord]:
    """Map one rendered ``table.tblSecDetails`` data row to a raw record.

    Column order (15 columns, matching ``_SECONDARY_HEADER``):
        Exchange, Trade Date, ISIN, Listed/Unlisted security, Issuer name,
        Issue Description, Coupon(%), Maturity Date, Credit Rating,
        Number of Trades, Total Trade Value (Rs. Lakhs), Last Traded Price
        (in Rs.), weighted Average price (VWAP), Weighted Average Yield,
        Remark

    Uses the same cleaning/date conventions as ``parse_secondary_csv``.
    No CSV defect repair is applied: the HTML table already has structured
    cells. Returns ``None`` for rows without a usable ISIN (e.g. header or
    separator rows), mirroring how blank CSV rows are skipped.
    """
    isin = _isin_from_cell(cells, 2)
    if not isin:
        return None

    return CdslCorporateBondSecondaryRawRecord(
        exchange=_clean_field(_cell(cells, 0)),
        trade_date=_parse_date(_clean(_cell(cells, 1))),
        isin=isin,
        listed_unlisted=_clean_field(_cell(cells, 3)),
        issuer_name=_clean_field(_cell(cells, 4)),
        issue_description=_clean_field(_cell(cells, 5)),
        coupon_rate_raw=_clean_field(_cell(cells, 6)),
        maturity_date=_parse_date(_clean(_cell(cells, 7))),
        credit_rating_raw=_clean_field(_cell(cells, 8)),
        number_of_trades=_clean(_cell(cells, 9)),
        total_trade_value_raw=_clean(_cell(cells, 10)),
        last_traded_price_raw=_clean(_cell(cells, 11)),
        vwap_raw=_clean(_cell(cells, 12)),
        weighted_average_yield_raw=_clean(_cell(cells, 13)),
        remark=_clean_field(_cell(cells, 14)),
    )


def map_primary_html_row(
    cells: Sequence[HtmlCell],
) -> Optional[CdslCorporateBondPrimaryRawRecord]:
    """Map one rendered ``table.tblPriDetails`` data row to a raw record.

    Column order (11 columns, matching ``_PRIMARY_HEADER``):
        ISIN, Temporary Isin, Issuer Name, Issue Description, Issue Type,
        Issue Size (In Cr.), Issue Price (Rs.), Issue Date, Date of Maturity,
        Coupon Rate (%), Mode of Issuance

    Uses the same cleaning/date conventions as ``parse_primary_csv``.
    Returns ``None`` for rows without a usable ISIN.
    """
    isin = _isin_from_cell(cells, 0)
    if not isin:
        return None

    return CdslCorporateBondPrimaryRawRecord(
        isin=isin,
        temporary_isin=_clean(_cell(cells, 1)),
        issuer_name=_clean(_cell(cells, 2)),
        issue_description=_clean(_cell(cells, 3)),
        issue_type=_clean_field(_cell(cells, 4)),
        issue_size_raw=_clean(_cell(cells, 5)),
        issue_price_raw=_clean(_cell(cells, 6)),
        issue_date=_parse_date(_clean(_cell(cells, 7))),
        maturity_date=_parse_date(_clean(_cell(cells, 8))),
        coupon_rate_raw=_clean(_cell(cells, 9)),
        mode_of_issuance=_clean_field(_cell(cells, 10)),
    )



class CdsCorporateBondClient:
    """CDSL corporate-bond market-data client.

    Local parsing accepts raw CSV content or local CSV paths and returns raw
    records for later normalization. Live retrieval uses an isolated
    Playwright transport (headless Chromium) that drives the CDSL report
    page's own controls — no live ``__VIEWSTATE`` manipulation and no CAPTCHA
    automation.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._name = "CDSL Corporate Bonds"

    @property
    def name(self) -> str:
        return self._name

    def parse_primary_csv(self, content: str) -> List[CdslCorporateBondPrimaryRawRecord]:
        """Parse ``PrimaryMarketTradeData.csv`` content."""
        return parse_primary_csv(content)

    def parse_secondary_csv(self, content: str) -> List[CdslCorporateBondSecondaryRawRecord]:
        """Parse ``SecondaryMarketTradeData.csv`` content."""
        return parse_secondary_csv(content)

    def load_primary_from_path(self, path: str) -> List[CdslCorporateBondPrimaryRawRecord]:
        """Load primary CSV from a local file path."""
        return load_primary_from_path(path)

    def load_secondary_from_path(self, path: str) -> List[CdslCorporateBondSecondaryRawRecord]:
        """Load secondary CSV from a local file path."""
        return load_secondary_from_path(path)

    # -----------------------------------------------------------------------
    # Live retrieval (Playwright browser transport)
    # -----------------------------------------------------------------------

    def _cdsl_search_rows(
        self,
        trade_date: Union[date, datetime, str],
        market_type: str,
        table_selector: str,
    ) -> List[List[HtmlCell]]:
        """Open the CDSL report page, run the search and extract table rows.

        Shared browser helper for both live report shapes. Uses the sync
        Playwright API with a real headless Chromium browser and drives the
        page's own controls — no manually constructed ASP.NET postback
        payload is ever sent.

        Flow (matches the manually verified browser session):

            1. ``GET`` the report page.
            2. Set ``#idtradedate`` to the display date
               (e.g. ``"September 16, 2026"``) and ``#idhdndate`` to the
               hidden form date (e.g. ``"16-Sep-2026"``), dispatching
               ``input``/``change`` events and verifying both fields.
            3. ``#markettype_select`` = ``market_type`` (``"S"`` secondary,
               ``"P"`` primary) and ``#filter_select`` = ``"A"`` (for all).
               ``#search_text`` is intentionally left untouched because the
               control is hidden for filter ``A``.
            4. Click ``#btnsearch`` and wait for the resulting document.
               A navigation timeout is a retrieval failure: the complete
               search is retried once, and if the retry also fails a
               ``CdsCorporateBondLiveError`` is raised. The stale current
               page is never scraped after a timeout.
            5. Verify the rendered report heading references the requested
               hidden date (e.g. ``"Secondary Market Trade Data For
               17-Sep-2026"``) before scraping any rows. A missing or
               mismatched heading is a retrieval failure retried once.
            6. Extract the data rows of ``table_selector`` from the rendered
               DOM.

        Each returned row is a list of cells of the form
        ``{"text": <trimmed cell text>, "anchor": <first <a> text or None>}``.
        Header rows (leading ``<th>`` cells) are excluded.

        Raises:
            CdsCorporateBondLiveError: when Playwright is unavailable, the
                trade date cannot be interpreted, the page interaction fails,
                or ``table_selector`` is not present in the resulting
                document. A table that is present but genuinely contains no
                data rows is *not* an error — it is returned as an empty
                list.
        """
        try:
            from playwright.sync_api import (
                TimeoutError as PlaywrightTimeoutError,
                sync_playwright,
            )
        except ImportError as exc:
            raise CdsCorporateBondLiveError(
                "Live CDSL retrieval requires Playwright "
                "(pip install playwright && playwright install chromium)"
            ) from exc

        try:
            display_date, hidden_date = _cdsl_date_strings(trade_date)
        except ValueError as exc:
            raise CdsCorporateBondLiveError(str(exc)) from exc

        log.info(
            "CDSL live search: market_type=%s trade_date=%s table=%s",
            market_type,
            display_date,
            table_selector,
        )

        last_error: Optional[CdsCorporateBondLiveError] = None
        for attempt_no in (1, 2):
            try:
                return self._cdsl_search_rows_attempt(
                    trade_date=(display_date, hidden_date),
                    market_type=market_type,
                    table_selector=table_selector,
                    sync_playwright=sync_playwright,
                    PlaywrightTimeoutError=PlaywrightTimeoutError,
                )
            except _CdslSearchRetryableError as exc:
                last_error = CdsCorporateBondLiveError(str(exc))
                log.warning(
                    "CDSL live search attempt %d/2 failed: %s",
                    attempt_no,
                    exc,
                )
        assert last_error is not None  # loop always runs; for type-checkers
        raise last_error

    def _cdsl_search_rows_attempt(  # noqa: C901 - linear page-driving steps
        self,
        trade_date: Tuple[str, str],
        market_type: str,
        table_selector: str,
        sync_playwright: Any,
        PlaywrightTimeoutError: Any,
    ) -> List[List[HtmlCell]]:
        """Run one complete CDSL search attempt; raise retryable on failure."""
        display_date, hidden_date = trade_date
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                page = context.new_page()
                try:
                    page.goto(
                        CDSL_REPORT_URL,
                        wait_until="domcontentloaded",
                        timeout=60_000,
                    )

                    # Trade date: the visible display field plus the hidden
                    # field the page's JavaScript submits with the form.
                    # Dispatch input/change events so datepicker listeners
                    # observe the programmatic fill; both fields are then
                    # verified because the visible field must not be assumed
                    # to update the hidden field automatically.
                    page.locator("#idtradedate").fill(display_date)
                    page.locator("#idtradedate").evaluate(
                        "(el) => {"
                        " el.dispatchEvent(new Event('input', {bubbles: true}));"
                        " el.dispatchEvent(new Event('change', {bubbles: true}));"
                        "}"
                    )
                    page.locator("#idhdndate").evaluate(
                        "(el, value) => {"
                        " el.value = value;"
                        " el.dispatchEvent(new Event('input', {bubbles: true}));"
                        " el.dispatchEvent(new Event('change', {bubbles: true}));"
                        "}",
                        hidden_date,
                    )
                    visible_value = (
                        page.locator("#idtradedate").input_value() or ""
                    ).strip()
                    hidden_value = (
                        page.locator("#idhdndate").evaluate("(el) => el.value || ''")
                        or ""
                    ).strip()
                    if visible_value != display_date or hidden_value != hidden_date:
                        raise _CdslSearchRetryableError(
                            f"CDSL date fields did not accept {hidden_date}: "
                            f"visible={visible_value!r} hidden={hidden_value!r}."
                        )

                    page.locator("#markettype_select").select_option(market_type)
                    page.locator("#filter_select").select_option("A")

                    try:
                        with page.expect_navigation(
                            wait_until="domcontentloaded",
                            timeout=60_000,
                        ):
                            page.locator("#btnsearch").click()
                    except PlaywrightTimeoutError as exc:
                        # A navigation timeout means the requested report may
                        # not have rendered: never scrape the stale current
                        # page. Signal a retry of the complete search.
                        raise _CdslSearchRetryableError(
                            f"CDSL search navigation timed out for "
                            f"{hidden_date}; not scraping the current page."
                        ) from exc

                    _verify_report_heading(page, market_type, hidden_date)

                    table = page.locator(table_selector)

                    # CDSL does not render a table when no data exists.
                    page_text = page.locator("body").inner_text().lower()

                    if "no data is available" in page_text:
                        log.info(
                            "CDSL returned no data: market_type=%s trade_date=%s",
                            market_type,
                            display_date,
                        )
                        return []

                    try:
                        table.wait_for(
                            state="attached",
                            timeout=30_000,
                        )
                    except PlaywrightTimeoutError as exc:
                        raise _CdslSearchRetryableError(
                            "CDSL report table '%s' was not found after "
                            "search (market_type=%r, trade_date=%r): page "
                            "interaction failed"
                            % (
                                table_selector,
                                market_type,
                                display_date,
                            )
                        ) from exc

                    if table.count() == 0:
                        raise _CdslSearchRetryableError(
                            "CDSL report table '%s' was not found after "
                            "search (market_type=%r, trade_date=%r): page "
                            "interaction failed"
                            % (
                                table_selector,
                                market_type,
                                display_date,
                            )
                        )

                    rows: List[List[HtmlCell]] = table.evaluate(
                        """(t) => Array.from(t.rows)
                            .filter(r => r.cells.length
                                && r.cells[0].tagName !== 'TH')
                            .map(r => Array.from(r.cells).map(c => ({
                                text: (c.innerText || '').trim(),
                                anchor: c.querySelector('a')
                                    ? c.querySelector('a').innerText.trim()
                                    : null,
                            })))"""
                    )
                    return rows
                finally:
                    page.close()
                    context.close()
            finally:
                browser.close()

    def fetch_secondary_live(
        self,
        trade_date: Union[date, datetime, str],
    ) -> List[CdslCorporateBondSecondaryRawRecord]:
        """Retrieve the CDSL secondary-market report live for ``trade_date``.

        Searches the report page for Secondary Market (``#markettype_select``
        = ``"S"``) / For all (``#filter_select`` = ``"A"``) and maps the
        rendered ``table.tblSecDetails`` rows onto
        ``CdslCorporateBondSecondaryRawRecord``.

        Returns an empty list when the report table is present but contains
        no data rows; raises ``CdsCorporateBondLiveError`` when the browser
        retrieval or table extraction fails.
        """
        cells_rows = self._cdsl_search_rows(
            trade_date, "S", "table.tblSecDetails"
        )
        out: List[CdslCorporateBondSecondaryRawRecord] = []
        for cells in cells_rows:
            record = map_secondary_html_row(cells)
            if record is not None:
                out.append(record)
        return out

    def fetch_primary_live(
        self,
        trade_date: Union[date, datetime, str],
    ) -> List[CdslCorporateBondPrimaryRawRecord]:
        """Retrieve the CDSL primary-market report live for ``trade_date``.

        Searches the report page for Primary Market (``#markettype_select``
        = ``"P"``) / For all (``#filter_select`` = ``"A"``) and maps the
        rendered ``table.tblPriDetails`` rows onto
        ``CdslCorporateBondPrimaryRawRecord``.

        Returns an empty list when the report table is present but contains
        no data rows; raises ``CdsCorporateBondLiveError`` when the browser
        retrieval or table extraction fails.
        """
        cells_rows = self._cdsl_search_rows(
            trade_date, "P", "table.tblPriDetails"
        )
        out: List[CdslCorporateBondPrimaryRawRecord] = []
        for cells in cells_rows:
            record = map_primary_html_row(cells)
            if record is not None:
                out.append(record)
        return out


# ---------------------------------------------------------------------------
# Rich CDSL ISIN detail (single-bond contract terms + cash-flow schedule)
# ---------------------------------------------------------------------------

_RICH_ISIN_URL = "https://www.cdslindia.com/CorporateBond/CorpBondDatabase.aspx"

_GET_CASHFLOW_SCHEDULE_URL = (
    "https://www.cdslindia.com/CorporateBond/CorpBondDatabase.aspx"
    "/GetCashflowSchedule"
)
_GET_HISTORY_DTLS_URL = (
    "https://www.cdslindia.com/CorporateBond/CorpBondDatabase.aspx"
    "/GetHistorydtls"
)


class CdsRichDetailLiveError(Exception):
    """Raised when the CDSL rich ISIN detail page cannot be retrieved or parsed."""


def _is_blank_or_dash(raw: Optional[str]) -> bool:
    """Return True when *raw* is empty, '-' or 'N/A' (CDSL's no-data sentinel)."""
    if raw is None:
        return True
    t = raw.strip()
    return not t or t in ("-", "N/A", "NA", "n/a")


def _clean_cdsl_text(raw: Optional[str]) -> Optional[str]:
    """Trim and normalise a single CDSL cell / label value.

    The CDSL rich detail page occasionally embeds null bytes and unicode
    replacement characters inside cell text (observed in CRA-name cells).
    These are stripped before returning the cleaned value.

    Returns ``None`` for blank / dash / N/A values.
    """
    if _is_blank_or_dash(raw):
        return None
    t = raw.strip()
    t = t.replace("\x00", "").replace("\ufffd", "").strip()
    if not t or t in ("-", "N/A", "NA", "n/a"):
        return None
    return t


    return t




def _cdsl_table_value_cell(row) -> Optional[str]:
    """Return the trimmed text of the value cell in a label/value row.

    A CDSL label/value row has three cells::

        <tr>
          <td style="width:18%"><label class="lbl">LABEL</label></td>
          <td style="width:2%">:</td>
          <td style="width:30%"><span id="lblXXX" class="dataFont">VALUE</span></td>
        </tr>

    The value cell is the ``<td>`` that contains a ``span.dataFont`` element. If
    that span is empty or whitespace-only, the value is ``None``. If no
    ``span.dataFont`` is found, falls back to the last cell that has non-trivial
    text and is not the label cell.
    """
    cells = row.find_all("td")
    if not cells:
        return None

    # Locate the value td by presence of a span.dataFont (may be empty).
    value_td = None
    for td in cells:
        if td.find("span", class_=lambda c: (c or "") == "dataFont"):
            value_td = td
            break

    if value_td is not None:
        txt = value_td.get_text(strip=True)
        return txt if txt else None

    # Fallback: last non-trivial cell that is not the label cell.
    # The label cell is the first td containing a <label class="lbl"> or
    # a span.lbl.
    label_el = row.find("label", class_=lambda c: (c or "") == "lbl")
    if label_el is None:
        label_el = row.find("span", class_=lambda c: (c or "") == "lbl")
    label_td = label_el.find_parent("td") if label_el else None

    for td in reversed(cells):
        if td is label_td:
            continue
        txt = td.get_text(strip=True)
        if txt and txt not in (":",):
            return txt

    return None


def _cdsl_label_value_pairs(soup_or_div, table_selector=None) -> Dict[str, Optional[str]]:
    """Extract {label: value} from a CDSL label/value table.

    When *table_selector* is given the first matching table is used; otherwise
    the first label/value table under *soup_or_div* is used.
    """
    from bs4 import Tag

    container = soup_or_div
    if isinstance(container, str):
        container = BeautifulSoup(container, "lxml")
    tbl = None
    if table_selector:
        tbl = container.find("table", attrs={"id": table_selector})
    if tbl is None:
        tbl = container.find("table", attrs={"cellpadding": "5", "cellspacing": "10"})
    if tbl is None:
        return {}

    out: Dict[str, Optional[str]] = {}
    for row in tbl.find_all("tr"):
        label_el = row.find("label", class_=lambda c: c == "lbl" if c else False)
        if label_el is None:
            continue
        label = _clean_cdsl_text(label_el.get_text()) or label_el.get_text(strip=True).rstrip(":")
        value = _cdsl_table_value_cell(row)
        if label:
            out[label] = value
    return out


def _cdsl_grid_table(
    soup: BeautifulSoup,
    table_id: Optional[str] = None,
    table_attrs: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Optional[str]]]:
    """Extract rows from a CDSL grid table (``grd*`` ASP.NET generated tables).

    Returns a list of row dicts keyed by header text. Header detection prefers
    the first ``<tr>`` whose cells are ``<th>``; otherwise column positions are
    numbered (0-based).
    """
    tbl = None
    if table_id:
        tbl = soup.find("table", attrs={"id": table_id})
    if tbl is None and table_attrs:
        tbl = soup.find("table", attrs=table_attrs)
    if tbl is None:
        return []

    header_cells = tbl.find_all("th")
    headers: List[Optional[str]] = []
    if header_cells:
        headers = [th.get_text(strip=True) or None for th in header_cells]
    else:
        first_row = tbl.find("tr")
        if first_row:
            headers = [str(i) for i in range(len(first_row.find_all(["td", "th"])))]
        else:
            return []

    rows: List[Dict[str, Optional[str]]] = []
    for tr in tbl.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        if all(c.name == "th" for c in cells) and headers and any(
            h is not None for h in headers
        ):
            continue
        row: Dict[str, Optional[str]] = {}
        for i, cell in enumerate(cells):
            if i >= len(headers):
                break
            header = headers[i]
            if header is None:
                continue
            row[header] = cell.get_text(strip=True) or None
        if row:
            rows.append(row)
    return rows


def _cdsl_numeric(
    raw: Optional[str], default: Optional[float] = None
) -> Optional[float]:
    """Coerce a CDSL numeric string to float, returning ``default`` for blanks.

    CDSL numbers may contain thousands separators (``10,00,000.00``) and may
    use ``-`` / ``N/A`` as no-value sentinels.
    """
    if raw is None:
        return default
    t = raw.strip()
    if not t or t in ("-", "N/A", "NA", "n/a", "NaN", "nan"):
        return default
    try:
        return float(t.replace(",", "").replace("_", ""))
    except (TypeError, ValueError):
        return default


def _cdsl_date_or_none(raw: Optional[str]) -> Optional[str]:
    """Preserve a CDSL date string when it looks like a date, else ``None``.

    Accepts ``DD-Mon-YYYY`` (e.g. ``12-Nov-2021``) and ``DD/MM/YYYY``
    (e.g. ``26/10/2024``).
    """
    if raw is None:
        return None
    t = raw.strip()
    if not t or t in ("-", "N/A", "NA", "n/a"):
        return None
    import re as _re

    if _re.match(r"^\d{1,2}-[A-Za-z]{3}-\d{4}$", t):
        return t
    if _re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", t):
        return t
    return None


def _parse_cdsl_date(raw: Optional[str]) -> Optional[date]:
    """Parse a CDSL date string into a Python ``date`` when possible.

    Accepts ``DD-Mon-YYYY`` and ``DD/MM/YYYY``. Returns ``None`` for blanks,
    non-date strings, or invalid dates.
    """
    s = _cdsl_date_or_none(raw)
    if s is None:
        return None
    import re as _re

    m = _re.match(r"^(\d{1,2})-([A-Za-z]{3})-(\d{4})$", s)
    if m:
        day, mon, year = m.groups()
        months = {
            "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
            "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
        }
        try:
            mnum = months[mon.upper()]
            d = int(day)
            y = int(year)
            import calendar as _cal
            if not (1 <= d <= _cal.monthrange(y, mnum)[1]):
                return None
            return date(y, mnum, d)
        except (KeyError, ValueError):
            return None

    m = _re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        day, mon, year = m.groups()
        try:
            d = int(day)
            mnum = int(mon)
            y = int(year)
            import calendar as _cal
            if not (1 <= d <= _cal.monthrange(y, mnum)[1]):
                return None
            return date(y, mnum, d)
        except (ValueError, OverflowError):
            return None

    return None



def _fetch_rich_page_html(isin: str, session: requests.Session) -> str:
    """GET the CDSL rich ISIN detail page HTML.

    Raises ``CdsRichDetailLiveError`` on transport failure or non-2xx response.
    The ISIN is safely URL-encoded.
    """
    encoded = urllib.parse.quote(isin, safe="")
    url = f"{_RICH_ISIN_URL}?ISIN={encoded}"
    log.info("CDSL rich detail: GET %s", url)
    resp = session.get(url, timeout=HTTP_TIMEOUT)
    if not resp.ok:
        raise CdsRichDetailLiveError(
            "CDSL rich detail returned HTTP %d for %s"
            % (resp.status_code, isin)
        )
    return resp.text


def _post_cdsl_page_method(
    session: requests.Session,
    url: str,
    isin: str,
) -> Any:
    """POST to a CDSL ASP.NET page-method endpoint and return the decoded ``d`` payload."""
    payload = json.dumps({"isin": isin})
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/plain, */*",
    }
    log.info("CDSL page-method POST: %s (isin=%s)", url, isin)
    resp = session.get(
        url,
        headers=headers,
        data=payload.encode("utf-8"),
        timeout=HTTP_TIMEOUT,
    )
    if not resp.ok:
        log.warning(
            "CDSL page-method returned HTTP %d for %s (url=%s)",
            resp.status_code, isin, url,
        )
        return None
    try:
        data = resp.json()
    except (ValueError, Exception):
        return None
    return data.get("d") if isinstance(data, dict) else None



def _find_section_div(
    soup: Any,
    section_id: Optional[str] = None,
    heading_text: Optional[str] = None,
) -> Optional[Any]:
    """Locate a CDSL section container by *section_id* or by a heading.

    * If *section_id* is given, returns ``soup.find("div", id=section_id)``.
    * If *heading_text* is given, searches for an ``<h4>`` whose stripped text
      contains *heading_text*, then returns the next sibling ``<div>`` (the
      label/value table container). This handles sections inside accordion
      containers such as "Interest Payment Details" and "Payment Status".
    * If both are given, *heading_text* is tried first inside the found div.
    """
    if heading_text:
        h = soup.find("h4", string=lambda t: t and heading_text.lower() in t.lower())
        if h is not None:
            sibling = h.find_next_sibling("div", recursive=False)
            if sibling is not None:
                return sibling
        # Fallback: look inside accordion containers
        for acc in soup.find_all("div", id=lambda i: i and i.startswith("accordion")):
            h2 = acc.find("h4", string=lambda t: t and heading_text.lower() in t.lower())
            if h2 is not None:
                sib = h2.find_next_sibling("div", recursive=False)
                if sib is not None:
                    return sib
    if section_id:
        return soup.find("div", id=section_id)
    return None


def _parse_label_value_div(
    soup: Any,
    section_id: Optional[str] = None,
    heading_text: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Extract label → value map from a CDSL label/value table.

    The table is located by *section_id* (a ``<div id="...">``) or by
    *heading_text* (an ``<h4>`` followed by a ``<div>`` table container).

    Each row is expected to be::

        <tr>
          <td style="width:18%"><label class="lbl">LABEL</label></td>
          <td style="width:2%">:</td>
          <td style="width:30%"><span id="lblXXX" class="dataFont">VALUE</span></td>
        </tr>

    WHERE the value may also be a plain text node or a nested element. Blank
    / ``-`` / ``N/A`` values are returned as ``None``.
    """
    container = _find_section_div(soup, section_id=section_id, heading_text=heading_text)
    if container is None:
        return {}
    out: Dict[str, Optional[str]] = {}
    for row in container.find_all("tr"):
        label_el = row.find("label", class_=lambda c: (c or "") == "lbl")
        if label_el is None:
            label_el = row.find("span", class_=lambda c: (c or "") == "lbl")
        if label_el is None:
            # Some rows use a plain-text label before the colon in the first td.
            cells = row.find_all("td")
            if cells:
                first_text = cells[0].get_text(strip=True).rstrip(":")
                if first_text and ":" in first_text:
                    label_el = cells[0]
        if label_el is None:
            continue
        label = _clean_cdsl_text(label_el.get_text())
        if not label:
            continue
        # The value is in the last td that contains a span.dataFont or plain text
        value = _cdsl_table_value_cell(row)
        if value is not None:
            out[label] = value
    return out


def _parse_rich_page_html(
    isin: str,
    html: str,
) -> CdslRichCorporateDetail:
    """Parse the CDSL rich ISIN detail page HTML into a ``CdslRichCorporateDetail``.

    Extraction strategy (structural, section-by-section):

    * Label/value ``<table>``s inside each tab ``<div id="...">`` — one dict
      per section, sourced from ``<label class="lbl">`` rows.
    * Grid tables (``grdRatingDtls``, ``grdRecordDateDtls``, ``grdExchDtls``)
      — rows with header-based column keys.
    * The **Payment Status** block — a set of label/value pairs under the
      ``Details of interest Payments`` / ``Details of Redemption Payments``
      labels.
    * The **Cashflow Schedule** — the static HTML tbody is usually empty; the
      authoritative schedule comes from the ``GetCashflowSchedule`` page-method
      JSON. That method is called separately by the caller (via
      ``_fetch_cashflow_schedule``) and merged in after parsing.

    Blank / ``"-"`` / ``"N/A"`` values are preserved as ``None``.
    """
    soup = BeautifulSoup(html, "lxml")

    detail = CdslRichCorporateDetail(isin=isin)

    # --- Issuer Details ---
    issuer = _parse_label_value_div(soup, "Issuer")
    detail.issuer_name = issuer.get("Issuer Name")
    detail.issuer_address = issuer.get("Address of the Issuer")
    detail.issuer_former_names = issuer.get("Issuer Former Names")
    detail.cin = issuer.get("CIN")
    detail.lei = issuer.get("LEI")
    detail.type_of_issuer = issuer.get("Type of Issuer")
    detail.nature_of_issuer = issuer.get("Nature of Issuer")
    detail.business_sector = issuer.get("Business Sector")

    # --- Instrument Details ---
    instrument = _parse_label_value_div(soup, "Instrument")
    detail.security_description = instrument.get("Instrument Description")
    detail.isin_short_description = instrument.get("ISIN Short Description")
    detail.instrument_type = instrument.get("Type of Instrument")
    detail.secured_or_unsecured = instrument.get("Whether Secured or Unsecured")
    detail.guaranteed_or_partially_guaranteed = instrument.get(
        "Whether Guaranteed or Partially Guaranteed"
    )
    detail.convertibility = instrument.get("Type of Convertibility")
    detail.seniority_in_payment = instrument.get("Seniority In Payment")
    detail.tax_free = instrument.get("Whether Tax Free")
    detail.series = instrument.get("Series")
    detail.tranche_no = instrument.get("Tranche No.")
    detail.infrastructure_category = instrument.get("Infrastructure Category")
    detail.face_value = instrument.get("Face Value/Security")
    detail.tenure = instrument.get("Tenure")
    detail.defaulted_in_redemption = instrument.get("ISIN Defaulted in Redemption")
    detail.principal_protected = instrument.get("Principal Protected")
    detail.is_tokenized = instrument.get("Is Tokenized")

    # --- Redemption Details ---
    redemption = _parse_label_value_div(soup, "Redemption")
    detail.redemption_type = redemption.get("Redemption Type")
    detail.redemption_date = redemption.get("Redemption Date")
    detail.redemption_premium_details = redemption.get("Redemption Premium Details")
    detail.total_quantity_redeemed = redemption.get("Total Quantity Redeemed")
    detail.total_value_redeemed = redemption.get("Total Value Redeemed")
    detail.net_quantity = redemption.get("Net Quantity")
    detail.maturity_type = redemption.get("Maturity Type")

    # --- Issue Details (inside accordion1, following h4 heading) ---
    issue = _parse_label_value_div(
        soup,
        heading_text="Issue Details",
    )
    detail.issue_type_label = issue.get("Issue Type")
    detail.put_option = issue.get("Put Option")
    detail.put_option_dates = issue.get("Put Option Dates")
    detail.call_option = issue.get("Call Option")
    detail.call_option_dates = issue.get("Call Option Dates")
    detail.rating_status = issue.get("Rating Status")
    detail.mode_of_issue = issue.get("Mode of Issue")
    detail.ebp_non_ebp = issue.get("EBP / Non EBP")
    detail.schedule_opening_date = issue.get("Schedule Opening Date")
    detail.schedule_closing_date = issue.get("Schedule Closing Date")
    detail.actual_closing_date = issue.get("Actual Closing Date")
    detail.arranger_to_issue = issue.get("Arranger to Issue")
    detail.lead_manager_to_issue = issue.get("Lead Manager To Issue")
    detail.registrar_to_issue = issue.get("Registrar To Issue")
    detail.debenture_trustee_to_issue = issue.get("Debenture Trustee To Issue")
    detail.date_of_allotment = issue.get("Date of Allotement")
    detail.debentures_bonds_nature_perpetual = issue.get(
        "Debentures/Bonds Nature Perpetual?"
    )
    detail.total_allotment_quantity = issue.get("Total Allotement Quantity")
    detail.issue_price = issue.get("Issue Price")
    detail.issue_size_including_green_shoe = issue.get(
        "Issue Size including Green Shoe Option, if applicable:"
    )
    detail.green_shoe_option = issue.get("Green Shoe Option")
    detail.amount_raised = issue.get(
        "Amount Raised (Total allotment Quantity * issue price):"
    )

    # --- Interest Payment Details (inside accordion1, following h4 heading) ---
    interest = _parse_label_value_div(
        soup,
        heading_text="Interest Payment Details",
    )
    detail.coupon_basis = interest.get("Coupon Basis")
    detail.coupon_rate_label = interest.get("Coupon Rate")
    detail.coupon_type = interest.get("Coupon Type")
    detail.step_up_down_coupon_basis = interest.get("Step Up/Down Coupon Basis")
    detail.coupon_reset_value = interest.get("Coupon Reset Value")
    detail.coupon_reset_date = interest.get("Coupon Reset Date")
    detail.day_count_convention = interest.get("Day Count Convention")
    detail.frequency_of_interest_payment = interest.get("Frequency Of Interest Payment")
    detail.interest_payment_start_date = interest.get("Interest Payment Start Date")
    detail.interest_payment_end_date = interest.get("Interest Payment End Date")

    # --- Agency Details: rating grid + debenture trustee ---
    agency_div = soup.find("div", id="Agency")
    if agency_div:
        rating_grid = _cdsl_grid_table(agency_div, table_id="grdRatingDtls")
        detail.rating_records = [
            CdslRatingRecord(
                cra_name=_clean_cdsl_text(r.get("CRA Name")),
                credit_rating=_clean_cdsl_text(r.get("Credit Rating")),
                rating_outlook=_clean_cdsl_text(r.get("Rating Outlook")),
                credit_rating_date=_cdsl_date_or_none(r.get("Credit Rating date")),
                record_status=_clean_cdsl_text(r.get("Record Status")),
                verification_date=_cdsl_date_or_none(r.get("Verification Date")),
            )
            for r in rating_grid
            if _clean_cdsl_text(r.get("CRA Name")) or _clean_cdsl_text(r.get("Credit Rating"))
        ]

        # Debenture trustee from agency section label/value rows
        for row in agency_div.find_all("tr") if agency_div else []:
            label_el = row.find("label", class_=lambda c: c == "lbl" if c else False)
            if label_el is None:
                continue
            label = _clean_cdsl_text(label_el.get_text()) or label_el.get_text(strip=True).rstrip(":")
            if label == "Debenture Trustee Name":
                value = _cdsl_table_value_cell(row)
                if value:
                    detail.debenture_trustee_to_issue = value

    # --- Cashflow Schedule (static HTML tbody, usually empty) ---
    cashflow_div = soup.find("div", id="Cashflow")
    if cashflow_div:
        cashflow_grid = _cdsl_grid_table(
            cashflow_div,
            table_id="grdCashflow",
            table_attrs={"class": "grd", "cellpadding": "4", "cellspacing": "2"},
        )
        for r in cashflow_grid:
            if _clean_cdsl_text(r.get("Event Type")) or _clean_cdsl_text(r.get("ISIN")):
                detail.cash_flow_schedule.append(
                    CdslCashFlowEvent(
                        event_type=_clean_cdsl_text(r.get("Event Type")),
                        redemption_method=_clean_cdsl_text(r.get("Redemption Method")),
                        quantity_redeemed=_clean_cdsl_text(r.get("Quantity Redeemed")),
                        redemption_premium=_clean_cdsl_text(r.get("Redemption Premium")),
                        net_face_value=_clean_cdsl_text(r.get("Net Face Value")),
                        record_date=_clean_cdsl_text(r.get("Record Date")),
                        due_date=_clean_cdsl_text(r.get("Due Date")),
                        amount_payable=_clean_cdsl_text(r.get("Amount Payable")),
                        payment_date=_clean_cdsl_text(r.get("Date of Payment")),
                    )
                )

    # --- Exchange Details (inside accordion2, following h4 heading) ---
    exchange_div = _find_section_div(
        soup,
        heading_text="Exchange Details",
    )
    if exchange_div:
        exch_grid = _cdsl_grid_table(exchange_div, table_id="grdExchDtls")
        if exch_grid:
            row = exch_grid[0]
            detail.exchange_name = _clean_cdsl_text(row.get("Exchange Name"))
            detail.exchange_listing_status = _clean_cdsl_text(row.get("Listing Status"))
            detail.exchange_listing_date = _cdsl_date_or_none(row.get("Listing Date"))

    # --- Payment Status (Details of interest Payments / Details of Redemption Payments) ---
    payment_labels: Dict[str, Optional[str]] = {}
    pstatus_div = _find_section_div(
        soup,
        heading_text="Payment Status",
    )
    if pstatus_div:
        for row in pstatus_div.find_all("tr"):
            label_el = row.find("label", class_=lambda c: (c or "") == "lbl")
            if label_el is None:
                label_el = row.find("span", class_=lambda c: (c or "") == "lbl")
            if label_el is None:
                # Fallback: first td may contain a plain-text label before colon
                cells = row.find_all("td")
                if cells:
                    first_text = cells[0].get_text(strip=True).rstrip(":")
                    if first_text:
                        label_el = cells[0]
            if label_el is None:
                continue
            label = _clean_cdsl_text(label_el.get_text())
            if not label:
                continue
            value = _cdsl_table_value_cell(row)
            if value is not None:
                payment_labels[label] = value

        detail.interest_payment_record_date = payment_labels.get("Interest Payment Record Date")
        detail.interest_due_date = payment_labels.get("Due date for Interest Payment")
        detail.interest_actual_payment_date = payment_labels.get("Actual Date for Interest Payment")
        detail.interest_amount_paid = payment_labels.get("Amount of interest paid")

        detail.redemption_type_status = payment_labels.get("Type of Redemption")
        detail.partial_redemption = payment_labels.get("Partial Redemption")
        detail.redemption_reason = payment_labels.get("Reason for redemption")
        detail.redemption_date_due_to_put = payment_labels.get("Redemption Date due to PUT option")
        detail.redemption_date_due_to_call = payment_labels.get("Redemption Date due to CALL option")
        detail.quantity_redeemed_status = payment_labels.get("Quantity Redeemed")
        detail.redemption_due_date = payment_labels.get("Due date for Redemption/ Maturity")
        detail.redemption_actual_date = payment_labels.get("Actual Date for Redemption")
        detail.amount_redeemed_status = payment_labels.get("Amount Redeemed")
        detail.outstanding_amount_status = payment_labels.get("Outstanding Amount (Rs.)")

        for key in ("Date of last Interest Payment", "Date Of Last Interest Payment"):
            if payment_labels.get(key):
                detail.redemption_last_interest_payment_date = payment_labels[key]
                break

        detail.interest_non_payment_reason = payment_labels.get(
            "Reason for non-payment/ delay in payment"
        )

    # --- Record date grid (grdRecordDateDtls) ---
    record_grid = _cdsl_grid_table(soup, table_id="grdRecordDateDtls")
    detail.record_date_rows = [
        {k: _clean_cdsl_text(v) for k, v in row.items()}
        for row in record_grid
        if _clean_cdsl_text(row.get("Sr. No.")) or _clean_cdsl_text(row.get("ISIN"))
    ]

    # --- Source ---
    detail.source = "CDSL"
    detail.retrieved_at = datetime.utcnow()

    return detail


def _merge_cashflow_schedule_from_page_method(
    detail: CdslRichCorporateDetail,
    schedule: Any,
) -> None:
    """Merge a ``GetCashflowSchedule`` JSON payload into *detail.cash_flow_schedule*.

    CDSL returns either a list of row objects or a list of lists.
    """
    if not schedule or not isinstance(schedule, list):
        return
    for row in schedule:
        if isinstance(row, dict):
            ev = CdslCashFlowEvent(
                event_type=_clean_cdsl_text(row.get("EventType"))
                or _clean_cdsl_text(row.get("Event Type")),
                redemption_method=_clean_cdsl_text(row.get("RedemptionMethod"))
                or _clean_cdsl_text(row.get("Redemption Method")),
                quantity_redeemed=_clean_cdsl_text(row.get("QuantityRedeemed"))
                or _clean_cdsl_text(row.get("Quantity Redeemed")),
                redemption_premium=_clean_cdsl_text(row.get("RedemptionPremium"))
                or _clean_cdsl_text(row.get("Redemption Premium")),
                net_face_value=_clean_cdsl_text(row.get("NetFaceValue"))
                or _clean_cdsl_text(row.get("Net Face Value")),
                record_date=_clean_cdsl_text(row.get("RecordDate"))
                or _clean_cdsl_text(row.get("Record Date")),
                due_date=_clean_cdsl_text(row.get("DueDate"))
                or _clean_cdsl_text(row.get("Due Date")),
                amount_payable=_clean_cdsl_text(row.get("AmountPayable"))
                or _clean_cdsl_text(row.get("Amount Payable")),
                payment_date=_clean_cdsl_text(row.get("DateOfPayment"))
                or _clean_cdsl_text(row.get("Date of Payment"))
                or _clean_cdsl_text(row.get("Payment Date")),
            )
        elif isinstance(row, (list, tuple)):
            ev = CdslCashFlowEvent(
                event_type=_clean_cdsl_text(row[0]) if len(row) > 0 else None,
                redemption_method=_clean_cdsl_text(row[1]) if len(row) > 1 else None,
                quantity_redeemed=_clean_cdsl_text(row[2]) if len(row) > 2 else None,
                redemption_premium=_clean_cdsl_text(row[3]) if len(row) > 3 else None,
                net_face_value=_clean_cdsl_text(row[4]) if len(row) > 4 else None,
                record_date=_clean_cdsl_text(row[5]) if len(row) > 5 else None,
                due_date=_clean_cdsl_text(row[6]) if len(row) > 6 else None,
                amount_payable=_clean_cdsl_text(row[7]) if len(row) > 7 else None,
                payment_date=_clean_cdsl_text(row[8]) if len(row) > 8 else None,
            )
        else:
            continue
        if ev.event_type or ev.amount_payable or ev.due_date:
            detail.cash_flow_schedule.append(ev)


def _merge_history_from_page_method(
    detail: CdslRichCorporateDetail,
    history: Any,
) -> None:
    """Merge a ``GetHistorydtls`` payload into *detail.record_date_rows*."""
    if not history or not isinstance(history, list):
        return
    for row in history[:200]:
        if isinstance(row, dict):
            detail.record_date_rows.append(
                {k: _clean_cdsl_text(v) for k, v in row.items()}
            )
        elif isinstance(row, (list, tuple)):
            detail.record_date_rows.append(
                {str(i): _clean_cdsl_text(v) for i, v in enumerate(row)}
            )


def fetch_detail_live(
    isin: str,
    session: Optional[requests.Session] = None,
) -> CdslRichCorporateDetail:
    """Retrieve and parse the CDSL rich ISIN detail page for a single *isin*.

    This is the synchronous, non-Playwright path for enriching one corporate
    bond on demand. It is intended to be called only after the user has selected
    a single ISIN from the lightweight corporate list — never during list
    rendering, pagination, or search.

    The page is fetched with a plain HTTP GET; the authoritative cash-flow
    schedule is supplemented from the page's ``GetCashflowSchedule`` JSON
    method. If that method returns an empty schedule (the common case), the
    schedule remains empty and the frontend shows the neutral 'No cash-flow
    schedule available' state.

    Raises:
        CdsRichDetailLiveError: on transport failure, non-2xx response, or
            unparseable page. The lightweight daily corporate bond is unaffected.
    """
    if session is None:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
                )
            }
        )

    html = _fetch_rich_page_html(isin, session)
    detail = _parse_rich_page_html(isin, html)

    # Supplement schedule from the page method (best-effort; ignore failures).
    schedule = _post_cdsl_page_method(session, _GET_CASHFLOW_SCHEDULE_URL, isin)
    if isinstance(schedule, list):
        _merge_cashflow_schedule_from_page_method(detail, schedule)

    # Supplement history from the page method (best-effort; ignore failures).
    history = _post_cdsl_page_method(session, _GET_HISTORY_DTLS_URL, isin)
    if isinstance(history, list):
        _merge_history_from_page_method(detail, history)

    log.info(
        "CDSL rich detail fetched: isin=%s schedule_rows=%d rating_rows=%d",
        isin,
        len(detail.cash_flow_schedule),
        len(detail.rating_records),
    )
    return detail

