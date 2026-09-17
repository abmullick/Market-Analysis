"""
Normalized Bond domain model.

Represents Government of India dated securities (G-Secs), Treasury Bills (T-Bills),
State Development Loans (SDLs), and Corporate Bonds (public issues and private
placements). Provider-specific payloads are normalized into this model so that the
frontend and service layer never depend on source-specific field names.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Instrument type
# ---------------------------------------------------------------------------

class InstrumentType(str, Enum):
    """Normalized instrument types for government and corporate securities.

    Covers G-Secs, T-Bills, SDLs, and Corporate Bonds (public and private
    placements). Enum values mirror the frontend/instrument-type filter vocabulary
    used in the Bond analysis UI.
    """

    G_SEC = "G-Sec"
    T_BILL = "T-Bill"
    SDL = "SDL"
    CORPORATE = "Corporate Bond"
    UNKNOWN = "Unknown"


# ---------------------------------------------------------------------------
# Day-count conventions
# ---------------------------------------------------------------------------

class DayCountConvention(str, Enum):
    """Day-count conventions used in Indian government bond markets."""

    ACT_ACT = "ACT/ACT"
    ACT_365 = "ACT/365"
    ACT_360 = "ACT/360"
    THIRTY_360 = "30/360"
    UNKNOWN = "Unknown"


# ---------------------------------------------------------------------------
# Data types / freshness classification
# ---------------------------------------------------------------------------

class DataType(str, Enum):
    """Classification of an observation's nature."""

    TRADED = "traded"
    INDICATIVE = "indicative"
    MTM = "mtm"
    REFERENCE = "reference"
    AUCTION = "auction"
    HISTORICAL = "historical"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------

