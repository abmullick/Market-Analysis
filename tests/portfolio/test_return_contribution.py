"""Tests for the additive Return Contribution (performance attribution).

Methodology under test (see ``backend/services/portfolio/mf_analysis.py``):

    contribution_i = sum_t w_i * r_i(t) * V(t-1)

where ``w_i`` is the fund's constant target weight, ``r_i(t)`` its daily
return over the portfolio's common NAV dates, and ``V(t-1)`` the portfolio's
cumulative growth factor just before day ``t`` (V(0) = 1). Because the
existing portfolio daily return is ``R_p(t) = sum_i w_i * r_i(t)``, the
contributions telescope exactly:

    sum_i contribution_i = sum_t R_p(t) * V(t-1) = V(T) - 1

i.e. the sum of fund contributions equals the portfolio's total return over
the common analysis period. The documented reconciliation tolerance is
1e-9 (float-rounding noise only; the construction is exactly additive).
"""

import math
from datetime import date, timedelta

import pytest

from backend.models.mutual_fund import NAVRecord
from backend.services.portfolio.mf_analysis import (
    PortfolioAnalysisError,
    calculate_portfolio_analysis,
)

RECONCILIATION_TOLERANCE = 1e-9
DAYS = 40  # common observation count for success cases (> MIN_COMMON_OBSERVATIONS)


def make_navs(values, start=(2020, 1, 1)):
    d0 = date(*start)
    return [
        NAVRecord(date=(d0 + timedelta(days=i)).isoformat(), nav=float(v))
        for i, v in enumerate(values)
    ]


def growing_navs(n, daily=0.01, start_nav=100.0, start=(2020, 1, 1)):
    v = start_nav
    values = []
    for _ in range(n):
        values.append(v)
        v *= 1 + daily
    return make_navs(values, start)


def declining_navs(n, daily=0.01, start_nav=100.0, start=(2020, 1, 1)):
    v = start_nav
    values = []
    for _ in range(n):
        values.append(v)
        v *= 1 - daily
    return make_navs(values, start)


def constant_navs(n, nav=100.0, start=(2020, 1, 1)):
    return make_navs([nav] * n, start)


def run(funds):
    return calculate_portfolio_analysis(
        [{"scheme_code": c, "allocation": a, "navs": navs} for c, a, navs in funds]
    )


def by_code(rc, code):
    return next(e for e in rc.contributions if e.scheme_code == code)


# ---------------------------------------------------------------------------
# 1./2. Equal-weight and unequal allocations (positive contributions)
# ---------------------------------------------------------------------------


def test_equal_weight_positive():
    result = run([("A", 50, growing_navs(DAYS)), ("B", 50, constant_navs(DAYS))])
    rc = result.return_contribution
    assert rc is not None
    entries = {e.scheme_code: e for e in rc.contributions}
    # Flat fund contributes nothing.
    assert entries["B"].contribution == pytest.approx(0.0, abs=RECONCILIATION_TOLERANCE)
    # Portfolio daily return is a constant 0.005, so fund A's contribution
    # telescopes to exactly the portfolio total return: (1.005^39) - 1.
    expected = (1.005 ** (DAYS - 1)) - 1
    assert entries["A"].contribution == pytest.approx(expected, abs=RECONCILIATION_TOLERANCE)
    assert rc.total_contribution == pytest.approx(
        result.metrics.total_return, abs=RECONCILIATION_TOLERANCE
    )


def test_unequal_allocations():
    result = run([("A", 70, growing_navs(DAYS)), ("B", 30, constant_navs(DAYS))])
    rc = result.return_contribution
    entries = {e.scheme_code: e for e in rc.contributions}
    expected = (1.007 ** (DAYS - 1)) - 1  # portfolio daily return = 0.7 * 0.01
    assert entries["A"].contribution == pytest.approx(expected, abs=RECONCILIATION_TOLERANCE)
    assert entries["B"].contribution == pytest.approx(0.0, abs=RECONCILIATION_TOLERANCE)
    assert rc.total_contribution == pytest.approx(
        result.metrics.total_return, abs=RECONCILIATION_TOLERANCE
    )


# ---------------------------------------------------------------------------
# 3./4./5./6. Mixed positive/negative contributions + zero-allocation fund
# ---------------------------------------------------------------------------


def test_mixed_contributions_and_zero_allocation():
    result = run(
        [
            ("A", 60, growing_navs(DAYS, daily=0.02)),
            ("B", 30, declining_navs(DAYS, daily=0.01)),
            ("C", 10, constant_navs(DAYS)),
            ("Z", 0, growing_navs(DAYS)),  # zero-allocation fund
        ]
    )
    rc = result.return_contribution
    codes = [e.scheme_code for e in rc.contributions]
    # Zero-allocation fund is excluded from the contribution table
    # (consistent with its exclusion from all portfolio calculations).
    assert "Z" not in codes
    a, b, c = by_code(rc, "A"), by_code(rc, "B"), by_code(rc, "C")
    assert a.contribution > 0
    assert b.contribution < 0
    assert c.contribution == pytest.approx(0.0, abs=RECONCILIATION_TOLERANCE)
    # Ordering: largest positive first, negative contributors last.
    assert rc.contributions[0].scheme_code == "A"
    assert rc.contributions[-1].scheme_code == "B"
    # Reconciliation.
    assert rc.total_contribution == pytest.approx(
        result.metrics.total_return, abs=RECONCILIATION_TOLERANCE
    )
    assert abs(rc.reconciliation_difference) < RECONCILIATION_TOLERANCE


