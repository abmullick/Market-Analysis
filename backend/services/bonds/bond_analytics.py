"""Bond analytics engine.

Independent fixed-income analytics for government securities and T-Bills.

Calculations:
  1. Current Yield
  2. Accrued Interest
  3. Cash Flow Schedule
  4. YTM (calculated independently of market YTM)
  5. Macaulay Duration
  6. Modified Duration
  7. Convexity
  8. DV01

For T-Bills (zero-coupon):
  - Treat as zero-coupon instruments.
  - Do NOT force coupon-bond calculations.
  - YTM is computed from price + maturity.

For coupon-bearing securities:
  - Construct actual cash flows from coupon, frequency, maturity and face value.
  - Respect the appropriate settlement/accrual convention where available.

The engine does NOT contact any external data source.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
import math

from backend.models.bonds import AnalyticsResult, Bond, DataType, DayCountConvention
from backend.services.bonds.bond_cashflows import generate_cash_flows, accrued_interest


# ---------------------------------------------------------------------------
# YTM solver (Newton-Raphson)
# ---------------------------------------------------------------------------

def _price_from_yield(
    cash_flows: list[dict[str, Any]],
    ytm: float,                  # decimal, e.g. 0.0715 for 7.15%
    settlement_date: date,
    day_count: str = "ACT/365",
) -> float:
    """Compute dirty price from a yield and cash-flow schedule.

    Discounts each cash flow back to settlement_date using compound
    discounting with the appropriate time factor.
    """
    total = 0.0
    for cf in cash_flows:
        cf_date = cf["date"]
        amount = float(cf["total"])
        t = _time_factor(settlement_date, cf_date, day_count)
        if t < 0:
            t = 0.0
        total += amount / ((1.0 + ytm) ** t)
    return total


def _time_factor(from_date: date, to_date: date, day_count: str) -> float:
    """Compute the time factor (years) between two dates.

    Conventions:
      - ACT/365: actual days / 365
      - ACT/360: actual days / 360
      - ACT/ACT: actual days / actual days in coupon period (approx
        365/frequency)
    """
    actual = (to_date - from_date).days
    if actual <= 0:
        return 0.0
    if day_count == "ACT/365":
        return actual / 365.0
    if day_count == "ACT/360":
        return actual / 360.0
    # ACT/ACT fallback: use 365/frequency approximation
    return actual / 365.0


def solve_ytm(
    cash_flows: list[dict[str, Any]],
    dirty_price: float,
    settlement_date: date,
    day_count: str = "ACT/365",
    guess: float = 0.07,
    max_iter: int = 200,
    tolerance: float = 1e-8,
) -> Optional[float]:
    """Solve for YTM (decimal) given a dirty price and cash-flow schedule.

    Uses Newton-Raphson on the bond pricing function.

    Returns None if:
      - dirty_price <= 0
      - no cash flows
      - solver fails to converge
    """
    if dirty_price <= 0 or not cash_flows:
        return None

    y = guess
    for _ in range(max_iter):
        price = _price_from_yield(cash_flows, y, settlement_date, day_count)
        diff = price - dirty_price
        if abs(diff) < tolerance:
            return y

        # Numerical derivative
        dy = 1e-6
        price_plus = _price_from_yield(cash_flows, y + dy, settlement_date, day_count)
        derivative = (price_plus - price) / dy

        if abs(derivative) < 1e-12:
            break

        y = y - diff / derivative

        # Clamp to reasonable range
        if y < -0.5:
            y = -0.49
        if y > 0.5:
            y = 0.49

    # Final check
    price = _price_from_yield(cash_flows, y, settlement_date, day_count)
    if abs(price - dirty_price) < tolerance * dirty_price + 1e-6:
        return y

    return None


# ---------------------------------------------------------------------------
# Public analytics API
# ---------------------------------------------------------------------------

def compute_analytics(
    bond: Bond,
    settlement_date: Optional[date] = None,
    day_count: Optional[str] = None,
) -> AnalyticsResult:
    """Compute full analytics for a normalized Bond.

    Args:
        bond: Normalized Bond record (master + market observation).
        settlement_date: Date for analytics. Defaults to trade_date or today.
        day_count: Day-count convention. Defaults to bond's convention or ACT/365.

    Returns:
        AnalyticsResult with calculated_ytm (independent of market YTM),
        market_ytm (retained separately from source), current_yield,
        accrued_interest, cash_flows, durations, convexity, DV01.
    """
    notes: list[str] = []

    # --- Settlement date ---
    if settlement_date is None:
        if bond.trade_date:
            settlement_date = bond.trade_date
        else:
            settlement_date = date.today()

    # --- Day count ---
    if day_count is None:
        if bond.day_count_convention and bond.day_count_convention != DayCountConvention.UNKNOWN:
            day_count = bond.day_count_convention.value
        else:
            day_count = "ACT/365"

    notes.append(f"Settlement date: {settlement_date}")
    notes.append(f"Day count: {day_count}")

    # --- Face value / coupon / frequency defaults ---
    face_value = bond.face_value if bond.face_value else 100.0
    coupon_rate = bond.coupon_rate
    frequency = bond.coupon_frequency or 2

    is_tbill = (
        bond.instrument_type is not None
        and bond.instrument_type.value == "T-Bill"
    ) or (coupon_rate is not None and coupon_rate == 0)

    if is_tbill:
        notes.append("T-Bill / zero-coupon instrument: treated as zero-coupon")

    # --- Cash flow schedule ---
    cash_flows = generate_cash_flows(
        issue_date=bond.issue_date,
        maturity_date=bond.maturity_date,
        coupon_rate=coupon_rate,
        coupon_frequency=frequency,
        face_value=face_value,
        settlement_date=settlement_date,
        day_count=day_count,
    )

    # --- Accrued interest ---
    last_coupon = None
    if cash_flows and len(cash_flows) > 1:
        last_coupon = cash_flows[0]["date"]
    elif cash_flows and len(cash_flows) == 1:
        # T-Bill: no accrued
        last_coupon = None

    ai_amount, ai_days = accrued_interest(
        coupon_rate=coupon_rate,
        face_value=face_value,
        last_coupon_date=last_coupon,
        settlement_date=settlement_date,
        coupon_frequency=frequency,
        day_count=day_count,
    )

    # --- Clean price ---
    dirty_price = None
    clean_price = None

    if bond.dirty_price is not None:
        dirty_price = bond.dirty_price
    elif bond.price is not None:
        dirty_price = bond.price

    if bond.clean_price is not None:
        clean_price = bond.clean_price
    elif dirty_price is not None:
        clean_price = dirty_price - ai_amount

    # --- Current yield ---
    current_yield = None
    if clean_price and clean_price > 0 and coupon_rate and not is_tbill:
        current_yield = (coupon_rate * face_value) / clean_price * 100.0  # percent
        notes.append(f"Current yield: {current_yield:.4f}%")

    # --- Calculated YTM ---
    calculated_ytm = None
    if dirty_price and dirty_price > 0 and cash_flows:
        ytm_decimal = solve_ytm(
            cash_flows=cash_flows,
            dirty_price=dirty_price,
            settlement_date=settlement_date,
            day_count=day_count,
        )
        if ytm_decimal is not None:
            calculated_ytm = ytm_decimal * 100.0  # convert to percent
            notes.append(f"Calculated YTM: {calculated_ytm:.4f}%")

    # --- Market YTM (retained separately) ---
    market_ytm = bond.ytm  # source-reported YTM, in percent
    if market_ytm is not None:
        notes.append(f"Market YTM (source): {market_ytm:.4f}%")

    # --- Duration / Convexity / DV01 ---
    macaulay_duration = None
    modified_duration = None
    convexity = None
    dv01 = None

    if cash_flows and dirty_price and dirty_price > 0 and not is_tbill:
        ytm_decimal = (calculated_ytm / 100.0) if calculated_ytm is not None else (market_ytm / 100.0 if market_ytm is not None else 0.07)

        macaulay_duration, modified_duration, convexity = _compute_duration_convexity(
            cash_flows=cash_flows,
            ytm=ytm_decimal,
            settlement_date=settlement_date,
            day_count=day_count,
        )

        # DV01: change in price for 1bp move in yield, per 100 par
        if modified_duration is not None:
            dv01 = modified_duration * 0.0001 * face_value
            # More precise: recompute price at y +/- 1bp and take diff
            dv01_precise = _dv01_from_pricing(
                cash_flows=cash_flows,
                ytm=ytm_decimal,
                settlement_date=settlement_date,
                day_count=day_count,
                face_value=face_value,
            )
            if dv01_precise is not None:
                dv01 = dv01_precise

        notes.append(f"Macaulay duration: {macaulay_duration:.4f} years" if macaulay_duration else "Macaulay duration: N/A")
        notes.append(f"Modified duration: {modified_duration:.4f}" if modified_duration else "Modified duration: N/A")
        notes.append(f"Convexity: {convexity:.4f}" if convexity else "Convexity: N/A")
        notes.append(f"DV01: {dv01:.6f}" if dv01 else "DV01: N/A")

    elif is_tbill and cash_flows and dirty_price and dirty_price > 0:
        # T-Bill duration = time to maturity
        ttm = _time_factor(settlement_date, cash_flows[0]["date"], day_count)
        if ttm > 0:
            macaulay_duration = ttm
            modified_duration = ttm / (1.0 + (market_ytm / 100.0 if market_ytm else calculated_ytm / 100.0 if calculated_ytm else 0.0))
            dv01 = modified_duration * 0.0001 * face_value
            notes.append(f"T-Bill Macaulay duration (TTM): {macaulay_duration:.4f} years")
            notes.append(f"T-Bill DV01: {dv01:.6f}")

    return AnalyticsResult(
        current_yield=current_yield,
        calculated_ytm=calculated_ytm,
        market_ytm=market_ytm,
        cash_flows=cash_flows,
        accrued_interest=ai_amount,
        accrued_interest_days=ai_days,
        macaulay_duration=macaulay_duration,
        modified_duration=modified_duration,
        convexity=convexity,
        dv01=dv01,
        settlement_date=settlement_date,
        day_count_convention=day_count,
        notes=notes if notes else None,
    )


# ---------------------------------------------------------------------------
# Duration / convexity calculations
# ---------------------------------------------------------------------------

def _compute_duration_convexity(
    cash_flows: list[dict[str, Any]],
    ytm: float,
    settlement_date: date,
    day_count: str,
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Compute Macaulay duration, modified duration, and convexity.

    Returns (macaulay_duration, modified_duration, convexity).
    All values are None if computation fails.
    """
    if not cash_flows:
        return None, None, None

    macaulay_num = 0.0
    macaulay_den = 0.0
    convexity_num = 0.0

    for cf in cash_flows:
        amount = float(cf["total"])
        t = _time_factor(settlement_date, cf["date"], day_count)
        if t <= 0:
            continue
        df = 1.0 / ((1.0 + ytm) ** t)
        pv = amount * df
        macaulay_num += t * pv
        macaulay_den += pv
        convexity_num += t * (t + 1) * pv / ((1.0 + ytm) ** 2)

    if macaulay_den == 0:
        return None, None, None

    macaulay = macaulay_num / macaulay_den
    modified = macaulay / (1.0 + ytm)
    convexity_val = convexity_num / macaulay_den

    return round(macaulay, 6), round(modified, 6), round(convexity_val, 6)


def _dv01_from_pricing(
    cash_flows: list[dict[str, Any]],
    ytm: float,
    settlement_date: date,
    day_count: str,
    face_value: float,
) -> Optional[float]:
    """Compute DV01 by repricing at y +/- 1bp."""
    bp = 0.0001
    p_minus = _price_from_yield(cash_flows, ytm - bp, settlement_date, day_count)
    p_plus = _price_from_yield(cash_flows, ytm + bp, settlement_date, day_count)
    if p_minus is None or p_plus is None:
        return None
    return round(abs(p_minus - p_plus), 6)
