"""Mutual-fund portfolio analysis service.

Builds an allocation-weighted portfolio series from constituent-fund NAV
histories and computes portfolio-level metrics by reusing the existing
fund-level ``MetricsCalculator`` primitives — no new mathematical formulas
are introduced here.

Approved methodology (Phase 2C):
- Portfolio daily returns are the weighted sum of constituent-fund daily
  returns using constant target weights (periodic rebalancing assumption).
- Funds are aligned on the common/intersection of their published NAV dates;
  missing observations are NOT interpolated or forward-filled.
- Zero-allocation funds contribute nothing but remain visible in the result.
- CAGR: (End/Start)^(1/years) - 1 with years = calendar_days / 365.25.
- Volatility: sample_std(daily returns) * sqrt(252).
- Sharpe: (CAGR - 4% risk-free) / volatility.
- Sortino: (CAGR - 4% risk-free) / downside deviation (MAR = 0).
- Max drawdown: peak-to-trough on the portfolio growth series.
"""

from datetime import datetime
from typing import Any

from backend.models.mutual_fund import NAVRecord
from backend.models.portfolio import (
    PortfolioFundResult,
    PortfolioMetricsData,
    PortfolioAnalysisResult,
    PortfolioSeriesPoint,
)
from backend.services.mutual_funds.calculator import MetricsCalculator
from backend.services.portfolio.health_score import calculate_health_score
from backend.utils.logging import logger

MIN_FUNDS = 2
MAX_FUNDS = 10
ALLOCATION_TOLERANCE = 0.005  # allocations are 2-decimal percentages
MIN_COMMON_OBSERVATIONS = 30  # minimum usable common history (observations)