class BondMaster(BaseModel):
    """Immutable / reference master data for a bond security.

    Covers Government of India securities (G-Secs, T-Bills, SDLs) and Corporate
    Bonds (public issues and private placements). Provider-specific payloads are
    normalized into this model so that downstream code depends only on this common
    representation.

    Fields that are specific to a particular instrument class are still present on
    the shared model and default to ``None`` so that government-security records
    continue to validate without any corporate fields populated.
    """

    isin: Optional[str] = Field(default=None, description="ISIN")
    security_name: Optional[str] = Field(default=None, description="Security name/description")
    issuer: Optional[str] = Field(default=None, description="Issuing entity")
    instrument_type: InstrumentType = Field(default=InstrumentType.UNKNOWN)
    issue_date: Optional[date] = Field(default=None)
    maturity_date: Optional[date] = Field(default=None)
    coupon_rate: Optional[float] = Field(default=None, description="Annual coupon rate in percent")
    coupon_frequency: Optional[int] = Field(default=None, description="Coupon payments per year")
    face_value: Optional[float] = Field(default=None, description="Nominal/face/par value per unit")
    day_count_convention: DayCountConvention = Field(default=DayCountConvention.UNKNOWN)
    callable: bool = Field(default=False)
    puttable: bool = Field(default=False)
    listing_status: Optional[str] = Field(default=None)

    # --- Corporate-bond / private-placement reference fields ---
    # Populated from corporate-bond sources (NSE/CDSL/BSE). Left as None for
    # government securities and wherever a provider does not supply the value.
    credit_rating: Optional[str] = Field(default=None, description="Credit rating")
    rating_agency: Optional[str] = Field(default=None, description="Rating agency")
    secured_status: Optional[str] = Field(default=None, description="Secured / unsecured status")
    seniority: Optional[str] = Field(default=None, description="Seniority (senior / subordinated, etc.)")
    call_date: Optional[date] = Field(
        default=None, description="First call date, when available"
    )
    put_date: Optional[date] = Field(
        default=None, description="First put date, when available"
    )
    issuer_sector: Optional[str] = Field(default=None, description="Issuer sector / industry")
    issuer_type: Optional[str] = Field(
        default=None, description="Issuer classification / type"
    )
    issue_type: Optional[str] = Field(
        default=None, description="Type / category of the issue"
    )
    issue_size: Optional[float] = Field(
        default=None, description="Original issue size"
    )
    outstanding_amount: Optional[float] = Field(
        default=None, description="Amount currently outstanding, when available"
    )
    issue_price: Optional[float] = Field(
        default=None, description="Issue price"
    )
    coupon_type: Optional[str] = Field(
        default=None, description="Fixed / floating / zero / other, as supplied by source"
    )
    mode_of_issuance: Optional[str] = Field(
        default=None, description="EBP / NON-EBP / other source value"
    )
    guarantee_status: Optional[str] = Field(
        default=None, description="Guaranteed / unguaranteed / source value"
    )
    security_type: Optional[str] = Field(
        default=None, description="Source security classification"
    )
    exchange: Optional[str] = Field(
        default=None, description="Exchange / listing venue when supplied"
    )

    # --- Rich CDSL ISIN-detail fields (contract / security terms) ---
    # Populated from the CDSL rich ISIN detail page on demand when a single
    # corporate bond is selected. Left as None for government securities and
    # wherever the provider does not supply the value.

    # Issuer identity (beyond the basic issuer_name)
    issuer_address: Optional[str] = Field(
        default=None, description="Issuer registered address"
    )
    cin: Optional[str] = Field(
        default=None, description="Corporate Identification Number (CIN)"
    )
    lei: Optional[str] = Field(
        default=None, description="Legal Entity Identifier (LEI)"
    )

    # Coupon contract terms
    coupon_basis: Optional[str] = Field(
        default=None, description="Coupon basis: Fixed / Variable / Step-up, as supplied by source"
    )
    interest_start_date: Optional[date] = Field(
        default=None, description="Interest payment start date"
    )
    interest_end_date: Optional[date] = Field(
        default=None, description="Interest payment end date"
    )

    # Call / put option descriptors (text, not just dates)
    call_option: Optional[str] = Field(
        default=None, description="Call option descriptor (e.g. 'Not Applicable', 'Callable from ...')"
    )
    call_dates: Optional[str] = Field(
        default=None, description="Call option dates text"
    )
    put_option: Optional[str] = Field(
        default=None, description="Put option descriptor (e.g. 'Not Applicable', 'Putable from ...')"
    )
    put_dates: Optional[str] = Field(
        default=None, description="Put option dates text"
    )

    # Credit rating status
    rating_status: Optional[str] = Field(
        default=None, description="Rating status: Rated / Unrated"
    )
    credit_rating_outlook: Optional[str] = Field(
        default=None, description="Rating outlook (Stable / Positive / Negative etc.)"
    )
    rating_action_date: Optional[date] = Field(
        default=None, description="Date of rating action / latest rating"
    )

    # Redemption
    redemption_type: Optional[str] = Field(
        default=None, description="Redemption type: Full Redemption / Partial Redemption etc."
    )
    redemption_date: Optional[date] = Field(
        default=None, description="Redemption/maturity date (contractual)"
    )
    redemption_premium: Optional[str] = Field(
        default=None, description="Redemption premium details"
    )
    perpetual: Optional[bool] = Field(
        default=None, description="Whether the debenture/bond is perpetual"
    )
    debentuer_trustee: Optional[str] = Field(
        default=None, description="Debenture trustee name"
    )

    # Cash-flow schedule and record date rows from the CDSL rich detail page
    cash_flow_schedule: Optional[list] = Field(
        default=None, description="CDSL cash-flow schedule events"
    )
    record_date_rows: Optional[list] = Field(
        default=None, description="CDSL record date grid rows"
    )

    # Exchange/listing detail from the rich page
    exchange_listing_status: Optional[str] = Field(
        default=None, description="Exchange listing status (Listed / Unlisted)"
    )


# ---------------------------------------------------------------------------
# Market observation
# ---------------------------------------------------------------------------

