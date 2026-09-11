"""Portfolio Health Score (Phase 3A).

Computes a 0-100 Health Score from already-calculated portfolio analysis
data. This module performs NO NAV fetching and introduces NO new mathematical
formulas. It is a pure derivation from the portfolio metrics,
rolling-consistency windows, and per-fund metadata (AMC/category) produced by
the portfolio analysis engine.

The score measures historical portfolio construction / risk-return
characteristics of the *analysis period only*. It is not a prediction of
future returns and not investment advice.
"""

from __future__ import annotations

import math
from typing import Any

from backend.models.portfolio import (
    ComponentExplanation,
    HealthConfidence,
    HealthScoreComponents,
    HealthScoreData,
    HealthScoreExplanation,
    PortfolioAnalysisResult,
)

# Base component weights (out of 100). The final score is a weighted average
# using these anchors, re-normalized when a component is unavailable.
COMPONENT_WEIGHTS: dict[str, float] = {
    "return_quality": 25.0,
    "downside_risk": 25.0,
    "risk_adjusted_return": 20.0,
    "concentration": 20.0,
    "fund_mix": 10.0,
}

# Rolling-window weights for the consistency sub-score, re-normalized among
# the windows actually available for the analysis period.
WINDOW_WEIGHTS: dict[str, float] = {"1Y": 0.5, "3Y": 0.3, "5Y": 0.2}

# Calibration anchors (design choices, not empirical financial thresholds).
CAGR_KNEE_LOW = 0.12
CAGR_KNEE_HIGH = 0.20
MDD_FLOOR = 0.50
DD_RATIO_CEIL = 0.8
ROLLING_STD_CAP = 0.15
SORTINO_MID = 1.0
SORTINO_TOP = 2.0

TIER_LABELS = {
    "A": "High confidence",
    "B": "Good confidence",
    "C": "Limited - 3Y/5Y rolling windows unavailable",
    "D": "Low confidence",
}
LEGACY_TIER_C_LABEL = (
    "Limited - includes a scheme AMFI no longer publishes NAVs for"
)


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _piecewise(value: float, stops: list[tuple[float, float]]) -> float:
    """Piecewise-linear map through (x, y) stops, clamped to the stop range."""
    if value <= stops[0][0]:
        return stops[0][1]
    for (x0, y0), (x1, y1) in zip(stops, stops[1:]):
        if value <= x1:
            return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return stops[-1][1]


def _cagr_subscore(cagr: float) -> float:
    """R1: CAGR -> 0..40 (piecewise-linear, clamped)."""
    return _piecewise(
        cagr,
        [(0.0, 0.0), (CAGR_KNEE_LOW, 25.0), (CAGR_KNEE_HIGH, 40.0)],
    )


def _rolling_consistency_subscore(
    rolling: dict[str, Any] | None,
) -> float | None:
    """R2: rolling consistency + stability -> 0..100.

    Combines the positive-window percentage (consistency) and the inverse of
    rolling-return dispersion (stability), weighted 60/40 per window, then
    blended across available windows using WINDOW_WEIGHTS (re-normalized).
    """
    if not rolling:
        return None

    available_labels = [w for w in WINDOW_WEIGHTS if rolling.get(w)]
    if not available_labels:
        return None

    total_w = sum(WINDOW_WEIGHTS[w] for w in available_labels)
    score = 0.0
    for label in available_labels:
        window = rolling[label]
        positive_pct = window.get("positive_pct")
        if positive_pct is None:
            continue
        consistency = positive_pct / 100.0
        std_return = window.get("std_return")
        stability = (
            1.0 - min(1.0, std_return / ROLLING_STD_CAP)
            if std_return is not None
            else 0.0
        )
        r2_window = 0.6 * consistency + 0.4 * stability
        score += (WINDOW_WEIGHTS[label] / total_w) * r2_window

    return score * 100.0


