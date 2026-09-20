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
from typing import Dict, Optional

from backend.models.bonds import (
    Bond,
    CcilRawRecord,
    CdslCorporateBondPrimaryRawRecord,
    CdslCorporateBondSecondaryRawRecord,
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
    "%d-%b-%y",      # 11-May-36
    "%d %b %Y",      # 11 May 2036
    "%d %B %Y",      # 11 May 2036
    "%d-%b-%Y %H:%M:%S",  # NSE datetime exports
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M",
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
        market["clean_price"] = ltp
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
# NSE normalization (Debt Instruments security master)
# ---------------------------------------------------------------------------

# Explicit NSE `SECTYPE` codes observed in the WDM Debt Instruments master
# ("Securities Available for Trading"). The code is the primary, deterministic
# classification source whenever it is present and recognized:
#
#   SECTYPE=TB -> Treasury Bill      ISSUE_DESC="GOI TBILL 364D-23/10/26"
#   SECTYPE=GS -> Government Stock
#   SECTYPE=SG -> State Government loan; classified SDL only when the
#                 description confirms SDL / state-government wording
#                 (e.g. "SDL GUJARAT 8.26% 2031"). A plain `SG` code is NOT
#                 enough: some `SG` rows are state special bonds, not SDLs.
#
# Keys are normalized (upper-case, alphanumeric only), so "G-Sec" and "GSEC"
# both resolve to the same key.
_NSE_SECTYPE_EXPLICIT: Dict[str, InstrumentType] = {
    "TB": InstrumentType.T_BILL,
    "TBILL": InstrumentType.T_BILL,
    "GS": InstrumentType.G_SEC,
    "GSEC": InstrumentType.G_SEC,
    "SDL": InstrumentType.SDL,
    "SGS": InstrumentType.SDL,
}

_NSE_SECTYPE_KEY_RE = re.compile(r"[^A-Z0-9]")
_NSE_TOKEN_RE = re.compile(r"[a-z0-9]+")

# SDL confirmation vocabulary (token-aware; never substring matching).
_NSE_SDL_TOKENS = frozenset({"sdl", "sgs"})
_NSE_SDL_PHRASES = (
    frozenset({"state", "development"}),
    frozenset({"state", "government"}),
    frozenset({"state", "govt"}),
    frozenset({"state", "loan"}),
)

# G-Sec fallback vocabulary (token-aware; "gs" must be a standalone token,
# never a substring inside a symbol such as "GSIL28").
_NSE_GSEC_TOKENS = frozenset({"gs", "gsec", "dated"})


def _nse_sectype_key(raw: Any) -> Optional[str]:
    """Return the normalized explicit SECTYPE key, or None when absent."""
    value = (getattr(raw, "instrument_type", None) or "").strip().upper()
    if not value:
        return None
    return _NSE_SECTYPE_KEY_RE.sub("", value) or None


def _nse_tokens(*values: Any) -> frozenset:
    """Tokenize the given free-text values (lower-case alphanumeric tokens)."""
    joined = " ".join(str(v) for v in values if v)
    return frozenset(_NSE_TOKEN_RE.findall(joined.lower()))


def _nse_desc_confirms_tbill(tokens: frozenset) -> bool:
    """True when the token set identifies a Treasury Bill."""
    if tokens & {"tbill", "tbills", "dtb", "dtbs"}:
        return True
    if "t" in tokens and "bill" in tokens:
        return True
    if "treasury" in tokens and "bill" in tokens:
        return True
    return any(tenor in tokens and "day" in tokens for tenor in ("91", "182", "364"))


def _nse_desc_confirms_sdl(tokens: frozenset) -> bool:
    """True when the token set identifies a State Development Loan."""
    if tokens & _NSE_SDL_TOKENS:
        return True
    return any(phrase <= tokens for phrase in _NSE_SDL_PHRASES)


def _nse_desc_confirms_gsec(tokens: frozenset) -> bool:
    """True when the token set identifies a dated government security."""
    if tokens & _NSE_GSEC_TOKENS:
        return True
    if {"g", "sec"} <= tokens:
        return True
    return "government" in tokens


def _classify_nse_instrument(
    raw: NseRawRecord,
    desc: Optional[str] = None,
) -> InstrumentType:
    """Classify one NSE raw record, deterministically and in priority order.

    Precedence (per the instrument-type contract):

        1. T-Bill            (explicit SECTYPE, then description tokens)
        2. SDL               (explicit SECTYPE confirmed by the description)
        3. G-Sec             (explicit SECTYPE, then description tokens)
        4. Corporate / unsupported -> UNKNOWN (excluded by the caller)
        5. Unknown           -> UNKNOWN (excluded by the caller)

    Rules:
        * An explicit, recognized ``SECTYPE`` wins outright (TB -> T_BILL,
          GS -> G_SEC; SDL/SGS -> SDL).
        * ``SG`` is classified SDL only when the full description
          (``issue_description``, then the caller-supplied ``desc``, then
          ``security_description``) confirms SDL / state-government wording.
        * A present but unrecognized ``SECTYPE`` (e.g. DB, PT, ID, GZ) is NOT
          run through the keyword fallback: the source already says the
          instrument is not a recognized government security type, so it
          stays UNKNOWN.
        * Fallback keyword matching (report_type / descriptions) runs only
          when no explicit SECTYPE is available, and is token-aware: the
          letters "gs" inside a larger token (e.g. "GSIL28") never imply
          G-Sec.
    """
    sectype = _nse_sectype_key(raw)
    tokens = _nse_tokens(
        raw.issue_description,
        desc if desc is not None else raw.security_description,
        raw.security_description if desc is not None else None,
        raw.report_type,
    )

    if sectype == "SG":
        # State Government loan: SDL only when the description confirms it.
        if _nse_desc_confirms_sdl(tokens):
            return InstrumentType.SDL
        return InstrumentType.UNKNOWN

    explicit = _NSE_SECTYPE_EXPLICIT.get(sectype) if sectype else None
    if explicit is not None:
        return explicit

    if sectype is not None:
        # Explicit but unrecognized SECTYPE: never a government instrument.
        return InstrumentType.UNKNOWN

    # No explicit SECTYPE: legacy/synthetic reports fall back to tokens.
    if _nse_desc_confirms_tbill(tokens):
        return InstrumentType.T_BILL
    if _nse_desc_confirms_sdl(tokens):
        return InstrumentType.SDL
    if _nse_desc_confirms_gsec(tokens):
        return InstrumentType.G_SEC
    return InstrumentType.UNKNOWN


def _nse_is_corporate(
    raw: NseRawRecord,
    desc: Optional[str] = None,
) -> bool:
    """True when the record is a corporate / unsupported debt instrument.

    Token-aware counterpart of the legacy substring checks ("corp", "ncd",
    "debenture", "commercial paper", leading "cp"). Used for observability
    only: such records are excluded from the government universe either way.
    """
    tokens = _nse_tokens(
        getattr(raw, "instrument_type", None),
        getattr(raw, "issue_description", None),
        desc if desc is not None else getattr(raw, "security_description", None),
        getattr(raw, "report_type", None),
    )
    if any(t.startswith("corp") or t == "ncd" or t.startswith("debenture") for t in tokens):
        return True
    if "commercial" in tokens and "paper" in tokens:
        return True
    return "cp" in tokens

def normalize_nse_record(raw: NseRawRecord) -> Optional[Bond]:
    """Normalize an NSE government-security master or trade row into a Bond.

    Fields absent from the source stay None. Partial records without an ISIN
    are accepted when their description and instrument classification are usable.
    """
    desc = (raw.security_description or "").strip()
    if not desc:
        return None
    isin = parse_isin(raw.isin)
    report_type = raw.report_type.strip().lower()

    instrument_type = _nse_instrument_type(raw, desc)
    if instrument_type == InstrumentType.UNKNOWN:
        return None
    issuer = _nse_issuer(raw, desc, instrument_type)

    bond = Bond(
        isin=isin,
        security_name=desc,
        issuer=issuer,
        instrument_type=instrument_type,
        issue_date=parse_date(raw.issue_date or ""),
        maturity_date=parse_date(raw.maturity_date or ""),
        coupon_rate=parse_float(raw.coupon_rate or ""),
        coupon_frequency=_parse_coupon_frequency(raw.coupon_frequency),
        face_value=parse_float(raw.face_value or ""),
        listing_status=(raw.listing_status or "").strip() or None,
        source="NSE",
        data_type=DataType.TRADED if report_type == "trades" else DataType.REFERENCE,
        price=parse_float(raw.price),
        ytm=parse_float(raw.yield_pct),
        traded_value=parse_float(raw.traded_value),
        trade_date=parse_date(raw.trade_date),
    )
    return bond


def _nse_instrument_type(
    raw: NseRawRecord,
    desc: Optional[str] = None,
) -> InstrumentType:
    """Classify an NSE raw record (delegates to the shared classifier).

    Kept as the historical entry point; the rules live in
    :func:`_classify_nse_instrument` so the normalizer and the enrichment
    matcher can never drift apart.
    """
    return _classify_nse_instrument(raw, desc)


def _nse_issuer(raw: NseRawRecord, desc: str, instrument_type: InstrumentType) -> str:
    if raw.issuer and raw.issuer.strip():
        return raw.issuer.strip()
    if instrument_type == InstrumentType.SDL:
        # Prefer the full published description (e.g. NSE WDM ISSUE_DESC
        # "SDL GUJARAT 8.26% 2031") over the short symbol when extracting
        # the state name.
        return (
            _issuer_from_description(raw.issue_description or "")
            or _issuer_from_description(desc)
            or "State Government"
        )
    return "Government of India"


def _parse_coupon_frequency(raw: str | None) -> Optional[int]:
    """Parse coupon frequency labels ('Half-Yearly', '2', 'Quarterly') to int.

    Also understands CDSL's spelled-out forms such as 'twelve times a year'
    and 'once a year'. Only well-defined payment cycles are returned;
    anything unrecognised stays ``None`` (never guessed).
    """
    if not raw:
        return None
    text = raw.strip().lower()
    if not text:
        return None
    m = re.search(r"\d+", text)
    if m:
        try:
            n = int(m.group(0))
            if 1 <= n <= 12:
                return n
        except ValueError:
            pass
    mapping = {
    "half-yearly": 2,
    "half yearly": 2,
    "semi-annual": 2,
    "semiannual": 2,
    "quarterly": 4,
    "monthly": 12,
    "annual": 1,
    "yearly": 1,
    }
    for key, val in mapping.items():
        if key in text:
            return val
    word_numbers = {
        "once": 1,
        "one": 1,
        "two": 2,
        "twice": 2,
        "three": 3,
        "four": 4,
        "six": 6,
        "twelve": 12,
    }
    if (
        "times a year" in text
        or "time a year" in text
        or "per year" in text
        or "a year" in text
        or "per annum" in text
    ):
        for word, n in word_numbers.items():
            if word in text:
                return n
    return None


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
    # Common patterns: "State of Maharashtra", "Maharashtra SDL", "SDL Gujarat 8.26% 2031".
    m = re.search(r"state of ([a-zA-Z ]+)", text)
    if m:
        return "State of " + m.group(1).title()
    m = re.search(r"([a-zA-Z ]+) sdl", text)
    if m:
        return "State of " + m.group(1).strip().title()
    # NSE WDM form: the SDL token precedes the state name
    # ("SDL GUJARAT 8.26% 2031", "SDL Goa 7.14% 2030").
    m = re.search(r"\bsdl\s+([a-zA-Z ]+?)(?:\s|$|\d)", text)
    if m and m.group(1).strip():
        return "State of " + m.group(1).strip().title()
    return None


# ---------------------------------------------------------------------------
# CDSL corporate bond normalization (primary + secondary market)
# ---------------------------------------------------------------------------

def _clean_str(value: Optional[str]) -> Optional[str]:
    """Trim whitespace and return None for blank strings."""
    if value is None:
        return None
    text = value.strip()
    return text or None


def _cdsl_coupon(raw: Optional[str]) -> Optional[float]:
    """Return the coupon rate as a float when the source value is numeric."""
    if not raw:
        return None
    text = raw.strip()
    if not text or text in ("-", "N/A", "NA", "n/a"):
        return None
    try:
        return float(text.replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def normalize_cdsl_corporate_primary_record(
    raw: CdslCorporateBondPrimaryRawRecord,
) -> Optional[Bond]:
    """Normalize a CDSL primary-market corporate issue row into a Bond.

    This is issuance/reference data only: no market price, YTM, LTP, VWAP,
    trade count, or trade value is fabricated. Fields absent from the
    source stay None. Returns None when the row lacks a usable ISIN.
    """
    isin = parse_isin(raw.isin)
    if not isin:
        return None

    security_name = _clean_str(raw.issue_description) or _clean_str(raw.issuer_name) or ""
    issuer = _clean_str(raw.issuer_name) or None

    issue_price = parse_float(raw.issue_price_raw or "")
    issue_size = parse_float(raw.issue_size_raw or "")
    coupon_rate = _cdsl_coupon(raw.coupon_rate_raw)

    bond = Bond(
        isin=isin,
        security_name=security_name,
        issuer=issuer,
        instrument_type=InstrumentType.CORPORATE,
        issue_date=parse_date(raw.issue_date or ""),
        maturity_date=parse_date(raw.maturity_date or ""),
        coupon_rate=coupon_rate,
        issue_size=issue_size,
        issue_price=issue_price,
        mode_of_issuance=_clean_str(raw.mode_of_issuance),
        source="CDSL",
        data_type=DataType.REFERENCE,
    )
    return bond


def normalize_cdsl_corporate_secondary_record(
    raw: CdslCorporateBondSecondaryRawRecord,
) -> Optional[Bond]:
    """Normalize a CDSL secondary-market corporate trade row into a Bond.

    Maps trade/market fields (LTP, VWAP, weighted-average yield, trade
    value, trade count) into the BondMarketObservation. Master fields
    (issuer, ISIN, description, coupon, maturity, credit rating) are
    populated when present. Source "-" / blank values are treated as
    missing. Returns None when the row lacks a usable ISIN.
    """
    isin = parse_isin(raw.isin)
    if not isin:
        return None

    security_name = _clean_str(raw.issue_description) or ""
    issuer = _clean_str(raw.issuer_name) or None
    coupon_rate = _cdsl_coupon(raw.coupon_rate_raw)
    maturity = parse_date(raw.maturity_date or "")
    trade_date = parse_date(raw.trade_date or "")

    ltp = parse_float(raw.last_traded_price_raw or "")
    vwap = parse_float(raw.vwap_raw or "")
    way = parse_float(raw.weighted_average_yield_raw or "")
    traded_value = parse_float(raw.total_trade_value_raw or "")
    trade_count_raw = parse_float(raw.number_of_trades or "")

    credit_rating = _clean_str(raw.credit_rating_raw)
    # CDSL uses "-" as a "no rating" sentinel; treat it as missing.
    if credit_rating in ("-", "--", "N/A", "NA", "n/a"):
        credit_rating = None
    listing_status = _clean_str(raw.listed_unlisted)
    if listing_status in ("-", "--", "N/A", "NA", "n/a"):
        listing_status = None

    market: dict = {
        "source": "CDSL",
        "data_type": DataType.TRADED,
        "exchange": _clean_str(raw.exchange),
        "last_traded_price": ltp,
        "weighted_average_price": vwap,
        "weighted_average_yield": way,
        "traded_value": traded_value,
        "trade_count": int(trade_count_raw) if trade_count_raw is not None else None,
        "trade_date": trade_date,
        "price": ltp,
        # CDSL supplies a Weighted Average Yield (WAY), not a distinct
        # last-traded yield, so last_traded_yield is deliberately None.
        "last_traded_yield": None,
    }
    if way is not None:
        market["ytm"] = way

    bond = Bond(
        isin=isin,
        security_name=security_name,
        issuer=issuer,
        instrument_type=InstrumentType.CORPORATE,
        maturity_date=maturity,
        coupon_rate=coupon_rate,
        credit_rating=credit_rating,
        listing_status=_clean_str(raw.listed_unlisted),
        **market,
    )
    return bond