class PortfolioAnalysisError(Exception):
    """Validation or data-sufficiency error for portfolio analysis.

    ``code`` is a stable machine-readable identifier for the frontend.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def validate_allocations(funds: list[dict[str, Any]]) -> None:
    """Validate the 2-10 fund allocation payload.

    Each entry must be ``{"scheme_code": str, "allocation": float>=0}`` and
    allocations must total exactly 100% (within 2-decimal tolerance).
    Raises :class:`PortfolioAnalysisError` on any violation.
    """
    if not isinstance(funds, list):
        raise PortfolioAnalysisError("invalid_request", "funds must be a list")

    if not MIN_FUNDS <= len(funds) <= MAX_FUNDS:
        raise PortfolioAnalysisError(
            "invalid_fund_count",
            f"Portfolio requires between {MIN_FUNDS} and {MAX_FUNDS} funds (got {len(funds)}).",
        )

    seen: set[str] = set()
    total = 0.0
    for i, fund in enumerate(funds):
        if not isinstance(fund, dict) or not isinstance(fund.get("scheme_code"), str) or not fund["scheme_code"].strip():
            raise PortfolioAnalysisError("invalid_fund", f"Fund entry {i} must have a non-empty scheme_code.")
        code = fund["scheme_code"].strip()
        if code in seen:
            raise PortfolioAnalysisError("duplicate_fund", f"Duplicate scheme_code in request: {code}")
        seen.add(code)

        allocation = fund.get("allocation")
        if isinstance(allocation, bool) or not isinstance(allocation, (int, float)):
            raise PortfolioAnalysisError(
                "invalid_allocation",
                f"Allocation for {code} must be a number (got {allocation!r}).",
            )
        if allocation < 0:
            raise PortfolioAnalysisError(
                "invalid_allocation",
                f"Allocation for {code} must not be negative (got {allocation}).",
            )
        if allocation > 100:
            raise PortfolioAnalysisError(
                "invalid_allocation",
                f"Allocation for {code} must not exceed 100 (got {allocation}).",
            )
        total += allocation

    if abs(total - 100.0) > ALLOCATION_TOLERANCE:
        raise PortfolioAnalysisError(
            "allocation_total",
            f"Allocations must total exactly 100% (got {round(total, 4)}%).",
        )


def calculate_portfolio_analysis(
    funds: list[dict[str, Any]],
) -> PortfolioAnalysisResult:
    """Compute portfolio series and metrics from pre-fetched NAV histories.

    Args:
        funds: list of ``{"scheme_code": str, "allocation": float,
               "navs": list[NAVRecord]}`` — one entry per requested fund.
               NAV histories may overlap only partially; the intersection of
               published dates is used with no interpolation.

    Returns:
        PortfolioAnalysisResult with the growth series (base 100), metrics
        computed via the existing MetricsCalculator primitives, per-fund
        summary, and warnings.

    Raises:
        PortfolioAnalysisError: on validation failure or insufficient
            usable common history.
    """
    validate_allocations(funds)

    # NAV histories keyed by scheme code; sorted by date (no interpolation).
    navs_by_code: dict[str, list[NAVRecord]] = {}
    for fund in funds:
        code = fund["scheme_code"].strip()
        navs_by_code[code] = sorted(fund.get("navs") or [], key=lambda n: n.date)

    contributing = [f for f in funds if float(f["allocation"]) > 0]
    zero_weight = [f for f in funds if float(f["allocation"]) == 0]

    warnings = [
        f"{f['scheme_code'].strip()}: 0% allocation — excluded from portfolio calculations."
        for f in zero_weight
    ]

    if not contributing:
        raise PortfolioAnalysisError(
            "no_contributing_funds",
            "All funds have 0% allocation; portfolio cannot be calculated.",
        )

    # Funds with usable history (< 2 observations cannot produce returns).
    usable: dict[str, list[NAVRecord]] = {}
    no_data: list[str] = []
    for fund in contributing:
        code = fund["scheme_code"].strip()
        if len(navs_by_code[code]) >= 2:
            usable[code] = navs_by_code[code]
        else:
            no_data.append(code)

    if no_data:
        raise PortfolioAnalysisError(
            "insufficient_fund_history",
            "Funds with insufficient NAV history: " + ", ".join(sorted(no_data)),
        )

    # --- Date alignment: intersection of published dates (no fill) ---------
    first_code = next(iter(usable))
    common_dates = {n.date for n in usable[first_code]}
    for records in usable.values():
        common_dates &= {n.date for n in records}
    common_dates = sorted(common_dates)

    if len(common_dates) < MIN_COMMON_OBSERVATIONS:
        raise PortfolioAnalysisError(
            "insufficient_common_history",
            f"Insufficient common history: only {len(common_dates)} shared NAV dates "
            f"across all funds (minimum {MIN_COMMON_OBSERVATIONS}).",
        )

    weights: dict[str, float] = {
        f["scheme_code"].strip(): float(f["allocation"]) / 100.0 for f in contributing
    }
    nav_by_date: dict[str, dict[str, float]] = {
        code: {n.date: n.nav for n in records} for code, records in usable.items()
    }

    # --- Weighted daily returns (constant target weights, rebalanced) ------
    daily_returns: list[tuple[str, float]] = []
    for prev_date, date in zip(common_dates, common_dates[1:]):
        weighted = 0.0
        for code, weight in weights.items():
            prev_nav = nav_by_date[code][prev_date]
            if prev_nav <= 0:
                raise PortfolioAnalysisError(
                    "invalid_nav_data",
                    f"Non-positive NAV for {code} on {prev_date}.",
                )
            weighted += weight * (nav_by_date[code][date] / prev_nav - 1)
        daily_returns.append((date, weighted))

    # --- Portfolio growth series (base 100) --------------------------------
    start_date = common_dates[0]
    growth: list[NAVRecord] = [NAVRecord(date=start_date, nav=100.0)]
    value = 100.0
    for date, ret in daily_returns:
        value *= 1.0 + ret
        growth.append(NAVRecord(date=date, nav=value))

    # --- Metrics via existing MetricsCalculator primitives -----------------
    calculator = MetricsCalculator(scheme_code="portfolio", nav_records=growth)
    growth_daily_returns = calculator._daily_returns(growth)
    annualized_volatility = calculator._annualized_volatility(growth_daily_returns)
    cagr = calculator._cagr(growth)
    sharpe = calculator._sharpe(cagr, annualized_volatility)
    sortino = calculator._sortino(cagr, growth_daily_returns)
    downside_deviation = calculator._downside_deviation(growth_daily_returns)
    maximum_drawdown = calculator._max_drawdown(growth)
    total_return = growth[-1].nav / growth[0].nav - 1

    start_dt = datetime.strptime(growth[0].date, "%Y-%m-%d")
    end_dt = datetime.strptime(growth[-1].date, "%Y-%m-%d")
    years = (end_dt - start_dt).days / 365.25

    metrics = PortfolioMetricsData(
        cagr=cagr,
        annualized_volatility=annualized_volatility,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        downside_deviation=downside_deviation,
        maximum_drawdown=maximum_drawdown,
        total_return=total_return,
        start_date=growth[0].date,
        end_date=growth[-1].date,
        observations=len(common_dates),
        years=years,
    )

    fund_results = []
    for f in funds:
        code = f["scheme_code"].strip()
        records = navs_by_code[code]
        fund_results.append(
            PortfolioFundResult(
                scheme_code=code,
                allocation=float(f["allocation"]),
                effective_weight=float(f["allocation"]) / 100.0,
                observations=len(records),
                first_date=records[0].date if records else None,
                last_date=records[-1].date if records else None,
                contributes=float(f["allocation"]) > 0,
                amc=f.get("amc"),
                category=f.get("category"),
                is_stale=bool(f.get("is_stale")),
            )
        )

    logger.info(
        "Portfolio analysis: %d funds, %d common observations, %s to %s",
        len(funds),
        len(common_dates),
        growth[0].date,
        growth[-1].date,
    )

    # --- Phase 3A: rolling consistency + additive Health Score ------------
    # Reuse the existing MetricsCalculator._rolling_consistency primitive on the
    # portfolio growth series (no new formulas, no additional data fetched).
    rolling_consistency = calculator._rolling_consistency(growth)

    analysis_result = PortfolioAnalysisResult(
        funds=fund_results,
        metrics=metrics,
        series=[PortfolioSeriesPoint(date=n.date, value=n.nav) for n in growth],
        warnings=warnings,
        rolling_consistency=rolling_consistency,
    )
    analysis_result.health_score = calculate_health_score(analysis_result)

    return analysis_result