def _downside_risk_subscore(
    max_drawdown: float | None,
    downside_deviation: float | None,
    volatility: float | None,
) -> float | None:
    """Downside Risk component -> 0..100.

    D1 (60%): max drawdown. Drawdown is a negative fraction; 0 -> 100,
    magnitude >= MDD_FLOOR -> 0.
    D2 (40%): downside-deviation / volatility ratio. ratio 0 -> 100,
    ratio >= DD_RATIO_CEIL -> 0. Volatility 0 -> D2 = 100.
    """
    d1 = None
    if max_drawdown is not None and _finite(max_drawdown):
        d1 = _clamp((1.0 - abs(max_drawdown) / MDD_FLOOR) * 100.0)

    d2 = None
    if (
        volatility is not None
        and downside_deviation is not None
        and _finite(volatility)
        and _finite(downside_deviation)
    ):
        if volatility == 0:
            d2 = 100.0
        else:
            ratio = downside_deviation / volatility
            d2 = _clamp((1.0 - ratio / DD_RATIO_CEIL) * 100.0)

    if d1 is not None and d2 is not None:
        return 0.6 * d1 + 0.4 * d2
    return d1 if d1 is not None else d2


def _risk_adjusted_subscore(sortino: float | None) -> float | None:
    """Risk-Adjusted Return component (Sortino only) -> 0..100."""
    if sortino is None or not _finite(sortino):
        return None
    return _piecewise(
        sortino,
        [(0.0, 0.0), (SORTINO_MID, 60.0), (SORTINO_TOP, 100.0)],
    )


def _concentration_subscore(weights: list[float]) -> float | None:
    """Concentration (diversification) component -> 0..100.

    Herfindahl-Hirschman Index over contributing-fund weights.
    n >= 2: 100 * ((1 - HHI) / (1 - 1/n)). n <= 1: 0.
    """
    n = len(weights)
    if n <= 1:
        return 0.0
    hhi = sum(w * w for w in weights)
    return 100.0 * ((1.0 - hhi) / (1.0 - 1.0 / n))


def _fund_mix_subscore(
    categories: list[str | None], amcs: list[str | None],
) -> float | None:
    """Fund Mix component -> 0..100 from category + AMC spread.

    category_score = (distinct_categories - 1) / min(n-1, 4)
    amc_score     = (distinct_amcs - 1) / min(n-1, 3)
    blended 60/40. Missing metadata drops the relevant sub-component and
    re-normalizes the remainder.
    """
    n = len(categories)
    if n <= 1:
        return 0.0

    has_cat = any(c for c in categories)
    has_amc = any(a for a in amcs)

    cat_score = None
    amc_score = None
    if has_cat:
        distinct = len({c for c in categories if c})
        cat_score = (distinct - 1) / min(n - 1, 4)
    if has_amc:
        distinct = len({a for a in amcs if a})
        amc_score = (distinct - 1) / min(n - 1, 3)

    if cat_score is not None and amc_score is not None:
        return (0.6 * cat_score + 0.4 * amc_score) * 100.0
    if cat_score is not None:
        return cat_score * 100.0
    if amc_score is not None:
        return amc_score * 100.0
    return 0.0


def _history_confidence(years: float | None, has_legacy: bool) -> tuple[str, str]:
    """Return (tier, label). Legacy schemes cap confidence at C."""
    if years is None or years < 1:
        return "D", TIER_LABELS["D"]
    if years >= 5:
        tier = "A"
    elif years >= 3:
        tier = "B"
    else:
        tier = "C"

    if has_legacy and tier in ("A", "B"):
        return "C", LEGACY_TIER_C_LABEL
    return tier, TIER_LABELS[tier]


