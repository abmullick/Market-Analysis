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
    - Use semiannual coupon-period discounting for Indian G-Secs / SDLs.
    - Use 30/360 period fractions when the security uses 30/360.
    - Keep market YTM separate from independently calculated YTM.

The engine does NOT contact any external data source.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Optional

from backend.models.bonds import (
    AnalyticsResult,
    Bond,
    DayCountConvention,
)
from backend.services.bonds.bond_cashflows import (
    accrued_interest,
    generate_cash_flows,
)


# ---------------------------------------------------------------------------
# Date / coupon-period helpers
# ---------------------------------------------------------------------------


def _days_between(
    from_date: date,
    to_date: date,
    day_count: str,
) -> int:
    """Return the number of days between two dates under the supplied basis."""
    if to_date <= from_date:
        return 0

    if day_count == "30/360":
        d1 = min(from_date.day, 30)
        d2 = min(to_date.day, 30)

        return (
            360 * (to_date.year - from_date.year)
            + 30 * (to_date.month - from_date.month)
            + (d2 - d1)
        )

    return (to_date - from_date).days


def _time_factor(
    from_date: date,
    to_date: date,
    day_count: str,
) -> float:
    """Compute years between two dates under the supplied day-count basis."""
    if to_date <= from_date:
        return 0.0

    if day_count == "30/360":
        return _days_between(from_date, to_date, day_count) / 360.0

    actual = (to_date - from_date).days

    if day_count == "ACT/360":
        return actual / 360.0

    if day_count == "ACT/365":
        return actual / 365.0

    # Preserve the existing ACT/ACT fallback used by the project.
    return actual / 365.0


def _coupon_period_details(
    cash_flows: list[dict[str, Any]],
    settlement_date: date,
    day_count: str,
) -> tuple[Optional[date], Optional[date], Optional[int], Optional[int], Optional[float]]:
    """Return previous coupon, next coupon and coupon-period day counts.

    Returns:
        (previous_coupon, next_coupon, A, DSC, E)

    A   = elapsed days from previous coupon to settlement.
    DSC = days from settlement to next coupon.
    E   = length of the current coupon period.

    For Indian G-Secs under 30/360, using the day before settlement for accrued
    interest means A + DSC may differ by one day from a naive calendar split.
    The YTM pricing convention, however, uses the settlement-to-next-coupon
    fraction DSC / E. With the standard 30/360 dates for a regular coupon bond
    this reproduces the RBI/Excel-style semiannual YIELD result.
    """
    if not cash_flows:
        return None, None, None, None, None

    ordered_dates = sorted(
        {
            cf["date"]
            for cf in cash_flows
            if isinstance(cf.get("date"), date)
        }
    )

    if not ordered_dates:
        return None, None, None, None, None

    previous_coupon: Optional[date] = None
    next_coupon: Optional[date] = None

    for cf_date in ordered_dates:
        if cf_date <= settlement_date:
            previous_coupon = cf_date
        elif next_coupon is None:
            next_coupon = cf_date
            break

    if next_coupon is None:
        return previous_coupon, None, None, None, None

    if previous_coupon is None:
        # Settlement before the first generated cash flow. This should be rare,
        # but use the first cash-flow date as the next coupon and infer the
        # preceding period from the next available coupon where possible.
        first_idx = ordered_dates.index(next_coupon)
        if first_idx > 0:
            previous_coupon = ordered_dates[first_idx - 1]
        else:
            previous_coupon = next_coupon

    e_days = _days_between(previous_coupon, next_coupon, day_count)
    dsc_days = _days_between(settlement_date, next_coupon, day_count)
    if day_count == "30/360":
        dsc_days += 1
    a_days = _days_between(previous_coupon, settlement_date, day_count)

    if e_days <= 0:
        return previous_coupon, next_coupon, a_days, dsc_days, None

    return (
        previous_coupon,
        next_coupon,
        a_days,
        dsc_days,
        float(e_days),
    )


