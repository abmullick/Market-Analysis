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

Public surface is intentionally CSV/text/path-based for this phase. There is
no live URL discovery, scraping, or CAPTCHA automation in this module.

Raw records use the source models defined in ``backend.models.bonds``:

    - CdslCorporateBondPrimaryRawRecord
    - CdslCorporateBondSecondaryRawRecord
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import Dict, List, Optional, Sequence

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


def _clean(s: Optional[str]) -> Optional[str]:
    """Return trimmed text or ``None`` for blank/None inputs."""
    if s is None:
        return None
    t = s.strip()
    return t or None


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
            mapped: Dict[str, int] = {}
            for idx, name in enumerate(norm):
                if name:
                    mapped[name.lower()] = idx
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
    for name in _PRIMARY_HEADER:
        for key, pos in {
            k.strip().lower(): v for v, k in enumerate(header)
        }.items():
            if key == name.lower():
                idx[name] = pos

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
        issue_type = _clean(_col("Issue Type"))
        issue_size_raw = _clean(_col("Issue Size (In Cr.)"))
        issue_price_raw = _clean(_col("Issue Price (Rs.)"))
        issue_date = _parse_date(_clean(_col("Issue Date")))
        maturity_date = _parse_date(_clean(_col("Date of Maturity")))
        coupon_rate_raw = _clean(_col("Coupon Rate (%)"))
        mode_of_issuance = _clean(_col("Mode of Issuance"))

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

    # Walk backwards from the last known fixed columns to find where the
    # surplus began. The last 5 columns are: LTP, VWAP, WAY, Remark, and
    # the trade-value field is immediately before LTP.
    expected_tail = [
        "Last Traded Price (in Rs.)",
        "weighted Average price (VWAP)",
        "Weighted Average Yield",
        "Remark",
    ]

    total_expected = len(_SECONDARY_HEADER)
    surplus = len(fields) - total_expected
    if surplus <= 0:
        return None

    # Rebuild by merging the middle block that contains the malformed value.
    # Strategy: keep first N columns up to trade-value, merge any surplus
    # columns into trade-value, then keep remaining fixed columns.
    nv_index = None
    for i, name in enumerate(_SECONDARY_HEADER):
        if name == "Total Trade Value (Rs. Lakhs)":
            nv_index = i
            break

    if nv_index is None:
        return None

    before = list(fields[: nv_index + 1])
    middle = list(fields[nv_index + 1 : len(fields) - 4])
    after = list(fields[len(fields) - 4 :])

    merged_value = ",".join([
        _clean(f) or ""
        for f in (fields[nv_index : len(fields) - 4])
    ])

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

        exchange = _clean(_col("Exchange"))
        trade_date = _parse_date(_clean(_col("Trade Date")))
        listed_unlisted = _clean(_col("Listed/Unlisted security"))
        issuer_name = _clean(_col("Issuer name"))
        issue_description = _clean(_col("Issue Description"))
        coupon_rate_raw = _clean(_col("Coupon(%)"))
        maturity_date = _parse_date(_clean(_col("Maturity Date")))
        credit_rating_raw = _clean(_col("Credit Rating"))
        number_of_trades = _clean(_col("Number of Trades"))
        total_trade_value_raw = _clean(_col("Total Trade Value (Rs. Lakhs)"))
        last_traded_price_raw = _clean(_col("Last Traded Price (in Rs.)"))
        vwap_raw = _clean(_col("weighted Average price (VWAP)"))
        weighted_average_yield_raw = _clean(_col("Weighted Average Yield"))
        remark = _clean(_col("Remark"))

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



class CdsCorporateBondClient:
    """CDSL corporate-bond market-data client (CSV/text/path phase).

    This client does not perform live fetching, scraping, or CAPTCHA
    automation. It accepts raw CSV content or local CSV paths and returns
    raw records for later normalization.
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