def calculate_health_score(
    result: PortfolioAnalysisResult,
) -> HealthScoreData:
    """Compute the additive Health Score from a PortfolioAnalysisResult.

    Pure function over already-calculated data - no NAV fetching, no new
    metrics. Uses result.metrics, result.rolling_consistency, and the
    per-fund effective_weight/category/amc/is_stale metadata.

    Returns HealthScoreData with component sub-scores, confidence tier, and
    the weighted final score (None when withheld for <1 year history).
    Also returns structured explanation data for UI explainability (Phase 3B).
    """
    from backend.models.portfolio import (
        ComponentExplanation,
        HealthScoreExplanation,
    )

    metrics = result.metrics
    rolling = getattr(result, "rolling_consistency", None)
    funds = result.funds

    # --- Return Quality (R1 + R2) ---------------------------------------
    r1 = (
        _cagr_subscore(metrics.cagr)
        if metrics.cagr is not None and _finite(metrics.cagr)
        else None
    )
    r2 = _rolling_consistency_subscore(rolling)
    if r1 is not None and r2 is not None:
        return_quality = 0.4 * r1 + 0.6 * r2
    elif r1 is not None:
        return_quality = r1
    elif r2 is not None:
        return_quality = r2
    else:
        return_quality = None

    # --- Downside Risk ---------------------------------------------------
    downside_risk = _downside_risk_subscore(
        metrics.maximum_drawdown,
        metrics.downside_deviation,
        metrics.annualized_volatility,
    )

    # --- Risk-Adjusted Return (Sortino only) -----------------------------
    risk_adjusted = _risk_adjusted_subscore(metrics.sortino_ratio)

    # --- Concentration ---------------------------------------------------
    contributing_weights = [
        f.effective_weight for f in funds if f.contributes and f.effective_weight > 0
    ]
    concentration = _concentration_subscore(contributing_weights)

    # --- Fund Mix --------------------------------------------------------
    categories = [f.category for f in funds if f.contributes]
    amcs = [f.amc for f in funds if f.contributes]
    fund_mix = _fund_mix_subscore(categories, amcs)

    # --- History confidence + legacy -------------------------------------
    has_legacy = any(f.is_stale for f in funds if f.contributes)
    tier, label = _history_confidence(metrics.years, has_legacy)

    single_fund = len(contributing_weights) <= 1

    # --- Assemble components + re-normalize weights ----------------------
    components: dict[str, float | None] = {
        "return_quality": return_quality,
        "downside_risk": downside_risk,
        "risk_adjusted_return": risk_adjusted,
        "concentration": concentration,
        "fund_mix": fund_mix,
    }
    available = {
        k: v for k, v in components.items() if v is not None and _finite(v)
    }
    total_weight = sum(COMPONENT_WEIGHTS[k] for k in available)
    component_weights = (
        {k: COMPONENT_WEIGHTS[k] / total_weight for k in available}
        if total_weight > 0
        else {}
    )

    score: float | None
    if total_weight > 0:
        score = sum(available[k] * component_weights[k] for k in available)
        score = _clamp(score)
    else:
        score = None

    # --- Withhold score entirely when history < 1 year -------------------
    score_withheld = tier == "D"
    withholding_reason = (
        "Insufficient history - less than 1 year of common history."
        if score_withheld
        else None
    )
    if score_withheld:
        score = None

    # --- Build explanation data (Phase 3B) ------------------------------
    explanation = _build_health_score_explanation(
        score=score,
        components=components,
        component_weights=component_weights,
        available=available,
        metrics=metrics,
        rolling=rolling,
        funds=funds,
        categories=categories,
        amcs=amcs,
        contributing_weights=contributing_weights,
        tier=tier,
        label=label,
        has_legacy=has_legacy,
        score_withheld=score_withheld,
    )

    return HealthScoreData(
        score=score,
        confidence=HealthConfidence(tier=tier, label=label),
        components=HealthScoreComponents(
            return_quality=return_quality,
            downside_risk=downside_risk,
            risk_adjusted_return=risk_adjusted,
            concentration=concentration,
            fund_mix=fund_mix,
        ),
        component_weights=component_weights,
        available_components=list(available.keys()),
        single_fund_portfolio=single_fund,
        has_legacy_scheme=has_legacy,
        score_withheld=score_withheld,
        withholding_reason=withholding_reason,
        explanation=explanation,
    )
# ---------------------------------------------------------------------------
# Phase 3B: Explanation helpers (pure derivation, no formula changes).
# Each helper reuses the scoring functions above so the explanation always
# describes the exact calculation that produced the component score.
# ---------------------------------------------------------------------------


def _fmt_pct(value: float | None, decimals: int = 2) -> str:
    """Format decimal ratio (0.12) as percentage string (12.00%)."""
    if value is None or not _finite(value):
        return "Not available"
    return f"{float(value) * 100:.{decimals}f}%"


def _fmt_num(value: float | None, decimals: int = 2) -> str:
    if value is None or not _finite(value):
        return "Not available"
    return f"{float(value):.{decimals}f}"


