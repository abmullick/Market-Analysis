"""Normalization logic for provider raw records into the internal Bond model.

This module is the bridge between source-specific raw records
(CcilRawRecord / NseRawRecord / RbiRawRecord) and the normalized
Bond model.

Rules:
  - Never expose source-specific field names to the rest of the app.
  - Preserve source metadata (source, raw field values) when useful.
  - Use None for unavailable fields; never fabricate values.
  - Classify observations by data type (traded / indicative / reference / etc.).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from backend.models.bonds import (
    Bond,
    CcilRawRecord,
    DataType,
    DayCountConvention,
    InstrumentType,
    NseRawRecord,
    RbiRawRecord,
)


# ---------------------------------------------------------------------------
# Date parsing helpers
# ---------------------------------------------------------------------------

_INDIAN_DATE_FORMATS = [
    "%d-%b-%Y",      # 15-Jan-2026
    "%d-%B-%Y",      # 15-January-2026
    "%Y-%m-%d",      # 2026-01-15
    "%d/%m/%Y",      # 15/01/2026
    "%d-%m-%Y",      # 15-01-2026
]


def parse_date(raw: str) -> Optional[date]:
    """Parse a source date string into a date, or return None."""
    if not raw:
        return None
    text = raw.strip()
    for fmt in _INDIAN_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_float(raw: str) -> Optional[float]:
    """Parse a source numeric string into a float, or return None."""
    if not raw:
        return None
    text = raw.strip().replace("\xa0", " ").replace(",", "").replace("%", "").strip()
    try:
        return float(text)
    except (ValueError, InvalidOperation):
        return None


def parse_isin(raw: str) -> Optional[str]:
    """Return a cleaned ISIN if it looks valid, else None."""
    if not raw:
        return None
    text = raw.strip().upper()
    if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", text):
        return text
    return None


# ---------------------------------------------------------------------------
# CCIL normalization
# ---------------------------------------------------------------------------

def normalize_ccil_record(raw: CcilRawRecord) -> Bond:
    """Normalize a CCIL raw record into a Bond.

    CCIL Market Watch sections:
      - central  -> G-Sec (Central Government)
      - state    -> SDL
      - tbills   -> T-Bill

    Market data is classified as 'traded' where an LTP is present,
    otherwise 'indicative' where bid/offer exists, otherwise
    'reference'.
    """
    section = raw.section.lower().strip()
    # Normalize section name variants: "T-BILLS" -> "tbills", "CENTRAL" -> "central"
    section_clean = section.replace("-", "")
    if "tbill" in section_clean:
        section = "tbills"
    elif "central" in section:
        section = "central"
    elif "state" in section:
        section = "state"

    # --- Master data ---
    security_name = raw.security_description or raw.security_name or ""
    security_name = security_name.strip()

    issuer: Optional[str] = None
    instrument_type = InstrumentType.UNKNOWN

    if section == "central":
        issuer = "Government of India"
        instrument_type = InstrumentType.G_SEC
    elif section == "state":
        issuer = _issuer_from_description(security_name) or "State Government"
        instrument_type = InstrumentType.SDL
    elif section == "tbills":
        issuer = "Government of India"
        instrument_type = InstrumentType.T_BILL

    # Parse maturity date
    maturity = parse_date(raw.maturity_date)

    # Parse coupon / ISIN from description where possible
    coupon = _coupon_from_ccil_description(security_name, section)
    isin = parse_isin(raw.isin) or _isin_from_ccil_description(security_name)

    # --- Market data ---
    ltp = parse_float(raw.ltp)
    lty = parse_float(raw.lty)
    bid_price = parse_float(raw.bid_price)
    bid_yield = parse_float(raw.bid_yield)
    offer_price = parse_float(raw.offer_price)
    offer_yield = parse_float(raw.offer_yield)
    lta = parse_float(raw.lta)
    tta = parse_float(raw.tta)

    # Classify data type
    if ltp is not None:
        data_type = DataType.TRADED
        price = ltp
        ytm = lty
        last_traded_price = ltp
        last_traded_yield = lty
        traded_value = lta or tta
    elif bid_price is not None and offer_price is not None:
        data_type = DataType.INDICATIVE
        price = None
        ytm = None
        bid_price_val = bid_price
        offer_price_val = offer_price
        bid_yield_val = bid_yield
        offer_yield_val = offer_yield
    else:
        data_type = DataType.REFERENCE
        price = None
        ytm = None

    # Build market observation dict
    market: dict = {
        "source": "CCIL",
        "data_type": data_type,
        "last_traded_price": ltp,
        "last_traded_yield": lty,
        "traded_value": lta or tta,
    }

    if data_type == DataType.TRADED:
        market["price"] = ltp
        market["ytm"] = lty
    elif data_type == DataType.INDICATIVE:
        market["bid_price"] = bid_price
        market["bid_yield"] = bid_yield
        market["offer_price"] = offer_price
        market["offer_yield"] = offer_yield
        market["price"] = None
        market["ytm"] = None

    # --- Build Bond ---
    bond = Bond(
        isin=isin,
        security_name=security_name,
        issuer=issuer,
        instrument_type=instrument_type,
        maturity_date=maturity,
        coupon_rate=coupon,
        **market,
    )

    return bond


# ---------------------------------------------------------------------------
# NSE normalization
# ---------------------------------------------------------------------------

def normalize_nse_record(raw: NseRawRecord) -> Optional[Bond]:
    """Normalize an NSE raw record into a Bond (or None if not a bond)."""
    report_type = raw.report_type.lower().strip()

    # Determine instrument type from report family / description
    desc = raw.security_description or ""
    is_tbill = (
        "tbill" in report_type
        or _looks_like_tbill(desc)
    )
    is_gsec = (
        ("gsec" in report_type or "sec" in report_type or "trade" in report_type or "histor" in report_type)
        and not is_tbill
    )

    if not (is_gsec or is_tbill):
        return None

    instrument_type = InstrumentType.T_BILL if is_tbill else InstrumentType.G_SEC
    issuer = "Government of India"

    # --- Master data ---
    security_name = desc.strip()
    maturity = parse_date(raw.maturity_date)
    coupon = parse_float(raw.coupon_rate)
    isin = parse_isin(raw.isin)

    # --- Market data ---
    price = parse_float(raw.price)
    ytm = parse_float(raw.yield_pct)
    traded_value = parse_float(raw.traded_value)
    trade_date = parse_date(raw.trade_date)
    accrued = parse_float(raw.accrued_interest)

    # Classify
    if report_type in ("trades", "historical"):
        data_type = DataType.TRADED if trade_date else DataType.HISTORICAL
    elif report_type in ("accrued-interest",):
        data_type = DataType.REFERENCE
    elif report_type in ("zcyc",):
        data_type = DataType.REFERENCE
    else:
        data_type = DataType.REFERENCE

    market: dict = {
        "source": "NSE",
        "data_type": data_type,
        "price": price,
        "ytm": ytm,
        "traded_value": traded_value,
        "trade_date": trade_date,
    }

    if accrued is not None:
        market["accrued_interest"] = accrued  # retained for validation, not a Bond field

    bond = Bond(
        isin=isin,
        security_name=security_name,
        issuer=issuer,
        instrument_type=instrument_type,
        maturity_date=maturity,
        coupon_rate=coupon,
        **market,
    )

    return bond


# ---------------------------------------------------------------------------
# RBI normalization
# ---------------------------------------------------------------------------

def normalize_rbi_record(raw: RbiRawRecord) -> Optional[Bond]:
    """Normalize an RBI reference record into a Bond (or None if not usable)."""
    series = raw.series or ""
    desc = raw.security_description or ""

    if not series and not desc:
        return None

    # Determine instrument type
    instrument_type_str = (raw.instrument_type or "").lower().strip()
    if "tbill" in instrument_type_str or _looks_like_tbill(desc):
        instrument_type = InstrumentType.T_BILL
    elif "sdl" in instrument_type_str:
        instrument_type = InstrumentType.SDL
    else:
        instrument_type = InstrumentType.G_SEC

    issuer = (
        "Government of India"
        if instrument_type != InstrumentType.SDL
        else _issuer_from_description(desc) or "State Government"
    )

    security_name = (desc or series).strip()
    maturity = parse_date(raw.maturity_date)
    coupon = parse_float(raw.coupon_rate)
    issue_date = parse_date(raw.issue_date)
    isin = parse_isin(raw.isin)
    auction_yield = parse_float(raw.auction_yield)
    reference_yield = parse_float(raw.reference_yield)
    as_of = parse_date(raw.as_of)

    # RBI is reference data; prefer auction yield for T-Bills, reference
    # yield for G-Secs / SDLs.
    ytm: Optional[float] = None
    if instrument_type == InstrumentType.T_BILL and auction_yield is not None:
        ytm = auction_yield
    elif reference_yield is not None:
        ytm = reference_yield

    bond = Bond(
        isin=isin,
        security_name=security_name,
        issuer=issuer,
        instrument_type=instrument_type,
        issue_date=issue_date,
        maturity_date=maturity,
        coupon_rate=coupon,
        ytm=ytm,
        source="RBI",
        data_type=DataType.REFERENCE,
        as_of=as_of,
    )

    return bond


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _looks_like_tbill(desc: str) -> bool:
    """Heuristic: T-Bill descriptions often contain 'TBILL', '91-Day', '182-Day', '364-Day'."""
    text = (desc or "").lower()
    return bool(
        re.search(r"tbill|91-day|182-day|364-day|treasury bill", text)
    )


# CCIL security descriptions embed the coupon as a leading numeric token:
#   "06.94 GS 2036"      -> 6.94   (Central Government G-Sec)
#   "07.17 MP SDL 2029"  -> 7.17   (State SDL)
#   "07.92 HR SGS 2052"  -> 7.92   (State Government Security)
# The match is anchored at the start of the description and must be
# immediately followed by the security-type token, so the maturity year is
# never mistaken for a coupon.
_CCIL_COUPON_PREFIX_RE = re.compile(
    r"^\s*(\d{1,2}(?:\.\d{1,4})?)\s+(?:[A-Z]{2,3}\s+)?(?:GS|SDL|SGS)\b",
    re.IGNORECASE,
)

# Explicit percentage form, e.g. "12.30%, 09-Dec-2026".
_CCIL_COUPON_PERCENT_RE = re.compile(r"(\d{1,2}(?:\.\d{1,4})?)\s*%")

# Money-market descriptions carry a tenor (91/182/364 days), not a coupon.
_CCIL_TBILL_DESC_RE = re.compile(
    r"\b(?:DTB|TBILL|T-BILL|TREASURY\s+BILL|CMB|CASH\s+MANAGEMENT)\b",
    re.IGNORECASE,
)

# Sane coupon band for Indian government securities (percent).
_COUPON_MIN = 0.1
_COUPON_MAX = 25.0


def _plausible_coupon(value: float) -> Optional[float]:
    """Return *value* when it lies in a sane coupon band, else None."""
    if _COUPON_MIN <= value <= _COUPON_MAX:
        return value
    return None


def _coupon_from_ccil_description(desc: str, section: str) -> Optional[float]:
    """Attempt to extract coupon rate from a CCIL security description.

    CCIL publishes two description conventions:

      * explicit percentage form:
            "12.30%, 09-Dec-2026"  -> 12.30
      * NDS-OM short form (no '%' symbol at all):
            "06.94 GS 2036"        -> 6.94
            "06.48 GS 2035"        -> 6.48
            "07.06 GS 2041"        -> 7.06
            "07.17 MP SDL 2029"    -> 7.17
            "07.92 HR SGS 2052"    -> 7.92

    Zero-coupon / money-market descriptions return None:
            "364 DTB 09092027"     -> None (tenor, not coupon)
            "182 DTB 31122026"     -> None
            "91 Day T-Bill"        -> None
            "GOI FRB 2033"         -> None (no coupon in description)

    The maturity year is never interpreted as a coupon, and the T-Bill
    tenor (91/182/364) is never interpreted as a coupon.
    """
    if section == "tbills":
        return None
    text = (desc or "").strip()
    if not text or _CCIL_TBILL_DESC_RE.search(text):
        return None

    # 1. Explicit percentage form.
    m = _CCIL_COUPON_PERCENT_RE.search(text)
    if m:
        return _plausible_coupon(float(m.group(1)))

    # 2. NDS-OM short form: leading coupon followed by the security type.
    m = _CCIL_COUPON_PREFIX_RE.match(text)
    if m:
        return _plausible_coupon(float(m.group(1)))

    return None


def _isin_from_ccil_description(desc: str) -> Optional[str]:
    """Attempt to extract an ISIN from a CCIL security description."""
    m = re.search(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", desc)
    if m:
        return m.group(0)
    return None


def _issuer_from_description(desc: str) -> Optional[str]:
    """Attempt to extract state name from SDL description."""
    text = (desc or "").lower()
    # Common patterns: "State of Maharashtra", "Maharashtra SDL", etc.
    m = re.search(r"state of ([a-zA-Z ]+)", text)
    if m:
        return "State of " + m.group(1).title()
    m = re.search(r"([a-zA-Z ]+) sdl", text)
    if m:
        return "State of " + m.group(1).strip().title()
    return None