def _cash_flow_exponents(
    cash_flows: list[dict[str, Any]],
    settlement_date: date,
    day_count: str,
    frequency: int,
) -> list[tuple[dict[str, Any], float]]:
    """Assign semiannual/frequency coupon-period exponents to future cash flows.

    The first future cash flow is discounted by DSC/E coupon periods.
    Subsequent cash flows advance by exactly one coupon period.
    """
    if not cash_flows or frequency <= 0:
        return []

    (
        _previous_coupon,
        next_coupon,
        _a_days,
        dsc_days,
        e_days,
    ) = _coupon_period_details(
        cash_flows,
        settlement_date,
        day_count,
    )

    if next_coupon is None or e_days is None or e_days <= 0:
        return []

    first_fraction = (
        dsc_days / e_days
        if dsc_days is not None
        else 1.0
    )

    # Settlement exactly on a coupon date: the next coupon is one full period
    # away, not zero periods away.
    if first_fraction <= 0.0:
        first_fraction = 1.0

    future = [
        cf
        for cf in cash_flows
        if cf["date"] > settlement_date
    ]

    exponents: list[tuple[dict[str, Any], float]] = []

    for index, cf in enumerate(future):
        exponent = first_fraction + index
        exponents.append((cf, exponent))

    return exponents


# ---------------------------------------------------------------------------
# YTM solver
# ---------------------------------------------------------------------------


def _price_from_yield(
    cash_flows: list[dict[str, Any]],
    ytm: float,
    settlement_date: date,
    day_count: str = "ACT/365",
    frequency: int = 2,
) -> float:
    """Compute dirty price from yield.

    Coupon-bearing securities use periodic compounding:
        Price = sum(CF / (1 + y/f)^n)

    where n is the number of coupon periods from settlement to each future
    cash flow, including the fractional first period DSC/E.

    For frequency <= 1, retain the annual effective-discount fallback.
    """
    if not cash_flows:
        return 0.0

    if frequency <= 1:
        total = 0.0

        for cf in cash_flows:
            cf_date = cf["date"]
            amount = float(cf["total"])

            t = _time_factor(
                settlement_date,
                cf_date,
                day_count,
            )

            if t < 0:
                t = 0.0

            denominator = 1.0 + ytm
            if denominator <= 0:
                return float("inf")

            total += amount / (denominator ** t)

        return total

    rate_per_period = ytm / frequency

    if 1.0 + rate_per_period <= 0.0:
        return float("inf")

    total = 0.0

    for cf, exponent in _cash_flow_exponents(
        cash_flows=cash_flows,
        settlement_date=settlement_date,
        day_count=day_count,
        frequency=frequency,
    ):
        amount = float(cf["total"])
        total += amount / ((1.0 + rate_per_period) ** exponent)

    return total


def solve_ytm(
    cash_flows: list[dict[str, Any]],
    dirty_price: float,
    settlement_date: date,
    day_count: str = "ACT/365",
    guess: float = 0.07,
    max_iter: int = 200,
    tolerance: float = 1e-8,
    frequency: int = 2,
) -> Optional[float]:
    """Solve for YTM (decimal) given a dirty price and cash-flow schedule.

    Coupon-bearing securities use periodic compounding with the supplied
    coupon frequency. For Indian G-Secs / SDLs this is normally frequency=2.

    Uses Newton-Raphson on the bond pricing function.

    Returns None if:
        - dirty_price <= 0
        - no cash flows
        - solver fails to converge
    """
    if dirty_price <= 0 or not cash_flows:
        return None

    y = float(guess)

    for _ in range(max_iter):
        price = _price_from_yield(
            cash_flows,
            y,
            settlement_date,
            day_count,
            frequency,
        )

        if not math.isfinite(price):
            return None

        diff = price - dirty_price

        if abs(diff) < tolerance:
            return y

        # Numerical derivative.
        dy = 1e-6

        price_plus = _price_from_yield(
            cash_flows,
            y + dy,
            settlement_date,
            day_count,
            frequency,
        )

        if not math.isfinite(price_plus):
            break

        derivative = (price_plus - price) / dy

        if abs(derivative) < 1e-12:
            break

        y = y - diff / derivative

        # Clamp to a reasonable range.
        if y < -0.5:
            y = -0.49

        if y > 0.5:
            y = 0.49

    # Final check.
    price = _price_from_yield(
        cash_flows,
        y,
        settlement_date,
        day_count,
        frequency,
    )

    if math.isfinite(price) and abs(price - dirty_price) < (
        tolerance * max(dirty_price, 1.0) + 1e-6
    ):
        return y

    return None