def _explain_return_quality(
    cagr: float | None,
    rolling: dict[str, Any] | None,
    score: float | None,
    weight: float | None,
) -> ComponentExplanation:
    """Return Quality = 0.4 x R1 + 0.6 x R2 (mirrors calculate_health_score)."""
    inputs: dict[str, Any] = {}
    intermediate: dict[str, Any] = {}
    details: list[str] = []
    cagr_ok = cagr is not None and _finite(cagr)
    inputs["cagr"] = float(cagr) if cagr_ok else None
    r1: float | None = _cagr_subscore(cagr) if cagr_ok else None
    intermediate["R1"] = r1
    if cagr_ok:
        details.append(
            f"CAGR: {_fmt_pct(cagr)} -> R1: {_fmt_num(r1, 1)}/40 "
            f"(0% -> 0, {CAGR_KNEE_LOW * 100:.0f}% -> 25, "
            f"{CAGR_KNEE_HIGH * 100:.0f}% -> 40, above capped at 40)"
        )
    else:
        details.append("CAGR: Not available -> R1 cannot be computed.")
    window_scores: dict[str, float] = {}
    if rolling:
        for label in ("1Y", "3Y", "5Y"):
            window = rolling.get(label)
            if not window:
                inputs[f"rolling_{label}"] = None
                continue
            inputs[f"rolling_{label}"] = {
                "positive_pct": window.get("positive_pct"),
                "std_return": window.get("std_return"),
                "n": window.get("n"),
            }
            pos = window.get("positive_pct")
            std = window.get("std_return")
            if pos is not None and _finite(pos):
                consistency = float(pos) / 100.0
                s = float(std) if std is not None and _finite(std) else 0.0
                stability = 1.0 - min(1.0, s / ROLLING_STD_CAP)
                w_score = 0.6 * consistency + 0.4 * stability
                window_scores[label] = w_score
                details.append(
                    f"{label}: positive {_fmt_num(pos, 1)}%, dispersion "
                    f"{_fmt_num(std, 4)} -> window score "
                    f"{_fmt_num(w_score * 100, 1)}/100 "
                    f"(weight {WINDOW_WEIGHTS[label]})"
                )
            else:
                details.append(f"{label}: Not available.")
    else:
        for label in ("1Y", "3Y", "5Y"):
            inputs[f"rolling_{label}"] = None
        details.append("Rolling consistency: Not available (history too short).")
    r2: float | None = _rolling_consistency_subscore(rolling)
    intermediate["R2"] = r2
    intermediate["window_scores"] = window_scores or None
    if r2 is not None:
        details.append(f"R2 blended: {_fmt_num(r2, 1)}/100")
    else:
        details.append("R2: Not available.")
    if r1 is not None and r2 is not None and score is not None:
        details.append(
            f"Return Quality = 0.4 x {_fmt_num(r1, 1)} + 0.6 x "
            f"{_fmt_num(r2, 1)} = {_fmt_num(score, 1)}"
        )
        summary = (
            f"CAGR {_fmt_pct(cagr)} gives R1 {_fmt_num(r1, 1)}/40; rolling "
            f"gives R2 {_fmt_num(r2, 1)}/100; blended = {_fmt_num(score, 1)}."
        )
    elif score is not None:
        details.append(f"Return Quality (partial data): {_fmt_num(score, 1)}")
        summary = f"Return Quality {_fmt_num(score, 1)} from available inputs."
    else:
        details.append("Return Quality: Not available.")
        summary = "Return Quality unavailable: no CAGR or rolling data."
    return ComponentExplanation(
        component_name="Return Quality",
        component_score=score,
        component_weight=weight,
        inputs=inputs,
        intermediate_scores=intermediate,
        calculation_details=details,
        summary_text=summary,
    )

