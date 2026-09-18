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
    _step_back,
    accrued_interest,
    build_cash_flow_schedule,
    generate_cash_flows,
)
from backend.services.bonds.bond_normalizer import parse_date, parse_float


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
    frequency: int,
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
            previous_coupon = _step_back(
                next_coupon,
                frequency,
            )

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
        frequency,
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

    Metrics are computed ONLY from source-validated inputs. When a required
    term (coupon rate, coupon frequency, payment dates, day count, price) is
    missing, the affected metric is left ``None`` and a human-readable reason
    is recorded in ``unavailable_metrics`` — nothing is fabricated.

    Args:
        bond: Normalized Bond record (master + market observation).
        settlement_date: Date for analytics. Defaults to trade_date or today.
        day_count: Day-count convention. Defaults to the bond's published
                   convention, falling back to ACT/365 when the source does
                   not publish one.

    Returns:
        AnalyticsResult with calculated_ytm (independent of market YTM),
        market_ytm (retained separately from source), current_yield,
        accrued_interest, cash_flows, durations, convexity, DV01, plus
        ``unavailable_metrics`` explanations and ``cash_flow_source``.
    """
    notes: list[str] = []
    unavailable: dict[str, str] = {}

    # --- Settlement date ---
    if settlement_date is None:
        if bond.trade_date:
            settlement_date = bond.trade_date
        else:
            settlement_date = date.today()

    # --- Day count ---
    day_count_published = (
        bond.day_count_convention is not None
        and bond.day_count_convention != DayCountConvention.UNKNOWN
    )
    if day_count is None:
        if day_count_published:
            day_count = bond.day_count_convention.value
        else:
            day_count = "ACT/365"

    notes.append(f"Settlement date: {settlement_date}")
    notes.append(f"Day count: {day_count}")
    if day_count_published:
        notes.append("Day count published by the source.")
    else:
        notes.append(
            "Day count not published by the source; ACT/365 applied for "
            "time fractions."
        )

    # All price-based metrics use the per-100-par basis (quoted prices are
    # percent of par). Face value only matters for absolute cash amounts and
    # is reported separately when it differs from 100.
    if bond.face_value is not None and abs(bond.face_value - 100.0) > 1e-9:
        notes.append(
            f"Source face value: {bond.face_value:g} per unit; analytics "
            "expressed per 100 par."
        )

    # --- Coupon / frequency policy ---
    coupon_rate = bond.coupon_rate
    instrument_value = (
        bond.instrument_type.value if bond.instrument_type is not None else ""
    )
    is_government = instrument_value in ("G-Sec", "SDL")

    is_tbill = (
        instrument_value == "T-Bill"
        or (coupon_rate is not None and coupon_rate == 0)
    )

    frequency: Optional[int] = bond.coupon_frequency
    if frequency is None and not is_tbill and is_government:
        # Indian central/state government securities pay semi-annual coupons
        # (documented market convention; module docstring). This is applied
        # ONLY to government securities and is disclosed in the notes.
        frequency = 2
        notes.append(
            "Coupon frequency not published; semi-annual applied per Indian "
            "government-bond market convention."
        )

    if is_tbill:
        notes.append(
            "T-Bill / zero-coupon instrument: treated as zero-coupon"
        )

    # --- Cash flow schedule (source-provided first, then strictly calculated) ---
    cash_flow_source: Optional[str] = None
    schedule_reason: Optional[str] = None
    cash_flows: Optional[list[dict[str, Any]]] = None

    source_rows = bond.cash_flow_schedule or []
    if source_rows:
        # Source amounts are per the bond's actual face value; the schedule
        # is expressed per 100 par to line up with quoted prices.
        face_scale = (bond.face_value / 100.0) if bond.face_value else 1.0
        mapped: list[dict[str, Any]] = []
        for idx, ev in enumerate(source_rows, start=1):
            ev_date = parse_date(getattr(ev, "due_date", None) or "")
            if ev_date is None:
                ev_date = parse_date(getattr(ev, "payment_date", None) or "")
            amount = parse_float(str(getattr(ev, "amount_payable", "") or ""))
            if ev_date is None or amount is None or face_scale <= 0:
                continue
            amount_per_100 = amount / face_scale
            ev_type = (getattr(ev, "event_type", "") or "").lower()
            is_interest = "interest" in ev_type
            is_principal = ("redemption" in ev_type) or ("principal" in ev_type)
            mapped.append(
                {
                    "period": idx,
                    "date": ev_date,
                    "coupon": amount_per_100 if is_interest and not is_principal else 0.0,
                    "principal": amount_per_100 if is_principal else 0.0,
                    "total": amount_per_100,
                    "source": "cdsl",
                }
            )
        if mapped:
            cash_flows = sorted(mapped, key=lambda r: r["date"])
            cash_flow_source = "source"
            notes.append(
                "Cash-flow schedule provided by CDSL (source-published)."
            )
        else:
            schedule_reason = (
                "CDSL published a cash-flow schedule but its rows could not "
                "be parsed into dated payments."
            )

    if cash_flows is None and schedule_reason is None:
        anchor_date = bond.interest_start_date or bond.issue_date
        final_date = bond.redemption_date or bond.maturity_date
        # Government securities anchor their coupon calendar on the maturity
        # date (project convention); corporates must publish an anchor.
        maturity_anchored = is_government or is_tbill
        if anchor_date is None and not maturity_anchored:
            schedule_reason = (
                "Interest payment start / issue date not published (cannot "
                "anchor the coupon calendar)."
            )
        else:
            built_flows, built_source, built_reason = build_cash_flow_schedule(
                coupon_rate=coupon_rate,
                coupon_frequency=frequency,
                anchor_date=anchor_date,
                final_date=final_date,
                is_zero_coupon=is_tbill,
                allow_maturity_anchor=maturity_anchored and anchor_date is None,
            )
            if built_flows:
                cash_flows = built_flows
                cash_flow_source = built_source
                if not is_tbill and anchor_date is None:
                    notes.append(
                        "Coupon dates generated backwards from the published "
                        "maturity date (government security convention)."
                    )
            else:
                schedule_reason = built_reason

    if cash_flows is None:
        if schedule_reason is None:
            schedule_reason = "Cash-flow schedule unavailable."
        unavailable["cash_flows"] = schedule_reason

    # Cash flows on or before settlement have already occurred and must not
    # be included in YTM, duration, convexity, or DV01 calculations.
    future_cash_flows = [
        cf
        for cf in (cash_flows or [])
        if cf["date"] > settlement_date
    ]

    # --- Accrued interest (only when a real previous coupon date exists) ---
    ai_amount: Optional[float] = None
    ai_days: Optional[int] = None

    if is_tbill:
        unavailable["accrued_interest"] = (
            "Zero-coupon instrument: there is no coupon accrual."
        )
    elif cash_flows is None:
        unavailable["accrued_interest"] = schedule_reason
    else:
        previous_candidates = [
            cf["date"]
            for cf in cash_flows
            if cf["date"] <= settlement_date
        ]
        last_coupon = max(previous_candidates) if previous_candidates else None
        if last_coupon is None:
            unavailable["accrued_interest"] = (
                "Settlement precedes the first coupon of the published schedule."
            )
        else:
            ai_amount, ai_days = accrued_interest(
                coupon_rate=coupon_rate,
                face_value=100.0,
                last_coupon_date=last_coupon,
                settlement_date=settlement_date,
                coupon_frequency=frequency or 2,
                day_count=day_count,
            )

    # --- Clean / dirty price ---
    dirty_price = None
    clean_price = None

    if bond.clean_price is not None:
        clean_price = bond.clean_price
        dirty_price = clean_price + (ai_amount or 0.0)
    elif bond.dirty_price is not None:
        dirty_price = bond.dirty_price
        clean_price = dirty_price - (ai_amount or 0.0)
    elif bond.price is not None:
        # Legacy fallback: price is treated as dirty when no explicit
        # clean/dirty classification is available.
        dirty_price = bond.price
        if ai_amount is not None:
            clean_price = dirty_price - ai_amount

    if dirty_price is None or dirty_price <= 0:
        price_reason = (
            "No usable market price (LTP/weighted average price) for this bond."
        )
        unavailable["current_yield"] = price_reason
        unavailable["calculated_ytm"] = price_reason
        unavailable["macaulay_duration"] = price_reason
        unavailable["modified_duration"] = price_reason
        unavailable["convexity"] = price_reason
        unavailable["dv01"] = price_reason

    # --- Current yield ---
    current_yield = None

    if is_tbill:
        unavailable["current_yield"] = (
            "Zero-coupon instrument: current yield is not applicable."
        )
    elif coupon_rate is None or coupon_rate <= 0:
        if "current_yield" not in unavailable:
            unavailable["current_yield"] = (
                "Coupon rate not published for this ISIN."
            )
    elif clean_price and clean_price > 0:
        # coupon_rate is already stored as a percentage
        # (e.g. 6.94 means 6.94%), so do not multiply by 100.
        # Per-100-par basis: annual coupon per 100 = coupon_rate, so the
        # yield in percent is coupon_rate / clean_price * 100.
        current_yield = coupon_rate * 100.0 / clean_price

        notes.append(
            f"Current yield: {current_yield:.4f}%"
        )
    elif dirty_price and dirty_price > 0:
        # Accrued interest could not be derived, so no clean price exists;
        # fall back to the traded price rather than withholding the metric.
        current_yield = coupon_rate * 100.0 / dirty_price

        notes.append(
            f"Current yield: {current_yield:.4f}% "
            "(clean price unavailable; traded price used)"
        )

    # --- Calculated YTM ---
    calculated_ytm = None

    if dirty_price and dirty_price > 0 and cash_flows is not None:
        if is_tbill:
            if future_cash_flows:
                maturity_date = future_cash_flows[-1]["date"]

                ytm_decimal = _solve_tbill_ytm(
                    maturity_date=maturity_date,
                    price=dirty_price,
                    face_value=100.0,
                    settlement_date=settlement_date,
                    day_count=day_count,
                )
            else:
                ytm_decimal = None
        elif any(cf.get("coupon", 0) > 0 for cf in future_cash_flows):
            # A coupon-bearing YTM requires at least one future coupon; a
            # maturity-only placeholder must never be priced as a YTM.
            ytm_decimal = solve_ytm(
                cash_flows=cash_flows,
                dirty_price=dirty_price,
                settlement_date=settlement_date,
                day_count=day_count,
                frequency=frequency or 2,
            )
        else:
            ytm_decimal = None

        if ytm_decimal is not None and math.isfinite(ytm_decimal):
            # Plausibility guard: suppress nonsensical solves caused by
            # degenerate inputs rather than displaying them.
            if -0.5 <= ytm_decimal <= 2.0:
                calculated_ytm = ytm_decimal * 100.0

                notes.append(
                    f"Calculated YTM: {calculated_ytm:.4f}%"
                )
            else:
                unavailable["calculated_ytm"] = (
                    "Solved YTM fell outside a plausible range and was "
                    "suppressed rather than displayed."
                )
        elif "calculated_ytm" not in unavailable:
            unavailable["calculated_ytm"] = (
                "YTM could not be solved from the available price and schedule."
            )
    elif "calculated_ytm" not in unavailable:
        if cash_flows is None and schedule_reason:
            unavailable["calculated_ytm"] = schedule_reason
        elif is_tbill and not future_cash_flows:
            unavailable["calculated_ytm"] = (
                "T-Bill has already matured; no future cash flow to price."
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

    if dirty_price and dirty_price > 0 and future_cash_flows and not is_tbill:
        # Discounting yield: the independently calculated YTM when available,
        # otherwise the source-reported YTM. A fabricated default (e.g. 7%)
        # is never used — without either yield the risk metrics are skipped.
        if calculated_ytm is not None:
            ytm_decimal = calculated_ytm / 100.0
        elif market_ytm is not None:
            ytm_decimal = market_ytm / 100.0
        else:
            ytm_decimal = None
            unavailable["macaulay_duration"] = (
                "Requires a calculated or source-reported YTM; neither is "
                "available for this bond."
            )

        if ytm_decimal is not None:
            (
                macaulay_duration,
                modified_duration,
                convexity,
            ) = _compute_duration_convexity(
                cash_flows=future_cash_flows,
                ytm=ytm_decimal,
                settlement_date=settlement_date,
                day_count=day_count,
                frequency=frequency or 2,
            )

            # DV01: change in price for 1bp move in yield, per 100 par.
            if modified_duration is not None:
                dv01 = (
                    modified_duration
                    * 0.0001
                    * 100.0
                )

                # More precise: reprice at y +/- 1bp (same per-100 basis).
                dv01_precise = _dv01_from_pricing(
                    cash_flows=future_cash_flows,
                    ytm=ytm_decimal,
                    settlement_date=settlement_date,
                    day_count=day_count,
                    face_value=100.0,
                    frequency=frequency or 2,
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
                    else None
                )
            )

            if ytm_for_duration is None:
                unavailable["macaulay_duration"] = (
                    "Requires a calculated or source-reported YTM; neither "
                    "is available for this bond."
                )
            else:
                modified_duration = ttm / (
                    1.0 + ytm_for_duration
                )

                macaulay_duration = ttm

                dv01 = (
                    modified_duration
                    * 0.0001
                    * 100.0
                )

                notes.append(
                    f"T-Bill Macaulay duration (TTM): "
                    f"{macaulay_duration:.4f} years"
                )

                notes.append(
                    f"T-Bill DV01: {dv01:.6f}"
                )

    # Any risk metric still missing without a reason: explain the gap.
    _risk_values = {
        "macaulay_duration": macaulay_duration,
        "modified_duration": modified_duration,
        "convexity": convexity,
        "dv01": dv01,
    }
    for metric, value in _risk_values.items():
        if value is None and metric not in unavailable:
            if cash_flows is None and schedule_reason:
                unavailable[metric] = schedule_reason
            else:
                unavailable[metric] = (
                    "Requires a validated coupon schedule, a market price "
                    "and a yield; one or more are missing for this bond."
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
        unavailable_metrics=unavailable if unavailable else None,
        cash_flow_source=cash_flow_source,
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