class BondMarketObservation(BaseModel):
    """A single market observation for a bond.

    Prices may be clean or dirty; where both are available they are stored
    independently. Yields are stored as percentages (e.g. 7.25 = 7.25%).
    """

    price: Optional[float] = Field(default=None, description="Reported price (source-dependent, may be clean or dirty)")
    clean_price: Optional[float] = Field(default=None, description="Clean price (excl. accrued interest)")
    dirty_price: Optional[float] = Field(default=None, description="Dirty price (incl. accrued interest)")
    ytm: Optional[float] = Field(default=None, description="Yield-to-maturity from source (market YTM), in percent")
    bid_price: Optional[float] = Field(default=None, description="Best bid price")
    bid_yield: Optional[float] = Field(default=None, description="Best bid yield, in percent")
    offer_price: Optional[float] = Field(default=None, description="Best offer/ask price")
    offer_yield: Optional[float] = Field(default=None, description="Best offer/ask yield, in percent")
    last_traded_price: Optional[float] = Field(default=None, description="Last traded price (LTP)")
    last_traded_yield: Optional[float] = Field(default=None, description="Last traded yield (LTY)")
    traded_value: Optional[float] = Field(default=None, description="Total traded value/amount (LTA)")
    traded_quantity: Optional[float] = Field(default=None, description="Traded quantity")
    trade_count: Optional[int] = Field(default=None, description="Number of trades")
    trade_date: Optional[date] = Field(default=None, description="Trade/observation date")
    trade_time: Optional[str] = Field(default=None, description="Trade time as reported by source")
    weighted_average_price: Optional[float] = Field(default=None, description="Volume-weighted average price (VWAP)")
    weighted_average_yield: Optional[float] = Field(default=None, description="Weighted average yield, in percent")

    # --- Source & freshness ---
    source: Optional[str] = Field(default=None, description="Originating source identifier")
    as_of: Optional[date] = Field(default=None, description="Date the observation is as-of")
    retrieved_at: Optional[datetime] = Field(default=None, description="When the observation was retrieved by the backend")
    data_type: DataType = Field(default=DataType.UNKNOWN, description="Classification: traded/indicative/MTM/reference/auction/historical")
    freshness_days: Optional[int] = Field(default=None, description="Days since the observation date")


# ---------------------------------------------------------------------------
# Full normalized bond record
# ---------------------------------------------------------------------------