def _explain_downside_risk(
    max_dd: float | None,
    downside_dev: float | None,
    volatility: float | None,
    score: float | None,
    weight: float | None,
) -> ComponentExplanation:
    """Downside Risk = 0.6 x D1 + 0.4 x D2 (mirrors _downside_risk_subscore)."""
    inputs: dict[str, Any] = {
        "maximum_drawdown": float(max_dd) if max_dd is not None and _finite(max_dd) else None,
        "downside_deviation": float(downside_dev) if downside_dev is not None and _finite(downside_dev) else None,
        "annualized_volatility": float(volatility) if volatility is not None and _finite(volatility) else None,
    }
    details: list[str] = []
    dd_ok = max_dd is not None and _finite(max_dd)
    d1: float | None = _clamp((1.0 - abs(float(max_dd)) / MDD_FLOOR) * 100.0) if dd_ok else None
    if dd_ok:
        details.append(
            f"Maximum Drawdown: {_fmt_pct(abs(float(max_dd)))} "
            f"-> D1: {_fmt_num(d1, 1)}/100"
        )
    else:
        details.append("Maximum Drawdown: Not available -> D1 cannot be computed.")
    ratio: float | None = None
    d2: float | None = None
    vol_ok = volatility is not None and _finite(volatility)
    ddv_ok = downside_dev is not None and _finite(downside_dev)
    if ddv_ok and vol_ok and float(volatility) != 0:
        ratio = float(downside_dev) / float(volatility)
        d2 = _clamp((1.0 - ratio / DD_RATIO_CEIL) * 100.0)
        details.append(
            f"Downside deviation: {_fmt_num(downside_dev, 4)}, volatility: "
            f"{_fmt_num(volatility, 4)} -> ratio {_fmt_num(ratio, 3)} "
            f"-> D2: {_fmt_num(d2, 1)}/100"
        )
    elif vol_ok and float(volatility) == 0:
        d2 = 100.0
        details.append("Volatility is zero -> D2: 100/100.")
    else:
        details.append("Downside deviation/volatility: Not available -> D2 cannot be computed.")
    if d1 is not None and d2 is not None and score is not None:
        details.append(
            f"Downside Risk = 0.6 x {_fmt_num(d1, 1)} + 0.4 x "
            f"{_fmt_num(d2, 1)} = {_fmt_num(score, 1)}"
        )
        summary = f"Drawdown {_fmt_num(d1, 1)}, downside-ratio {_fmt_num(d2, 1)}; blended = {_fmt_num(score, 1)}."
    elif score is not None:
        details.append(f"Downside Risk (partial data): {_fmt_num(score, 1)}")
        summary = f"Downside Risk {_fmt_num(score, 1)} from available inputs."
    else:
        details.append("Downside Risk: Not available.")
        summary = "Downside Risk unavailable: no drawdown or volatility data."
    return ComponentExplanation(
        component_name="Downside Risk",
        component_score=score,
        component_weight=weight,
        inputs=inputs,
        intermediate_scores={"D1": d1, "D2": d2, "downside_vol_ratio": ratio},
        calculation_details=details,
        summary_text=summary,
    )


def _explain_risk_adjusted(
    sortino: float | None,
    score: float | None,
    weight: float | None,
) -> ComponentExplanation:
    """Risk-Adjusted Return: Sortino map (mirrors _risk_adjusted_subscore)."""
    inputs: dict[str, Any] = {
        "sortino_ratio": float(sortino) if sortino is not None and _finite(sortino) else None,
    }
    details: list[str] = []
    sub: float | None = _risk_adjusted_subscore(sortino)
    if sortino is not None and _finite(sortino):
        details.append(
            f"Sortino Ratio: {_fmt_num(sortino, 3)} "
            f"(map: <=0 -> 0, 1.0 -> 60, 2.0 -> 100, above capped at 100)"
        )
        details.append(f"Risk-Adjusted Return score: {_fmt_num(sub, 1)}/100")
        summary = f"Sortino {_fmt_num(sortino, 3)} maps to {_fmt_num(sub, 1)}/100."
    else:
        details.append("Sortino Ratio: Not available.")
        summary = "Risk-Adjusted Return unavailable: no Sortino ratio."
    return ComponentExplanation(
        component_name="Risk-Adjusted Return",
        component_score=score,
        component_weight=weight,
        inputs=inputs,
        intermediate_scores={"sortino_score": sub},
        calculation_details=details,
        summary_text=summary,
    )


def _explain_concentration(
    weights: list[float],
    score: float | None,
    weight: float | None,
) -> ComponentExplanation:
    """Allocation Concentration: HHI-based (mirrors _concentration_subscore)."""
    n = len(weights)
    hhi: float | None = sum(float(w) * float(w) for w in weights) if n > 0 else None
    inputs: dict[str, Any] = {
        "fund_count": n,
        "effective_weights": [float(w) for w in weights],
    }
    intermediate: dict[str, Any] = {"HHI": hhi}
    details: list[str] = []
    if n > 0:
        pcts = ", ".join(f"{_fmt_pct(w, 2)}" for w in weights)
        details.append(f"Fund weights ({n}): {pcts}.")
        details.append(f"HHI = sum(w^2) = {_fmt_num(hhi, 4)}.")
    if n <= 1:
        details.append("Single fund -> concentration score 0 (no diversification).")
        summary = "Single-fund portfolio: concentration 0/100."
    elif score is not None and hhi is not None:
        details.append(
            f"Concentration = 100 x (1 - {_fmt_num(hhi, 4)}) / (1 - 1/{n}) "
            f"= {_fmt_num(score, 1)}/100"
        )
        if n > 0 and abs(hhi - 1.0 / n) < 1e-9:
            summary = f"Equal {n}-way allocation is the HHI minimum; score {_fmt_num(score, 1)}/100."
        else:
            summary = f"HHI {_fmt_num(hhi, 4)} over {n} funds gives {_fmt_num(score, 1)}/100."
    else:
        details.append("Concentration: Not available.")
        summary = "Concentration unavailable: no fund weights."
    return ComponentExplanation(
        component_name="Allocation Concentration",
        component_score=score,
        component_weight=weight,
        inputs=inputs,
        intermediate_scores=intermediate,
        calculation_details=details,
        summary_text=summary,
    )


