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
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

from backend.config.settings import Settings
from backend.models.bonds import (
    CdslCorporateBondPrimaryRawRecord,
    CdslCorporateBondSecondaryRawRecord,
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
               hidden form date (e.g. ``"16-Sep-2026"``).
            3. ``#markettype_select`` = ``market_type`` (``"S"`` secondary,
               ``"P"`` primary) and ``#filter_select`` = ``"A"`` (for all).
               ``#search_text`` is intentionally left untouched because the
               control is hidden for filter ``A``.
            4. Click ``#btnsearch`` and wait for the resulting document.
            5. Extract the data rows of ``table_selector`` from the rendered
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
                    page.locator("#idtradedate").fill(display_date)
                    page.locator("#idhdndate").evaluate(
                        "(el, value) => { el.value = value; }",
                        hidden_date,
                    )

                    page.locator("#markettype_select").select_option(market_type)
                    page.locator("#filter_select").select_option("A")

                    try:
                        with page.expect_navigation(
                            wait_until="domcontentloaded",
                            timeout=60_000,
                        ):
                            page.locator("#btnsearch").click()
                    except PlaywrightTimeoutError:
                        log.warning(
                            "CDSL search navigation timed out; continuing "
                            "with the current page state"
                        )

                    table = page.locator(table_selector)
                    table.wait_for(state="attached", timeout=30_000)

                    if table.count() == 0:
                        raise CdsCorporateBondLiveError(
                            "CDSL report table '%s' was not found after "
                            "search (market_type=%r, trade_date=%r): page "
                            "interaction failed"
                            % (table_selector, market_type, display_date)
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

