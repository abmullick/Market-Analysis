"""
Bond cash-flow schedule generation.

Generates projected cash flows for coupon-bearing government securities
and zero-coupon T-Bills.

Conventions:
  - G-Secs / SDLs: typically semi-annual coupons (frequency = 2).
  - T-Bills: single zero-coupon payment at maturity.
  - Supported day-count conventions:
      * 30/360
      * ACT/ACT
      * ACT/365
      * ACT/360

All calculations are purely computational; no external data is needed.

Strict mode (``build_cash_flow_schedule``) is used by the analytics engine:
it never assumes coupon frequency, face value, payment dates, or day-count
convention. A schedule is produced only when every required term is present
in the source data; otherwise the exact missing term is reported back so the
UI can explain why cash flows are unavailable.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional, Tuple


# Coupon frequencies with a well-defined calendar step. Anything else
# (e.g. 7 payments/year) has no standard month stepping and is refused
# rather than approximated.
SUPPORTED_FREQUENCIES = (1, 2, 4, 12)


# ---------------------------------------------------------------------------
# Core cash-flow generation
# ---------------------------------------------------------------------------


def generate_cash_flows(
    issue_date: Optional[date],
    maturity_date: Optional[date],
    coupon_rate: Optional[float],     # percent per annum, e.g. 7.15 = 7.15%
    coupon_frequency: int = 2,        # 2 = semi-annual (G-Sec default)
    face_value: float = 100.0,        # per 100 par
    settlement_date: date | None = None,
    day_count: str = "ACT/365",
) -> list[dict[str, Any]]:
    """Generate projected cash flows for a bond.

    Returns a list of dicts with keys:
      - period: int (1..n = coupon periods)
      - date: date of the cash flow
      - coupon: float (coupon payment amount; 0 for T-Bills)
      - principal: float (principal repayment; 0 except at maturity)
      - total: float (coupon + principal)

    For T-Bills (coupon_rate == 0):
      - A single cash flow at maturity: principal = face_value.

    For coupon-bearing securities:
      - Coupons are generated at each coupon date from issue to maturity.
      - The final cash flow includes the last coupon + principal.

    If issue_date or maturity_date is None, a safe fallback is used.
    """
    if not maturity_date:
        return []

    # T-Bill / zero-coupon handling
    if coupon_rate is None or coupon_rate == 0:
        cf_date = maturity_date
        return [
            {
                "period": 0,
                "date": cf_date,
                "coupon": 0.0,
                "principal": face_value,
                "total": face_value,
            }
        ]

    if not issue_date:
        # Without issue_date we cannot reliably reconstruct the coupon
        # schedule from the available master data.
        return [
            {
                "period": 0,
                "date": maturity_date,
                "coupon": 0.0,
                "principal": face_value,
                "total": face_value,
                "note": "issue_date unknown; only maturity cash flow returned",
            }
        ]

    if issue_date > maturity_date:
        return []

    if coupon_frequency <= 0:
        coupon_frequency = 2

    coupon_amount = (
        face_value
        * (coupon_rate / 100.0)
        / coupon_frequency
    )

    # Build coupon date schedule backwards from maturity.
    #
    # For example, for a semi-annual bond maturing on 11-May:
    #   11-May
    #   11-Nov
    #   11-May
    #   ...
    #
    # This preserves the actual coupon-day anchor rather than using an
    # approximate fixed number of days.
    periods: list[tuple[int, date]] = []
    current = maturity_date
    period = 0

    while current >= issue_date:
        periods.append((period, current))

        current = _step_back(
            current,
            coupon_frequency,
        )
        period += 1

        # Defensive guard against an invalid/custom frequency implementation.
        if period > 1000:
            break

    periods = [
        (p, d)
        for p, d in periods
        if d >= issue_date
    ]

    if not periods:
        return [
            {
                "period": 0,
                "date": maturity_date,
                "coupon": coupon_amount,
                "principal": face_value,
                "total": coupon_amount + face_value,
            }
        ]

    # Reverse so earliest cash flow is first.
    periods.reverse()

    cash_flows: list[dict[str, Any]] = []

    for i, (_, cf_date) in enumerate(periods):
        is_final = cf_date == maturity_date

        coupon = coupon_amount
        principal = face_value if is_final else 0.0
        total = coupon + principal

        cash_flows.append(
            {
                "period": i + 1,
                "date": cf_date,
                "coupon": round(coupon, 6),
                "principal": round(principal, 6),
                "total": round(total, 6),
            }
        )

    return cash_flows


# ---------------------------------------------------------------------------
# Strict (source-validated) schedule builder
# ---------------------------------------------------------------------------


def build_cash_flow_schedule(
    *,
    coupon_rate: Optional[float],
    coupon_frequency: Optional[int],
    anchor_date: Optional[date],
    final_date: Optional[date],
    is_zero_coupon: bool = False,
    allow_maturity_anchor: bool = False,
) -> Tuple[Optional[list[dict[str, Any]]], str, Optional[str]]:
    """Build a cash-flow schedule using ONLY source-provided terms.

    Returns ``(cash_flows, source_label, unavailable_reason)``:

    - ``cash_flows`` is ``None`` when the schedule cannot be produced; in
      that case ``unavailable_reason`` states exactly which term is missing.
    - ``source_label`` is ``"calculated"`` for generated schedules (the only
      mode this builder supports) and ``None`` when nothing was produced.

    Rules (no fabrication):
      - Zero-coupon instruments (T-Bills) need only ``final_date``.
      - Coupon-bearing instruments need: a positive coupon rate, a supported
        frequency (1/2/4/12), an anchor date (issue or first interest-payment
        date from the source) and a final date (redemption or maturity date
        from the source).
      - ``allow_maturity_anchor`` permits the government-security convention
        of stepping the coupon calendar backwards from the published maturity
        date when no issue/interest-start date was published.
      - Amounts are expressed per 100 par so they line up with the quoted
        (percent-of-par) price convention used everywhere in this app.
    """
    if is_zero_coupon:
        if final_date is None:
            return None, None, "Maturity / redemption date not published."
        return (
            [
                {
                    "period": 1,
                    "date": final_date,
                    "coupon": 0.0,
                    "principal": 100.0,
                    "total": 100.0,
                    "source": "calculated",
                }
            ],
            "calculated",
            None,
        )

    if coupon_rate is None:
        return None, None, "Coupon rate not published for this ISIN."
    if coupon_rate <= 0:
        return None, None, "Coupon rate is not positive."
    if coupon_frequency is None:
        return (
            None,
            None,
            "Coupon frequency not published (cannot assume annual or semi-annual).",
        )
    if coupon_frequency not in SUPPORTED_FREQUENCIES:
        return (
            None,
            None,
            f"Coupon frequency {coupon_frequency}/year is not a supported "
            "payment cycle (1, 2, 4 or 12 per year).",
        )
    if anchor_date is None and not allow_maturity_anchor:
        return (
            None,
            None,
            "Interest payment start / issue date not published (cannot "
            "anchor the coupon calendar).",
        )
    if final_date is None:
        return None, None, "Maturity / redemption date not published."
    if anchor_date is not None and final_date <= anchor_date:
        return (
            None,
            None,
            "Maturity / redemption date is not after the interest start date.",
        )

    if anchor_date is None:
        # Government convention: walk back a bounded window from maturity
        # (50 years) so historical coupons exist for accrued-interest logic.
        anchor_date = date(final_date.year - 50, final_date.month, final_date.day)

    flows = generate_cash_flows(
        issue_date=anchor_date,
        maturity_date=final_date,
        coupon_rate=coupon_rate,
        coupon_frequency=coupon_frequency,
        face_value=100.0,  # per 100 par; quoted prices use the same basis
        settlement_date=None,
        day_count="ACT/365",
    )

    if not flows:
        return None, None, "Coupon calendar could not be generated from the published terms."

    for row in flows:
        row["source"] = "calculated"

    return flows, "calculated", None


# ---------------------------------------------------------------------------
# Accrued interest
# ---------------------------------------------------------------------------


def accrued_interest(
    coupon_rate: Optional[float],
    face_value: float,
    last_coupon_date: Optional[date],
    settlement_date: date,
    coupon_frequency: int = 2,
    day_count: str = "ACT/365",
) -> tuple[float, int]:
    """Compute accrued interest from the last coupon date to settlement.

    Returns:
        (accrued_interest_amount, accrued_days)

    For zero-coupon instruments:
        returns (0.0, 0).

    Supported conventions:
      - 30/360  : 30-day months, 360-day year.
      - ACT/365  : actual days / 365.
      - ACT/360  : actual days / 360.
      - ACT/ACT  : actual days / actual coupon-period days.

    For 30/360, the accrual period ends on the day before settlement.
    """
    if coupon_rate is None or coupon_rate == 0:
        return 0.0, 0

    if not last_coupon_date:
        return 0.0, 0

    if settlement_date <= last_coupon_date:
        return 0.0, 0

    if coupon_frequency <= 0:
        coupon_frequency = 2

    coupon_amount = (
        face_value
        * (coupon_rate / 100.0)
        / coupon_frequency
    )

    if day_count == "30/360":
        # Indian bond-market accrual is measured up to the day before
        # settlement for the broken coupon period.
        accrual_end = settlement_date - timedelta(days=1)

        d1 = min(last_coupon_date.day, 30)
        d2 = min(accrual_end.day, 30)

        accrual_days = (
            360 * (accrual_end.year - last_coupon_date.year)
            + 30 * (accrual_end.month - last_coupon_date.month)
            + (d2 - d1)
        )

        if accrual_days <= 0:
            return 0.0, 0

        # For a semi-annual coupon, the coupon period is 180 days
        # under the 30/360 convention. More generally:
        # 360 / coupon_frequency.
        period_days = 360.0 / coupon_frequency

        accrued = (
            coupon_amount
            * accrual_days
            / period_days
        )

        return round(accrued, 6), accrual_days

    actual_days = (
        settlement_date - last_coupon_date
    ).days

    if day_count == "ACT/365":
        accrued = (
            coupon_amount
            * actual_days
            / 365.0
        )

    elif day_count == "ACT/360":
        accrued = (
            coupon_amount
            * actual_days
            / 360.0
        )

    elif day_count == "ACT/ACT":
        # Actual days in the coupon period.
        next_coupon = _next_coupon(
            last_coupon_date,
            coupon_frequency,
        )

        period_days = (
            next_coupon - last_coupon_date
        ).days

        if period_days <= 0:
            period_days = 365.0 / coupon_frequency

        accrued = (
            coupon_amount
            * actual_days
            / period_days
        )

    else:
        # Safe fallback for unknown convention.
        accrued = (
            coupon_amount
            * actual_days
            / 365.0
        )

    return round(accrued, 6), actual_days


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _step_back(
    d: date,
    frequency: int,
) -> date:
    """Step back one coupon period from date d.

    Uses calendar-month stepping for standard periodic coupon frequencies:

      - frequency == 2  -> 6 months
      - frequency == 4  -> 3 months
      - frequency == 12 -> 1 month
      - otherwise       -> 365 / frequency day approximation
    """
    if frequency == 2:
        return _shift_months(d, -6)

    if frequency == 4:
        return _shift_months(d, -3)

    if frequency == 12:
        return _shift_months(d, -1)

    days = int(365.0 / frequency)

    if days <= 0:
        days = 1

    return d - timedelta(days=days)


def _next_coupon(
    d: date,
    frequency: int,
) -> date:
    """Step forward one coupon period from date d."""
    if frequency <= 0:
        frequency = 2

    months = int(12 / frequency)

    if months <= 0:
        months = 1

    return _shift_months(
        d,
        months,
    )


def _shift_months(
    d: date,
    months: int,
) -> date:
    """Shift a date by a number of calendar months.

    The day of month is preserved where possible and capped at
    the last valid day of the destination month.
    """
    total_months = (
        d.month - 1 + months
    )

    year = (
        d.year
        + total_months // 12
    )

    month = (
        total_months % 12
        + 1
    )

    import calendar as _cal

    max_day = _cal.monthrange(
        year,
        month,
    )[1]

    day = min(
        d.day,
        max_day,
    )

    return date(
        year,
        month,
        day,
    )