def _explain_fund_mix(
    categories: list[str | None],
    amcs: list[str | None],
    score: float | None,
    weight: float | None,
) -> ComponentExplanation:
    """Fund Mix: category/AMC spread (mirrors _fund_mix_subscore)."""
    n = len(categories)
    has_cat = any(c for c in categories)
    has_amc = any(a for a in amcs)
    distinct_cats = len({c for c in categories if c}) if has_cat else 0
    distinct_amcs = len({a for a in amcs if a}) if has_amc else 0
    cat_score: float | None = None
    amc_score: float | None = None
    if has_cat and n > 1:
        cat_score = (distinct_cats - 1) / min(n - 1, 4)
    if has_amc and n > 1:
        amc_score = (distinct_amcs - 1) / min(n - 1, 3)
    inputs: dict[str, Any] = {
        "fund_count": n,
        "categories": list(categories),
        "amcs": list(amcs),
    }
    intermediate: dict[str, Any] = {
        "distinct_categories": distinct_cats,
        "distinct_amcs": distinct_amcs,
        "category_score": (cat_score * 100) if cat_score is not None else None,
        "amc_score": (amc_score * 100) if amc_score is not None else None,
    }
    details: list[str] = []
    details.append(f"{n} funds: {distinct_cats} categories, {distinct_amcs} AMCs.")
    if cat_score is not None:
        details.append(
            f"Category: ({distinct_cats} - 1)/min({n} - 1, 4) "
            f"= {_fmt_num(cat_score * 100, 1)}/100"
        )
    else:
        details.append("Category diversity: Not available.")
    if amc_score is not None:
        details.append(
            f"AMC: ({distinct_amcs} - 1)/min({n} - 1, 3) "
            f"= {_fmt_num(amc_score * 100, 1)}/100"
        )
    else:
        details.append("AMC diversity: Not available.")
    if cat_score is not None and amc_score is not None and score is not None:
        details.append(
            f"Fund Mix = 0.6 x {_fmt_num(cat_score * 100, 1)} + 0.4 x "
            f"{_fmt_num(amc_score * 100, 1)} = {_fmt_num(score, 1)}/100"
        )
        if distinct_cats < n and distinct_amcs == n:
            summary = (
                f"All {distinct_amcs} AMCs differ (full AMC diversity) but two funds "
                f"share a category, so category diversity is lower: "
                f"final {_fmt_num(score, 1)}/100."
            )
        else:
            summary = (
                f"Category {_fmt_num(cat_score * 100, 1)}, AMC "
                f"{_fmt_num(amc_score * 100, 1)}; blended = {_fmt_num(score, 1)}/100."
            )
    elif score is not None:
        details.append(f"Fund Mix (partial data): {_fmt_num(score, 1)}/100")
        summary = f"Fund Mix {_fmt_num(score, 1)}/100 from available metadata."
    else:
        details.append("Fund Mix: Not available.")
        summary = "Fund Mix unavailable: no category/AMC metadata."
    return ComponentExplanation(
        component_name="Fund Mix (category/AMC spread)",
        component_score=score,
        component_weight=weight,
        inputs=inputs,
        intermediate_scores=intermediate,
        calculation_details=details,
        summary_text=summary,
    )


