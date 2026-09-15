"""Bond cash-flow schedule generation.

Generates projected cash flows for coupon-bearing government securities
and zero-coupon T-Bills.

Conventions:
  - G-Secs: semi-annual coupons (frequency = 2) unless overridden.
  - T-Bills: single zero-coupon payment at maturity.
  - Day-count: ACT/ACT where available, else ACT/365.

All calculations are purely computational; no external data is needed.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional


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
      - period: int (0 = issue, 1..n = coupon periods)
      - date: date of the cash flow
      - coupon: float (coupon payment amount; 0 for T-Bills)
      - principal: float (principal repayment; 0 except at maturity)
      - total: float (coupon + principal)

    For T-Bills (coupon_rate == 0):
      - A single cash flow at maturity: principal = face_value.

    For coupon-bearing securities:
      - Coupons are generated at each coupon date from issue to maturity.
      - The final cash flow includes the last coupon + principal.

    If issue_date or maturity_date is None, returns an empty list.
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
        # Fallback: assume issue_date = first coupon date derived backwards
        # from maturity. Without issue_date we cannot reliably schedule
        # coupons, so return only the maturity cash flow as a fallback.
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

    coupon_amount = face_value * (coupon_rate / 100.0) / coupon_frequency

    # Build coupon date schedule
    # Determine the first coupon date: the first coupon_date after issue_date.
    # We walk backwards/forwards from maturity using the frequency.
    periods: list[int] = []
    current = maturity_date
    period = 0
    while current >= issue_date:
        periods.append((period, current))
        # Step back one coupon period
        current = _step_back(current, coupon_frequency)
        period += 1

    # Keep only dates on/after issue_date
    periods = [(p, d) for p, d in periods if d >= issue_date]
    if not periods:
        # Fallback: single maturity cash flow
        return [
            {
                "period": 0,
                "date": maturity_date,
                "coupon": coupon_amount,
                "principal": face_value,
                "total": coupon_amount + face_value,
            }
        ]

    # Reverse so earliest first
    periods.reverse()

    cash_flows: list[dict[str, Any]] = []
    for i, (period, cf_date) in enumerate(periods):
        is_final = cf_date == maturity_date
        c = coupon_amount if not is_final else coupon_amount
        principal = face_value if is_final else 0.0
        total = c + principal
        cash_flows.append(
            {
                "period": i + 1,  # 1-based period index
                "date": cf_date,
                "coupon": round(c, 6),
                "principal": round(principal, 6),
                "total": round(total, 6),
            }
        )

    return cash_flows


def accrued_interest(
    coupon_rate: Optional[float],
    face_value: float,
    last_coupon_date: Optional[date],
    settlement_date: date,
    coupon_frequency: int = 2,
    day_count: str = "ACT/365",
) -> tuple[float, int]:
    """Compute accrued interest from last coupon to settlement.

    Returns (accrued_interest_amount, accrued_days).

    For zero-coupon instruments (coupon_rate == 0): returns (0.0, 0).

    Day-count conventions:
      - ACT/365  : accrued = coupon * (actual days / 365)
      - ACT/ACT  : accrued = coupon * (actual days / actual days in
                    the coupon period)
      - ACT/360  : accrued = coupon * (actual days / 360)

    If last_coupon_date is None, returns (0.0, 0) as a safe fallback.
    """
    if coupon_rate is None or coupon_rate == 0:
        return 0.0, 0

    if not last_coupon_date:
        return 0.0, 0

    if settlement_date <= last_coupon_date:
        return 0.0, 0

    coupon_amount = face_value * (coupon_rate / 100.0) / coupon_frequency
    actual_days = (settlement_date - last_coupon_date).days

    if day_count == "ACT/365":
        accrued = coupon_amount * actual_days / 365.0
    elif day_count == "ACT/360":
        accrued = coupon_amount * actual_days / 360.0
    elif day_count == "ACT/ACT":
        # Actual days in the coupon period (next coupon - last coupon)
        # If we don't have next coupon, approximate with frequency.
        next_coupon = _next_coupon(last_coupon_date, coupon_frequency)
        period_days = (next_coupon - last_coupon_date).days
        if period_days <= 0:
            period_days = 365.0 / coupon_frequency
        accrued = coupon_amount * actual_days / period_days
    else:
        accrued = coupon_amount * actual_days / 365.0

    return round(accrued, 6), actual_days


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _step_back(d: date, frequency: int) -> date:
    """Step back one coupon period from date d.

    Uses a best-effort monthly/semi-annual stepping:
      - frequency == 2: ~6 months back
      - frequency == 4: ~3 months back
      - frequency == 12: ~1 month back
      - otherwise: 365/frequency days back
    """
    if frequency == 2:
        return _shift_months(d, -6)
    if frequency == 4:
        return _shift_months(d, -3)
    if frequency == 12:
        return _shift_months(d, -1)
    days = int(365.0 / frequency)
    return d - timedelta(days=days)


def _next_coupon(d: date, frequency: int) -> date:
    """Step forward one coupon period from date d."""
    return _shift_months(d, int(12 / frequency))


def _shift_months(d: date, months: int) -> date:
    """Shift a date by a number of months, capping at month end."""
    total_months = d.month - 1 + months  # 0-based month
    year = d.year + total_months // 12
    month = total_months % 12 + 1
    # Cap day at month end
    import calendar as _cal
    max_day = _cal.monthrange(year, month)[1]
    day = min(d.day, max_day)
    return date(year, month, day)
