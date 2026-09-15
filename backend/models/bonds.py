"""
Normalized Bond domain model.

Represents Government of India dated securities (G-Secs), Treasury Bills (T-Bills),
and State Development Loans (SDLs), with optional fields reserved for future
corporate-bond support (NSE/BSE/SEBI adapters).

The model is normalized from multiple public sources (CCIL, NSE, RBI) so that the
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
    """Normalized instrument types for government securities."""

    G_SEC = "G-Sec"
    T_BILL = "T-Bill"
    SDL = "SDL"
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
    """Immutable / reference master data for a bond security."""

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

    # --- Future corporate-bond fields (reserved, not populated for Govt bonds) ---
    credit_rating: Optional[str] = Field(default=None)
    rating_agency: Optional[str] = Field(default=None)
    secured_status: Optional[str] = Field(default=None)
    seniority: Optional[str] = Field(default=None)
    call_date: Optional[date] = Field(default=None)
    put_date: Optional[date] = Field(default=None)
    issuer_sector: Optional[str] = Field(default=None)


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
    """Raw NSE public debt-report row, normalized minimally for internal passing."""

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