def _explain_concentration(
    weights: list[float],
    score: float | None,
    weight: float | None,
) -> ComponentExplanation:
    """Allocation Concentration: HHI-based (mirrors _concentration_subscore)."""
    n = len(weights)
    hhi: float | None = sum(float(w) * float(w) for w in weights) if n > 0 else None
    inputs: dict[str, Any] = {
        "fund_count": n,
        "effective_weights": [float(w) for w in weights],
    }
    intermediate: dict[str, Any] = {"HHI": hhi}
    details: list[str] = []
    if n > 0:
        pcts = ", ".join(f"{_fmt_pct(w, 2)}" for w in weights)
        details.append(f"Fund weights ({n}): {pcts}.")
        details.append(f"HHI = sum(w^2) = {_fmt_num(hhi, 4)}.")
    if n <= 1:
        details.append("Single fund -> concentration score 0 (no diversification).")
        summary = "Single-fund portfolio: concentration 0/100."
    elif score is not None and hhi is not None:
        details.append(
            f"Concentration = 100 x (1 - {_fmt_num(hhi, 4)}) / (1 - 1/{n}) "
            f"= {_fmt_num(score, 1)}/100"
        )
        if n > 0 and abs(hhi - 1.0 / n) < 1e-9:
            summary = f"Equal {n}-way allocation is the HHI minimum; score {_fmt_num(score, 1)}/100."
        else:
            summary = f"HHI {_fmt_num(hhi, 4)} over {n} funds gives {_fmt_num(score, 1)}/100."
    else:
        details.append("Concentration: Not available.")
        summary = "Concentration unavailable: no fund weights."
    return ComponentExplanation(
        component_name="Allocation Concentration",
        component_score=score,
        component_weight=weight,
        inputs=inputs,
        intermediate_scores=intermediate,
        calculation_details=details,
        summary_text=summary,
    )


def _explain_fund_mix(categories, amcs, score, weight):
    """Fund Mix: category/AMC spread (mirrors _fund_mix_subscore)."""
    n = len(categories)
    has_cat = any(c for c in categories)
    has_amc = any(a for a in amcs)
    distinct_cats = len({c for c in categories if c}) if has_cat else 0
    distinct_amcs = len({a for a in amcs if a}) if has_amc else 0
    cat_score = (distinct_cats - 1) / min(n - 1, 4) if (has_cat and n > 1) else None
    amc_score = (distinct_amcs - 1) / min(n - 1, 3) if (has_amc and n > 1) else None
    inputs = {"fund_count": n, "categories": list(categories), "amcs": list(amcs)}
    intermediate = {
        "distinct_categories": distinct_cats,
        "distinct_amcs": distinct_amcs,
        "category_score": (cat_score * 100) if cat_score is not None else None,
        "amc_score": (amc_score * 100) if amc_score is not None else None,
    }
    details = [f"{n} funds: {distinct_cats} categories, {distinct_amcs} AMCs."]
    if cat_score is not None:
        details.append(f"Category: ({distinct_cats}-1)/min({n}-1,4) = {_fmt_num(cat_score*100,1)}/100")
    else:
        details.append("Category diversity: Not available.")
    if amc_score is not None:
        details.append(f"AMC: ({distinct_amcs}-1)/min({n}-1,3) = {_fmt_num(amc_score*100,1)}/100")
    else:
        details.append("AMC diversity: Not available.")
    if cat_score is not None and amc_score is not None and score is not None:
        details.append(f"Fund Mix = 0.6x{_fmt_num(cat_score*100,1)} + 0.4x{_fmt_num(amc_score*100,1)} = {_fmt_num(score,1)}/100")
        if distinct_cats < n and distinct_amcs == n:
            summary = f"All {distinct_amcs} AMCs differ (full AMC diversity) but two funds share a category, so category diversity is lower: final {_fmt_num(score,1)}/100."
        else:
            summary = f"Category {_fmt_num(cat_score*100,1)}, AMC {_fmt_num(amc_score*100,1)}; blended = {_fmt_num(score,1)}/100."
    elif score is not None:
        details.append(f"Fund Mix (partial data): {_fmt_num(score, 1)}/100")
        summary = f"Fund Mix {_fmt_num(score, 1)}/100 from available metadata."
    else:
        details.append("Fund Mix: Not available.")
        summary = "Fund Mix unavailable: no category/AMC metadata."
    return ComponentExplanation(component_name="Fund Mix (category/AMC spread)", component_score=score, component_weight=weight, inputs=inputs, intermediate_scores=intermediate, calculation_details=details, summary_text=summary)