class Bond(BondMaster, BondMarketObservation):
    """Normalized bond record combining master data and a market observation.

    This is the internal model used across the Bond service layer. Providers
    normalize their source-specific payloads into this model; the frontend and
    analytics layers consume only this model.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)


# ---------------------------------------------------------------------------
# API request / response helpers
# ---------------------------------------------------------------------------

class BondListQuery(BaseModel):
    """Query parameters for GET /api/bonds."""

    instrument_type: Optional[InstrumentType] = Field(default=None, description="Filter by instrument type")
    issuer: Optional[str] = Field(default=None, description="Filter by issuer substring")
    search: Optional[str] = Field(default=None, description="Free-text search across security name / ISIN")
    limit: int = Field(default=50, ge=1, le=200, description="Maximum results to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")
    sort_by: Optional[str] = Field(
        default=None,
        description="Sort field: maturity_date, market_ytm, clean_price, coupon_rate, security_name, instrument_type",
    )
    sort_dir: str = Field(default="asc", description="Sort direction: asc or desc")


class BondListResponse(BaseModel):
    """Paginated response envelope for GET /api/bonds.

    Returned only when the client requests ``envelope=true``; the default
    response remains a plain JSON list of Bond records (backward compatible).
    ``total`` is the number of bonds matching the query BEFORE limit/offset
    are applied, so it represents the full available universe.
    """

    items: list[Bond] = Field(default_factory=list, description="Page of bonds")
    total: int = Field(default=0, ge=0, description="Total bonds matching the query")
    limit: int = Field(default=50, ge=1, le=200, description="Page size used")
    offset: int = Field(default=0, ge=0, description="Offset used for this page")



class AnalyticsResult(BaseModel):
    """Computed analytics for a single bond observation."""

    # --- Yield & return ---
    current_yield: Optional[float] = Field(default=None, description="Annual coupon / clean price (percent)")
    calculated_ytm: Optional[float] = Field(default=None, description="Backend-calculated YTM (percent), independent of source YTM")
    market_ytm: Optional[float] = Field(default=None, description="Source-reported YTM retained separately (percent)")

    # --- Cash-flow schedule ---
    cash_flows: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Projected cash flows: {period, principal, coupon, total}"
    )

    # --- Accrued interest ---
    accrued_interest: Optional[float] = Field(default=None, description="Accrued interest as of the observation settlement date")
    accrued_interest_days: Optional[int] = Field(default=None, description="Accrued days used in the calculation")

    # --- Risk / sensitivity ---
    macaulay_duration: Optional[float] = Field(default=None, description="Macaulay duration in years")
    modified_duration: Optional[float] = Field(default=None, description="Modified duration (price sensitivity to yield)")
    convexity: Optional[float] = Field(default=None, description="Convexity (second-order price sensitivity)")
    dv01: Optional[float] = Field(default=None, description="DV01: price change for 1bp yield move per 100 par")

    # --- Metadata ---
    settlement_date: Optional[date] = Field(default=None, description="Settlement/valuation date used for analytics")
    day_count_convention: Optional[str] = Field(default=None, description="Convention used for the calculation")
    notes: Optional[list[str]] = Field(default=None, description="Calculation notes / assumptions")


# ---------------------------------------------------------------------------
# Provider-normalized raw records (internal, not exposed to frontend)
# ---------------------------------------------------------------------------

class CcilRawRecord(BaseModel):
    """Raw CCIL Market Watch row, normalized minimally for internal passing.

    CCIL publishes separate sections for Central Government, State Government,
    and T-Bills, with overlapping but slightly different field sets.
    """

    section: str = Field(default="", description="CCIL section: 'central', 'state', or 'tbills'")
    security_description: Optional[str] = None
    maturity_date: Optional[str] = None
    bid_amount: Optional[str] = None
    bid_yield: Optional[str] = None
    bid_price: Optional[str] = None
    offer_price: Optional[str] = None
    offer_yield: Optional[str] = None
    offer_amount: Optional[str] = None
    ltp: Optional[str] = None
    lty: Optional[str] = None
    lta: Optional[str] = None
    tta: Optional[str] = None
    isin: Optional[str] = None
    coupon_rate: Optional[str] = None
    security_name: Optional[str] = None


class NseRawRecord(BaseModel):
    """Raw NSE public debt-report row, normalized minimally for internal passing.

    Covers NSE WDM Debt Instruments master rows, government-bond trades, and the
    corporate-bond / private-placement payloads the model is being extended to
    support. Fields are kept as optional strings/dates because provider CSVs and
    feeds supply them inconsistently, and not every record will populate every
    field.
    """

    report_type: str = Field(default="", description="NSE report family")
    security_description: Optional[str] = None
    isin: Optional[str] = None
    maturity_date: Optional[str] = None
    coupon_rate: Optional[str] = None
    price: Optional[str] = None
    yield_pct: Optional[str] = None
    traded_value: Optional[str] = None
    traded_quantity: Optional[str] = None
    trade_date: Optional[str] = None
    accrued_interest: Optional[str] = None
    zcyc: Optional[str] = None
    # --- NSE Debt Instruments master fields (header-driven CSV) ---
    issue_date: Optional[str] = None
    coupon_frequency: Optional[str] = None
    face_value: Optional[str] = None
    issuer: Optional[str] = None
    instrument_type: Optional[str] = None
    listing_status: Optional[str] = None
    # --- Corporate-bond / private-placement fields (future NSE/CDSL providers) ---
    issuer_type: Optional[str] = None
    issue_type: Optional[str] = None
    issue_size: Optional[str] = None
    outstanding_amount: Optional[str] = None
    issue_price: Optional[str] = None
    coupon_type: Optional[str] = None
    mode_of_issuance: Optional[str] = None
    guarantee_status: Optional[str] = None
    security_type: Optional[str] = None
    exchange: Optional[str] = None
    credit_rating: Optional[str] = None
    rating_agency: Optional[str] = None
    secured_status: Optional[str] = None
    seniority: Optional[str] = None


class RbiRawRecord(BaseModel):
    """Raw RBI/DBIE reference row, normalized minimally for internal passing."""

    series: Optional[str] = None
    security_description: Optional[str] = None
    isin: Optional[str] = None
    instrument_type: Optional[str] = None
    maturity_date: Optional[str] = None
    coupon_rate: Optional[str] = None
    issue_date: Optional[str] = None
    auction_yield: Optional[str] = None
    reference_yield: Optional[str] = None
    state_borrowing_ref: Optional[str] = None
    as_of: Optional[str] = None


# ---------------------------------------------------------------------------
# CDSL corporate-bond / private-placement raw records
# ---------------------------------------------------------------------------

class CdslCorporateBondPrimaryRawRecord(BaseModel):
    """One row from CDSL PrimaryMarketTradeData.csv.

    Schema (11 columns):
        ISIN, Temporary Isin, Issuer Name, Issue Description, Issue Type,
        Issue Size (In Cr.), Issue Price (Rs.), Issue Date, Date of Maturity,
        Coupon Rate (%), Mode of Issuance

    Raw source values are preserved as strings where convenient; only fields
    that can be parsed deterministically are coerced.
    """

    isin: Optional[str] = None
    temporary_isin: Optional[str] = None
    issuer_name: Optional[str] = None
    issue_description: Optional[str] = None
    issue_type: Optional[str] = None
    issue_size_raw: Optional[str] = None
    issue_price_raw: Optional[str] = None
    issue_date: Optional[str] = None
    maturity_date: Optional[str] = None
    coupon_rate_raw: Optional[str] = None
    mode_of_issuance: Optional[str] = None


class CdslCorporateBondSecondaryRawRecord(BaseModel):
    """One row from CDSL SecondaryMarketTradeData.csv.

    Schema (15 columns):
        Exchange, Trade Date, ISIN, Listed/Unlisted security, Issuer name,
        Issue Description, Coupon(%), Maturity Date, Credit Rating,
        Number of Trades, Total Trade Value (Rs. Lakhs),
        Last Traded Price (in Rs.), weighted Average price (VWAP),
        Weighted Average Yield, Remark

    A small number of source rows place an unquoted thousands separator inside
    ``Total Trade Value (Rs. Lakhs)``, which can inflate the column count to 16
    when parsed naively. The parser must repair such rows before constructing
    the raw record.
    """

    exchange: Optional[str] = None
    trade_date: Optional[str] = None
    isin: Optional[str] = None
    listed_unlisted: Optional[str] = None
    issuer_name: Optional[str] = None
    issue_description: Optional[str] = None
    coupon_rate_raw: Optional[str] = None
    maturity_date: Optional[str] = None
    credit_rating_raw: Optional[str] = None
    number_of_trades: Optional[str] = None
    total_trade_value_raw: Optional[str] = None
    last_traded_price_raw: Optional[str] = None
    vwap_raw: Optional[str] = None
    weighted_average_yield_raw: Optional[str] = None
    remark: Optional[str] = None


# ---------------------------------------------------------------------------
# CDSL rich ISIN detail raw payload (from /CorporateBond/CorpBondDatabase.aspx?ISIN=...)
# ---------------------------------------------------------------------------
class CdslCashFlowEvent(BaseModel):
    """One row from the CDSL cash-flow schedule page method (GetCashflowSchedule)."""

    event_type: Optional[str] = None
    redemption_method: Optional[str] = None
    quantity_redeemed: Optional[str] = None
    redemption_premium: Optional[str] = None
    net_face_value: Optional[str] = None
    record_date: Optional[str] = None
    due_date: Optional[str] = None
    amount_payable: Optional[str] = None
    payment_date: Optional[str] = None


class CdslRatingRecord(BaseModel):
    """One row from the CDSL rating details grid (grdRatingDtls)."""

    cra_name: Optional[str] = None
    credit_rating: Optional[str] = None
    rating_outlook: Optional[str] = None
    credit_rating_date: Optional[str] = None
    record_status: Optional[str] = None
    verification_date: Optional[str] = None
    
    
class CdslRatingHistoryRecord(BaseModel):
    """One row from the CDSL GetHistorydtls rating-history endpoint."""

    cra_name: Optional[str] = None
    credit_rating: Optional[str] = None
    credit_rating_date: Optional[str] = None
    credit_rating_change_date: Optional[str] = None
    credit_rating_status: Optional[str] = None
    rating_action: Optional[str] = None
    verification_date: Optional[str] = None    


class CdslRichCorporateDetail(BaseModel):
    """Raw, normalized-as-possible payload from the CDSL rich ISIN detail page.

    This is the internal bridge between the HTML source and the domain Bond
    model. It is intentionally field-heavy and conservative: missing source
    fields are preserved as None; source text is retained where interpretation
    is uncertain.
    """

    isin: Optional[str] = None

    # --- Security / master terms ---
    issuer_name: Optional[str] = None
    issuer_address: Optional[str] = None
    issuer_former_names: Optional[str] = None
    cin: Optional[str] = None
    lei: Optional[str] = None
    type_of_issuer: Optional[str] = None
    nature_of_issuer: Optional[str] = None
    business_sector: Optional[str] = None
    security_description: Optional[str] = None
    isin_short_description: Optional[str] = None
    instrument_type: Optional[str] = None
    instrument_description: Optional[str] = None
    secured_or_unsecured: Optional[str] = None
    guaranteed_or_partially_guaranteed: Optional[str] = None
    convertibility: Optional[str] = None
    seniority_in_payment: Optional[str] = None
    tax_free: Optional[str] = None
    series: Optional[str] = None
    tranche_no: Optional[str] = None
    infrastructure_category: Optional[str] = None
    face_value: Optional[str] = None
    tenure: Optional[str] = None
    defaulted_in_redemption: Optional[str] = None
    principal_protected: Optional[str] = None
    is_tokenized: Optional[str] = None

    # --- Issue details ---
    issue_type_label: Optional[str] = None
    put_option: Optional[str] = None
    put_option_dates: Optional[str] = None
    call_option: Optional[str] = None
    call_option_dates: Optional[str] = None
    rating_status: Optional[str] = None
    mode_of_issue: Optional[str] = None
    ebp_non_ebp: Optional[str] = None
    schedule_opening_date: Optional[str] = None
    schedule_closing_date: Optional[str] = None
    actual_closing_date: Optional[str] = None
    arranger_to_issue: Optional[str] = None
    lead_manager_to_issue: Optional[str] = None
    registrar_to_issue: Optional[str] = None
    debenture_trustee_to_issue: Optional[str] = None
    date_of_allotment: Optional[str] = None
    debentures_bonds_nature_perpetual: Optional[str] = None
    total_allotment_quantity: Optional[str] = None
    issue_price: Optional[str] = None
    issue_size_including_green_shoe: Optional[str] = None
    green_shoe_option: Optional[str] = None
    amount_raised: Optional[str] = None

    # --- Coupon / interest ---
    coupon_basis: Optional[str] = None
    coupon_rate_label: Optional[str] = None
    coupon_type: Optional[str] = None
    step_up_down_coupon_basis: Optional[str] = None
    coupon_reset_value: Optional[str] = None
    coupon_reset_date: Optional[str] = None
    day_count_convention: Optional[str] = None
    frequency_of_interest_payment: Optional[str] = None
    interest_payment_start_date: Optional[str] = None
    interest_payment_end_date: Optional[str] = None

    # --- Redemption ---
    redemption_type: Optional[str] = None
    redemption_date: Optional[str] = None
    redemption_premium_details: Optional[str] = None
    total_quantity_redeemed: Optional[str] = None
    total_value_redeemed: Optional[str] = None
    net_quantity: Optional[str] = None
    maturity_type: Optional[str] = None

    # --- Rating grid ---
    rating_records: list[CdslRatingRecord] = Field(default_factory=list)
    
    # --- Rating history (page method GetHistorydtls) ---
    rating_history: list[CdslRatingHistoryRecord] = Field(default_factory=list)

    # --- Cash-flow schedule (page method GetCashflowSchedule) ---
    cash_flow_schedule: list[CdslCashFlowEvent] = Field(default_factory=list)

    # --- Payment status / history ---
    interest_payment_record_date: Optional[str] = None
    interest_due_date: Optional[str] = None
    interest_actual_payment_date: Optional[str] = None
    interest_amount_paid: Optional[str] = None
    last_interest_payment_date: Optional[str] = None
    interest_non_payment_reason: Optional[str] = None
    redemption_type_status: Optional[str] = None
    partial_redemption: Optional[str] = None
    redemption_reason: Optional[str] = None
    redemption_date_due_to_put: Optional[str] = None
    redemption_date_due_to_call: Optional[str] = None
    quantity_redeemed_status: Optional[str] = None
    redemption_due_date: Optional[str] = None
    redemption_actual_date: Optional[str] = None
    amount_redeemed_status: Optional[str] = None
    outstanding_amount_status: Optional[str] = None
    redemption_last_interest_payment_date: Optional[str] = None

    # --- Exchange / listing ---
    exchange_name: Optional[str] = None
    exchange_listing_status: Optional[str] = None
    exchange_listing_date: Optional[str] = None

    # --- Record date grid (grdRecordDateDtls) ---
    record_date_rows: list[dict[str, Optional[str]]] = Field(default_factory=list)

    # --- Source ---
    source: Optional[str] = Field(default=None, description="Originating source identifier")
    retrieved_at: Optional[datetime] = Field(default=None, description="When this detail was retrieved by the backend")