def _solve_tbill_ytm(
    maturity_date: date,
    price: float,
    face_value: float,
    settlement_date: date,
    day_count: str,
) -> Optional[float]:
    """Calculate zero-coupon YTM from price and maturity."""
    if price <= 0 or face_value <= 0 or maturity_date <= settlement_date:
        return None

    t = _time_factor(
        settlement_date,
        maturity_date,
        day_count,
    )

    if t <= 0:
        return None

    return (face_value / price) ** (1.0 / t) - 1.0


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
        day_count: Day-count convention. Defaults to bond's convention or
                   ACT/365.

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
        if (
            bond.day_count_convention
            and bond.day_count_convention != DayCountConvention.UNKNOWN
        ):
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
    ) or (
        coupon_rate is not None
        and coupon_rate == 0
    )

    if is_tbill:
        notes.append(
            "T-Bill / zero-coupon instrument: treated as zero-coupon"
        )

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

    # Cash flows on or before settlement have already occurred and must not
    # be included in YTM, duration, convexity, or DV01 calculations.
    future_cash_flows = [
        cf
        for cf in cash_flows
        if cf["date"] > settlement_date
    ]

    # --- Accrued interest ---
    last_coupon = None

    if future_cash_flows:
        # Previous coupon is the latest generated cash-flow date on or before
        # settlement. This avoids hard-coding cash_flows[0] for later coupons.
        previous_candidates = [
            cf["date"]
            for cf in cash_flows
            if cf["date"] <= settlement_date
        ]
        if previous_candidates:
            last_coupon = max(previous_candidates)

    # T-Bills are zero-coupon and therefore have no accrued coupon interest.
    if is_tbill:
        last_coupon = None

    ai_amount, ai_days = accrued_interest(
        coupon_rate=coupon_rate,
        face_value=face_value,
        last_coupon_date=last_coupon,
        settlement_date=settlement_date,
        coupon_frequency=frequency,
        day_count=day_count,
    )

    # --- Clean / dirty price ---
    dirty_price = None
    clean_price = None

    if bond.clean_price is not None:
        clean_price = bond.clean_price
        dirty_price = clean_price + ai_amount
    elif bond.dirty_price is not None:
        dirty_price = bond.dirty_price
        clean_price = dirty_price - ai_amount
    elif bond.price is not None:
        # Legacy fallback: price is treated as dirty when no explicit
        # clean/dirty classification is available.
        dirty_price = bond.price
        clean_price = dirty_price - ai_amount

    # --- Current yield ---
    current_yield = None

    if (
        clean_price
        and clean_price > 0
        and coupon_rate
        and not is_tbill
    ):
        # coupon_rate is already stored as a percentage
        # (e.g. 6.94 means 6.94%), so do not multiply by 100.
        current_yield = (
            coupon_rate * face_value
        ) / clean_price

        notes.append(
            f"Current yield: {current_yield:.4f}%"
        )

    # --- Calculated YTM ---
    calculated_ytm = None

    if (
        dirty_price
        and dirty_price > 0
        and future_cash_flows
    ):
        if is_tbill:
            maturity_date = future_cash_flows[-1]["date"]

            ytm_decimal = _solve_tbill_ytm(
                maturity_date=maturity_date,
                price=dirty_price,
                face_value=face_value,
                settlement_date=settlement_date,
                day_count=day_count,
            )
        else:
            ytm_decimal = solve_ytm(
                cash_flows=cash_flows,
                dirty_price=dirty_price,
                settlement_date=settlement_date,
                day_count=day_count,
                frequency=frequency,
            )

        if ytm_decimal is not None:
            calculated_ytm = ytm_decimal * 100.0

            notes.append(
                f"Calculated YTM: {calculated_ytm:.4f}%"
            )

    # --- Market YTM (retained separately) ---
    market_ytm = bond.ytm

    if market_ytm is not None:
        notes.append(
            f"Market YTM (source): {market_ytm:.4f}%"
        )

    # --- Duration / Convexity / DV01 ---
    macaulay_duration = None
    modified_duration = None
    convexity = None
    dv01 = None

    if (
        future_cash_flows
        and dirty_price
        and dirty_price > 0
        and not is_tbill
    ):
        ytm_decimal = (
            calculated_ytm / 100.0
            if calculated_ytm is not None
            else (
                market_ytm / 100.0
                if market_ytm is not None
                else 0.07
            )
        )

        (
            macaulay_duration,
            modified_duration,
            convexity,
        ) = _compute_duration_convexity(
            cash_flows=future_cash_flows,
            ytm=ytm_decimal,
            settlement_date=settlement_date,
            day_count=day_count,
            frequency=frequency,
        )

        # DV01: change in price for 1bp move in yield, per face value.
        if modified_duration is not None:
            dv01 = (
                modified_duration
                * 0.0001
                * face_value
            )

            # More precise: reprice at y +/- 1bp.
            dv01_precise = _dv01_from_pricing(
                cash_flows=future_cash_flows,
                ytm=ytm_decimal,
                settlement_date=settlement_date,
                day_count=day_count,
                face_value=face_value,
                frequency=frequency,
            )

            if dv01_precise is not None:
                dv01 = dv01_precise

        notes.append(
            f"Macaulay duration: {macaulay_duration:.4f} years"
            if macaulay_duration is not None
            else "Macaulay duration: N/A"
        )

        notes.append(
            f"Modified duration: {modified_duration:.4f}"
            if modified_duration is not None
            else "Modified duration: N/A"
        )

        notes.append(
            f"Convexity: {convexity:.4f}"
            if convexity is not None
            else "Convexity: N/A"
        )

        notes.append(
            f"DV01: {dv01:.6f}"
            if dv01 is not None
            else "DV01: N/A"
        )

    elif (
        is_tbill
        and cash_flows
        and dirty_price
        and dirty_price > 0
    ):
        # T-Bill duration = time to maturity.
        maturity_date = cash_flows[-1]["date"]
        ttm = _time_factor(
            settlement_date,
            maturity_date,
            day_count,
        )

        if ttm > 0:
            ytm_for_duration = (
                calculated_ytm / 100.0
                if calculated_ytm is not None
                else (
                    market_ytm / 100.0
                    if market_ytm is not None
                    else 0.0
                )
            )

            modified_duration = ttm / (
                1.0 + ytm_for_duration
            )

            macaulay_duration = ttm

            dv01 = (
                modified_duration
                * 0.0001
                * face_value
            )

            notes.append(
                f"T-Bill Macaulay duration (TTM): "
                f"{macaulay_duration:.4f} years"
            )

            notes.append(
                f"T-Bill DV01: {dv01:.6f}"
            )

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
    frequency: int = 2,
) -> tuple[
    Optional[float],
    Optional[float],
    Optional[float],
]:
    """Compute Macaulay duration, modified duration, and convexity.

    Coupon-bearing securities are valued using the same periodic-compounding
    convention as the YTM solver, so the risk measures are internally
    consistent with the calculated YTM.
    """
    if not cash_flows or frequency <= 0:
        return None, None, None

    exponents = _cash_flow_exponents(
        cash_flows=cash_flows,
        settlement_date=settlement_date,
        day_count=day_count,
        frequency=frequency,
    )

    if not exponents:
        return None, None, None

    rate_per_period = ytm / frequency

    if 1.0 + rate_per_period <= 0.0:
        return None, None, None

    macaulay_num = 0.0
    macaulay_den = 0.0
    convexity_num = 0.0

    for cf, exponent in exponents:
        amount = float(cf["total"])

        discount = 1.0 / (
            (1.0 + rate_per_period) ** exponent
        )
        pv = amount * discount

        t_years = exponent / frequency

        macaulay_num += t_years * pv
        macaulay_den += pv

        # Exact second-derivative form for periodic compounding.
        convexity_num += (
            exponent
            * (exponent + 1.0)
            * pv
            / (
                frequency ** 2
                * (1.0 + rate_per_period) ** 2
            )
        )

    if macaulay_den <= 0.0:
        return None, None, None

    macaulay = macaulay_num / macaulay_den
    modified = macaulay / (
        frequency * (1.0 + rate_per_period)
    )
    convexity_val = convexity_num / macaulay_den

    return (
        round(macaulay, 6),
        round(modified, 6),
        round(convexity_val, 6),
    )


def _dv01_from_pricing(
    cash_flows: list[dict[str, Any]],
    ytm: float,
    settlement_date: date,
    day_count: str,
    face_value: float,
    frequency: int = 2,
) -> Optional[float]:
    """Compute DV01 by repricing at y +/- 1bp."""
    if not cash_flows or face_value <= 0:
        return None

    bp = 0.0001

    p_minus = _price_from_yield(
        cash_flows,
        ytm - bp,
        settlement_date,
        day_count,
        frequency,
    )

    p_plus = _price_from_yield(
        cash_flows,
        ytm + bp,
        settlement_date,
        day_count,
        frequency,
    )

    if not math.isfinite(p_minus) or not math.isfinite(p_plus):
        return None

    # Current cash-flow amounts are already expressed for the bond's face
    # value, so the repricing result itself is the price change per that face.
    return round(
        abs(p_minus - p_plus) / 2.0,
        6,
    )