def _explain_confidence(years, tier, label, has_legacy, score_withheld):
    """Confidence explanation; tier comes from existing _history_confidence."""
    lines = []
    if years is None or not _finite(years):
        lines.append("Common history: Not available -> tier D.")
    else:
        lines.append(f"Common history: {_fmt_num(years, 2)} years (A>=5, B>=3, C>=1, D<1).")
    lines.append(f"Legacy scheme present: {'Yes' if has_legacy else 'No'}.")
    if has_legacy and tier in ("A", "B"):
        lines.append("Legacy schemes cap confidence below A/B.")
    if score_withheld:
        lines.append("Score withheld: history under 1 year (tier D).")
    lines.append(f"Result: {tier} - {label}.")
    return {
        "tier": tier, "label": label,
        "history_years": float(years) if years is not None and _finite(years) else None,
        "has_legacy": bool(has_legacy), "score_withheld": bool(score_withheld),
        "thresholds": {"A": ">= 5 years", "B": ">= 3 and < 5 years", "C": ">= 1 and < 3 years", "D": "< 1 year"},
        "reason": " ".join(lines),
    }


def _build_health_score_explanation(*, score, components, component_weights, available, metrics, rolling, funds, categories, amcs, contributing_weights, tier, label, has_legacy, score_withheld):
    """Build structured explanations; never alters scores/weights."""
    display_names = {"return_quality": "Return Quality", "downside_risk": "Downside Risk", "risk_adjusted_return": "Risk-Adjusted Return", "concentration": "Allocation Concentration", "fund_mix": "Fund Mix"}
    cagr = getattr(metrics, "cagr", None)
    max_dd = getattr(metrics, "maximum_drawdown", None)
    ddv = getattr(metrics, "downside_deviation", None)
    vol = getattr(metrics, "annualized_volatility", None)
    sortino = getattr(metrics, "sortino_ratio", None)
    years = getattr(metrics, "years", None)
    built = {}
    built["return_quality"] = _explain_return_quality(cagr, rolling, components.get("return_quality"), component_weights.get("return_quality"))
    built["downside_risk"] = _explain_downside_risk(max_dd, ddv, vol, components.get("downside_risk"), component_weights.get("downside_risk"))
    built["risk_adjusted_return"] = _explain_risk_adjusted(sortino, components.get("risk_adjusted_return"), component_weights.get("risk_adjusted_return"))
    built["concentration"] = _explain_concentration(contributing_weights, components.get("concentration"), component_weights.get("concentration"))
    built["fund_mix"] = _explain_fund_mix(categories, amcs, components.get("fund_mix"), component_weights.get("fund_mix"))
    overall_details = []
    total = 0.0
    for key in ("return_quality", "downside_risk", "risk_adjusted_return", "concentration", "fund_mix"):
        if key in available:
            w = component_weights.get(key, 0.0)
            s = available[key]
            contrib = float(s) * float(w)
            total += contrib
            overall_details.append(f"{display_names[key]}: {_fmt_num(s,1)} x {_fmt_num(float(w)*100,1)}% = {_fmt_num(contrib,3)}")
        else:
            overall_details.append(f"{display_names[key]}: unavailable (weight renormalized).")
    if score is not None:
        overall_details.append(f"Total: {_fmt_num(total,2)} -> {_fmt_num(score,1)} / 100")
    else:
        overall_details.append("Total: score withheld (insufficient history).")
    conf = _explain_confidence(years, tier, label, has_legacy, score_withheld)
    raw_available = {"cagr": cagr is not None and _finite(cagr), "rolling_1y": bool(rolling and rolling.get("1Y")), "rolling_3y": bool(rolling and rolling.get("3Y")), "rolling_5y": bool(rolling and rolling.get("5Y")), "maximum_drawdown": max_dd is not None and _finite(max_dd), "downside_deviation": ddv is not None and _finite(ddv), "annualized_volatility": vol is not None and _finite(vol), "sortino": sortino is not None and _finite(sortino), "fund_weights": len(contributing_weights) > 0, "categories": any(c for c in categories), "amcs": any(a for a in amcs), "history_years": years is not None and _finite(years)}
    return HealthScoreExplanation(overall_score=score, overall_weight_details=overall_details, total_weighted_contribution=total, components=built, confidence_explanation=conf, raw_metrics_available=raw_available)