def test_contribution_differs_from_allocation_times_fund_return():
    result = run(
        [
            ("A", 60, growing_navs(DAYS, daily=0.02)),
            ("B", 40, declining_navs(DAYS, daily=0.01)),
        ]
    )
    rc = result.return_contribution
    a, b = by_code(rc, "A"), by_code(rc, "B")
    # The naive "allocation x fund total return" shortcut ignores compounding
    # and daily rebalancing; it does NOT reconcile with the portfolio return.
    naive_total = 0.60 * a.fund_return + 0.40 * b.fund_return
    assert abs(naive_total - result.metrics.total_return) > 1e-3
    # The implemented wealth-relative contribution DOES reconcile exactly.
    assert rc.total_contribution == pytest.approx(
        result.metrics.total_return, abs=RECONCILIATION_TOLERANCE
    )
    assert a.contribution != pytest.approx(0.60 * a.fund_return, abs=1e-3)


def test_all_negative_contributions():
    result = run(
        [
            ("A", 50, declining_navs(DAYS, daily=0.01)),
            ("B", 50, declining_navs(DAYS, daily=0.02)),
        ]
    )
    rc = result.return_contribution
    assert all(e.contribution < 0 for e in rc.contributions)
    # The deeper decliner (B) is the largest drag and sorts last.
    assert rc.contributions[-1].scheme_code == "B"
    assert rc.total_contribution == pytest.approx(
        result.metrics.total_return, abs=RECONCILIATION_TOLERANCE
    )
    # Negative shares: each fund's share of the total negative contribution.
    neg_total = sum(e.contribution for e in rc.contributions)
    for e in rc.contributions:
        assert e.contribution_percentage == pytest.approx(
            e.contribution / abs(neg_total), abs=1e-9
        )


# ---------------------------------------------------------------------------
# 7. Portfolio return near zero — no fabricated/misleading percentages
# ---------------------------------------------------------------------------


def test_portfolio_return_near_zero():
    result = run(
        [
            ("A", 50, growing_navs(DAYS, daily=0.01)),
            ("B", 50, declining_navs(DAYS, daily=0.01)),
        ]
    )
    rc = result.return_contribution
    assert abs(rc.total_contribution) < 1e-12
    assert abs(result.metrics.total_return) < 1e-12
    a, b = by_code(rc, "A"), by_code(rc, "B")
    # Both contributions are float-rounding noise around zero, but the
    # sign-group percentages stay meaningful: A ≈ +100% of positive
    # contributions, B ≈ -100% of negative contributions.
    assert a.contribution_percentage == pytest.approx(1.0, abs=1e-6)
    assert b.contribution_percentage == pytest.approx(-1.0, abs=1e-6)


def test_zero_contributions_no_fabricated_percentage():
    result = run(
        [
            ("A", 50, constant_navs(DAYS)),
            ("B", 50, constant_navs(DAYS)),
        ]
    )
    rc = result.return_contribution
    for e in rc.contributions:
        assert e.contribution == pytest.approx(0.0, abs=RECONCILIATION_TOLERANCE)
        assert e.contribution_percentage is None
    assert rc.total_contribution == pytest.approx(0.0, abs=RECONCILIATION_TOLERANCE)
    assert result.metrics.total_return == pytest.approx(0.0, abs=RECONCILIATION_TOLERANCE)


# ---------------------------------------------------------------------------
# 8. Missing/insufficient history — existing data-sufficiency behavior
#    is preserved (no second validation system introduced).
# ---------------------------------------------------------------------------


def test_insufficient_fund_history_still_raises():
    with pytest.raises(PortfolioAnalysisError) as e:
        run([("A", 50, growing_navs(DAYS)), ("B", 50, growing_navs(1))])
    assert e.value.code == "insufficient_fund_history"


def test_insufficient_common_history_still_raises():
    short = growing_navs(20, start=(2020, 6, 1))
    with pytest.raises(PortfolioAnalysisError) as e:
        run([("A", 50, growing_navs(DAYS)), ("B", 50, short)])
    assert e.value.code == "insufficient_common_history"


# ---------------------------------------------------------------------------
# 9./10. Reconciliation with multiple funds; percentage sign shares
# ---------------------------------------------------------------------------


def test_reconciliation_multiple_funds():
    result = run(
        [
            ("A", 40, growing_navs(DAYS, daily=0.02)),
            ("B", 30, growing_navs(DAYS, daily=0.005)),
            ("C", 20, declining_navs(DAYS, daily=0.008)),
            ("D", 10, constant_navs(DAYS)),
        ]
    )
    rc = result.return_contribution
    assert math.isclose(
        sum(e.contribution for e in rc.contributions),
        rc.total_contribution,
        abs_tol=RECONCILIATION_TOLERANCE,
    )
    assert math.isclose(
        rc.total_contribution, result.metrics.total_return, abs_tol=RECONCILIATION_TOLERANCE
    )
    assert abs(rc.reconciliation_difference) < RECONCILIATION_TOLERANCE


def test_contribution_percentage_sign_shares():
    result = run(
        [
            ("A", 40, growing_navs(DAYS, daily=0.02)),
            ("B", 30, growing_navs(DAYS, daily=0.01)),
            ("C", 30, declining_navs(DAYS, daily=0.01)),
        ]
    )
    rc = result.return_contribution
    pos_share = sum(e.contribution_percentage for e in rc.contributions if e.contribution > 0)
    neg_share = sum(e.contribution_percentage for e in rc.contributions if e.contribution < 0)
    assert pos_share == pytest.approx(1.0, abs=1e-9)
    assert neg_share == pytest.approx(-1.0, abs=1e-9)
