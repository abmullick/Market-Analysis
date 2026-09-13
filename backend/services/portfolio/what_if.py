"""What-If Allocation comparison — historical simulation only.

Compares the existing portfolio allocation against ONE alternative allocation
using the SAME selected funds, same nav histories, same common date window,
same daily-weighted-return methodology, and same metrics as the existing
Mutual Fund Portfolio Analysis.

NOT portfolio optimization / recommendation / forecasting / Monte Carlo.
"""
from __future__ import annotations

import math
from typing import Any

from backend.models.portfolio import PortfolioAnalysisResult, PortfolioSeriesPoint
from backend.services.portfolio.mf_analysis import (
    ALLOCATION_TOLERANCE,
    MAX_FUNDS,
    MIN_FUNDS,
    PortfolioAnalysisError,
    calculate_portfolio_analysis,
    validate_allocations,
)

ERROR_MIN_FUNDS = "portfolio requires at least %d funds" % MIN_FUNDS
ERROR_MAX_FUNDS = "portfolio supports at most %d funds" % MAX_FUNDS
ERROR_ALLOC_TOTAL = "allocations must total exactly 100%%"
ERROR_ALLOC_INVALID = "invalid allocation value"
ERROR_DUPLICATE = "duplicate scheme_code"
ERROR_NEGATIVE = "allocations must be >= 0"
ERROR_UNKNOWN_FUND = "scenario fund not in the current portfolio"
ERROR_MISSING_FUND = "scenario must include every fund in the current portfolio"
ERROR_SCENARIO_TOTAL = "scenario allocations must total exactly 100%%"
ERROR_INSUFFICIENT_DATA = "insufficient historical data for analysis"


class WhatIfError(PortfolioAnalysisError):
    """Raised for invalid What-If requests; handled as 4xx by the route."""


def _scenario_allocation_map(
    scenario: list[dict[str, Any]],
) -> dict[str, float]:
    """Convert the scenario list into {scheme_code: alloc}."""
    return {item["scheme_code"]: round(float(item["allocation"]), 2) for item in scenario}


def _validate_scenario_funds(
    fund_codes: list[str],
    scenarios: list[dict[str, Any]],
) -> None:
    """Validate the scenario side of the What-If request.

    The current portfolio has already been validated by
    ``validate_allocations`` in the existing analysis path. Here we only
    enforce What-If-specific constraints: scenario allocations are a subset
    of the current fund list, contain no further duplicates, total 100%
    within the existing allocation tolerance, and contain no negative/non-numeric
    allocations.
    """
    if not isinstance(scenarios, list) or len(scenarios) == 0:
        raise WhatIfError("ALLOC_INVALID", ERROR_ALLOC_INVALID)

    codes_set = set(fund_codes)
    seen: set[str] = set()
    total = 0.0
    for item in scenarios:
        if not isinstance(item, dict):
            raise WhatIfError("ALLOC_INVALID", ERROR_ALLOC_INVALID)
        code = item.get("scheme_code")
        alloc = item.get("allocation")
        if not isinstance(code, str) or not code.strip():
            raise WhatIfError("ALLOC_INVALID", ERROR_ALLOC_INVALID)
        if not isinstance(alloc, (int, float)) or not math.isfinite(float(alloc)):
            raise WhatIfError("ALLOC_INVALID", ERROR_ALLOC_INVALID)
        if float(alloc) < 0:
            raise WhatIfError("ALLOC_INVALID", ERROR_NEGATIVE)
        if code not in codes_set:
            raise WhatIfError("SCENARIO_FUND_NOT_IN_PORTFOLIO", ERROR_UNKNOWN_FUND)
        if code in seen:
            raise WhatIfError("ALLOC_DUPLICATE", ERROR_DUPLICATE)
        seen.add(code)
        total += float(alloc)

    # Every current-portfolio fund must have a scenario weight — a partial
    # reallocation (e.g. omitting one fund) is not a valid What-If scenario.
    if seen != codes_set:
        raise WhatIfError("SCENARIO_MISSING_FUND", ERROR_MISSING_FUND)

    if abs(total - 100.0) > ALLOCATION_TOLERANCE:
        raise WhatIfError("ALLOC_TOTAL", ERROR_SCENARIO_TOTAL)



def validate_scenario_allocations(
    fund_codes: list[str],
    scenario_allocations: list[dict[str, Any]],
) -> None:
    """Validate the What-If scenario allocations.

    The current portfolio must already be validated via ``validate_allocations``.
    Enforces What-If-specific constraints: every scenario fund must exist in
    the current portfolio, no duplicates within the scenario, all allocations
    numeric and non-negative, and the scenario total must be exactly 100%
    within the existing allocation tolerance.
    """
    _validate_scenario_funds(fund_codes, scenario_allocations)


def compare_portfolio_results(
    current: PortfolioAnalysisResult,
    scenario: PortfolioAnalysisResult,
) -> dict[str, Any]:
    """Build the What-If comparison from two portfolio analysis results.

    Both results come from ``calculate_portfolio_analysis`` over the SAME
    fund universe and common date window, so the comparison is apples-to-apples.
    """
    cur_m = current.metrics
    sce_m = scenario.metrics
    deltas = {
        "cagr": _delta(sce_m.cagr, cur_m.cagr),
        "volatility": _delta(sce_m.annualized_volatility, cur_m.annualized_volatility),
        "sharpe": _delta(sce_m.sharpe_ratio, cur_m.sharpe_ratio),
        "sortino": _delta(sce_m.sortino_ratio, cur_m.sortino_ratio),
        "max_drawdown": _delta(sce_m.maximum_drawdown, cur_m.maximum_drawdown),
        "total_return": _delta(sce_m.total_return, cur_m.total_return),
    }

    return {
        "analysis_period": {
            "start_date": cur_m.start_date,
            "end_date": cur_m.end_date,
            "observations": cur_m.observations,
            "years": cur_m.years,
        },
        "current": {
            "allocations": [
                {"scheme_code": f.scheme_code, "allocation": f.allocation}
                for f in current.funds
            ],
            "metrics": cur_m.model_dump(),
            "benchmark_data": current.benchmark_data.model_dump() if current.benchmark_data else None,
        },
        "scenario": {
            "allocations": [
                {"scheme_code": f.scheme_code, "allocation": f.allocation}
                for f in scenario.funds
            ],
            "metrics": sce_m.model_dump(),
            "benchmark_data": scenario.benchmark_data.model_dump() if scenario.benchmark_data else None,
        },
        "deltas": deltas,
        "growth_series": _growth_series(current.series, scenario.series),
        "warnings": list(current.warnings) + list(scenario.warnings),
    }


def _delta(scenario_val, current_val):
    if scenario_val is None or current_val is None:
        return None
    return float(scenario_val) - float(current_val)


def _growth_series(
    current: list[PortfolioSeriesPoint],
    scenario: list[PortfolioSeriesPoint],
) -> list[dict[str, Any]]:
    if len(current) != len(scenario) or not current:
        return []
    base = current[0].value if current[0].value else 1e-9
    return [
        {
            "date": c.date,
            "current": c.value / base * 100.0,
            "scenario": s.value / base * 100.0,
        }
        for c, s in zip(current, scenario)
    ]
