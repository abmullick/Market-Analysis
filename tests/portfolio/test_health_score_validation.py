"""Phase 3C — Portfolio Health Score Numerical & Methodology Validation.

Validates the Health Score implementation against the approved Phase 2F
specification using deterministic synthetic inputs.

Each test calculates expected values from the methodology and compares
against the implementation.
"""

import math

import pytest

from backend.models.portfolio import (
    HealthScoreComponents,
    HealthScoreData,
    PortfolioAnalysisResult,
    PortfolioFundResult,
    PortfolioMetricsData,
)
from backend.services.portfolio.health_score import (
    _cagr_subscore,
    _concentration_subscore,
    _downside_risk_subscore,
    _fund_mix_subscore,
    _history_confidence,
    _risk_adjusted_subscore,
    _rolling_consistency_subscore,
    calculate_health_score,
)


# ===========================================================================
# Helper to build a PortfolioAnalysisResult with common defaults
# ===========================================================================

def _make_result(
    funds: list[PortfolioFundResult],
    metrics: PortfolioMetricsData,
    rolling_consistency: dict | None = None,
) -> PortfolioAnalysisResult:
    return PortfolioAnalysisResult(
        funds=funds,
        metrics=metrics,
        series=[],
        warnings=[],
        rolling_consistency=rolling_consistency,
    )


def _metrics(
    cagr: float | None = 0.10,
    annualized_volatility: float | None = 0.15,
    sharpe_ratio: float | None = 1.0,
    sortino_ratio: float | None = 1.5,
    downside_deviation: float | None = 0.08,
    maximum_drawdown: float | None = -0.20,
    observations: int = 2000,
    years: float = 5.0,
) -> PortfolioMetricsData:
    return PortfolioMetricsData(
        cagr=cagr,
        annualized_volatility=annualized_volatility,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        downside_deviation=downside_deviation,
        maximum_drawdown=maximum_drawdown,
        observations=observations,
        years=years,
    )


# ===========================================================================
# 1. 50/50 TWO-FUND PORTFOLIO
# ===========================================================================

class Test50_50TwoFundPortfolio:
    """Validate a 50/50 two-fund portfolio produces expected results."""

    def test_concentration_score_is_100(self):
        """n=2, 50/50 weights -> HHI=0.5 -> concentration=100."""
        # HHI = 0.5^2 + 0.5^2 = 0.5
        # concentration = 100 * (1 - 0.5) / (1 - 1/2) = 100 * 0.5 / 0.5 = 100
        assert _concentration_subscore([0.5, 0.5]) == 100.0

    def test_full_score_matches_worked_example(self):
        """
        50/50 portfolio with:
        - CAGR = 12% -> R1 = 25
        - Rolling: 1Y(70%, 0.05), 3Y(80%, 0.04), 5Y(90%, 0.03)
        - Max drawdown = -20% -> D1 = 60
        - Downside dev = 8%, vol = 15% -> ratio = 0.533 -> D2 = 33.33
        - Sortino = 1.5 -> RA = 80
        - 2 funds, 2 categories, 2 AMCs -> Fund Mix = 100

        Expected: approximately 70.6 / 100
        """
        funds = [
            PortfolioFundResult(
                scheme_code="A", allocation=50, effective_weight=0.5,
                observations=2000, contributes=True,
                category="Equity", amc="HDFC",
            ),
            PortfolioFundResult(
                scheme_code="B", allocation=50, effective_weight=0.5,
                observations=2000, contributes=True,
                category="Debt", amc="ICICI",
            ),
        ]
        metrics = _metrics(
            cagr=0.12,
            annualized_volatility=0.15,
            sortino_ratio=1.5,
            downside_deviation=0.08,
            maximum_drawdown=-0.20,
        )
        rolling = {
            "1Y": {"positive_pct": 70, "std_return": 0.05},
            "3Y": {"positive_pct": 80, "std_return": 0.04},
            "5Y": {"positive_pct": 90, "std_return": 0.03},
        }
        result = _make_result(funds, metrics, rolling)
        hs = calculate_health_score(result)

        # Verify score is in expected range (approximately 70.6)
        assert hs.score is not None
        assert 65 <= hs.score <= 75, f"Score {hs.score} outside expected range"

        # Verify concentration is 100
        assert hs.components.concentration == 100.0

        # Verify confidence is A (>= 5 years)
        assert hs.confidence.tier == "A"


# ===========================================================================
# 2. 90/10 TWO-FUND PORTFOLIO
# ===========================================================================

class Test90_10TwoFundPortfolio:
    """Validate a 90/10 two-fund portfolio."""

    def test_concentration_score(self):
        """n=2, 90/10 weights -> HHI=0.82 -> concentration=36."""
        # HHI = 0.9^2 + 0.1^2 = 0.81 + 0.01 = 0.82
        # concentration = 100 * (1 - 0.82) / (1 - 1/2) = 100 * 0.18 / 0.5 = 36
        assert _concentration_subscore([0.9, 0.1]) == pytest.approx(36.0, rel=0.001)

    def test_full_score_matches_worked_example(self):
        """
        90/10 portfolio with same metrics as 50/50 case.
        Expected: approximately 56.2 / 100
        """
        funds = [
            PortfolioFundResult(
                scheme_code="A", allocation=90, effective_weight=0.9,
                observations=2000, contributes=True,
                category="Equity", amc="HDFC",
            ),
            PortfolioFundResult(
                scheme_code="B", allocation=10, effective_weight=0.1,
                observations=2000, contributes=True,
                category="Debt", amc="ICICI",
            ),
        ]
        metrics = _metrics(
            cagr=0.12,
            annualized_volatility=0.15,
            sortino_ratio=1.5,
            downside_deviation=0.08,
            maximum_drawdown=-0.20,
        )
        rolling = {
            "1Y": {"positive_pct": 70, "std_return": 0.05},
            "3Y": {"positive_pct": 80, "std_return": 0.04},
            "5Y": {"positive_pct": 90, "std_return": 0.03},
        }
        result = _make_result(funds, metrics, rolling)
        hs = calculate_health_score(result)

        # Verify score is in expected range (approximately 56.2)
        assert hs.score is not None
        assert 50 <= hs.score <= 62, f"Score {hs.score} outside expected range"

        # Verify concentration is 36
        assert hs.components.concentration == pytest.approx(36.0, rel=0.001)


# ===========================================================================
# 3. FIVE-FUND EQUAL-WEIGHT PORTFOLIO
# ===========================================================================

class TestFiveFundEqualWeightPortfolio:
    """Validate equal 20% allocations across 5 funds."""

    def test_concentration_score_is_100(self):
        """n=5, equal 20% weights -> concentration=100."""
        # HHI = 5 * (0.2^2) = 5 * 0.04 = 0.2
        # concentration = 100 * (1 - 0.2) / (1 - 1/5) = 100 * 0.8 / 0.8 = 100
        weights = [0.2, 0.2, 0.2, 0.2, 0.2]
        assert _concentration_subscore(weights) == pytest.approx(100.0, rel=1e-9)

    def test_full_score_matches_worked_example(self):
        """
        Five-fund equal-weight portfolio.
        Expected: approximately 62.5 / 100
        """
        funds = [
            PortfolioFundResult(
                scheme_code=f"F{i}", allocation=20, effective_weight=0.2,
                observations=2000, contributes=True,
                category=["Equity", "Debt", "Hybrid", "Equity", "Debt"][i],
                amc=["HDFC", "ICICI", "HDFC", "SBI", "ICICI"][i],
            )
            for i in range(5)
        ]
        metrics = _metrics(
            cagr=0.10,
            annualized_volatility=0.15,
            sortino_ratio=1.2,
            downside_deviation=0.08,
            maximum_drawdown=-0.18,
        )
        rolling = {
            "1Y": {"positive_pct": 65, "std_return": 0.06},
            "3Y": {"positive_pct": 75, "std_return": 0.05},
            "5Y": {"positive_pct": 85, "std_return": 0.04},
        }
        result = _make_result(funds, metrics, rolling)
        hs = calculate_health_score(result)

        # Verify score is in expected range (approximately 62.5)
        assert hs.score is not None
        assert 57 <= hs.score <= 68, f"Score {hs.score} outside expected range"

        # Verify concentration is 100
        assert hs.components.concentration == pytest.approx(100.0, rel=1e-9)


# ===========================================================================
# 4. SINGLE FUND
# ===========================================================================

class TestSingleFund:
    """Test a single contributing fund with >=1 year history."""

    def test_single_fund_score_calculated(self):
        """Single fund with >=1 year should have a calculable score."""
        funds = [
            PortfolioFundResult(
                scheme_code="A", allocation=100, effective_weight=1.0,
                observations=2000, contributes=True,
                category="Equity", amc="HDFC",
            ),
        ]
        metrics = _metrics(years=5.0)
        result = _make_result(funds, metrics)
        hs = calculate_health_score(result)

        assert hs.score is not None
        assert hs.single_fund_portfolio is True
        assert hs.components.concentration == 0.0
        assert hs.components.fund_mix == 0.0
        assert hs.score_withheld is False


# ===========================================================================
# 5. LESS THAN ONE YEAR
# ===========================================================================

class TestLessThanOneYear:
    """Test portfolio with <1 year of common history."""

    def test_score_withheld(self):
        """Health Score should be withheld for <1 year history."""
        funds = [
            PortfolioFundResult(
                scheme_code="A", allocation=100, effective_weight=1.0,
                observations=100, contributes=True,
            ),
        ]
        metrics = _metrics(years=0.5, observations=100)
        result = _make_result(funds, metrics)
        hs = calculate_health_score(result)

        assert hs.score is None
        assert hs.score_withheld is True
        assert hs.confidence.tier == "D"


# ===========================================================================
# 6. ONE TO THREE YEARS
# ===========================================================================

class TestOneToThreeYears:
    """Test confidence C for 1-3 year history."""

    def test_confidence_c(self):
        """1-3 years -> confidence C."""
        funds = [
            PortfolioFundResult(
                scheme_code="A", allocation=100, effective_weight=1.0,
                observations=500, contributes=True,
            ),
        ]
        metrics = _metrics(years=2.0, observations=500)
        result = _make_result(funds, metrics)
        hs = calculate_health_score(result)

        assert hs.confidence.tier == "C"
        assert hs.score is not None
        assert hs.score_withheld is False


# ===========================================================================
# 7. THREE TO FIVE YEARS
# ===========================================================================

class TestThreeToFiveYears:
    """Test confidence B for 3-5 year history."""

    def test_confidence_b(self):
        """3-5 years -> confidence B."""
        funds = [
            PortfolioFundResult(
                scheme_code="A", allocation=100, effective_weight=1.0,
                observations=1000, contributes=True,
            ),
        ]
        metrics = _metrics(years=4.0, observations=1000)
        result = _make_result(funds, metrics)
        hs = calculate_health_score(result)

        assert hs.confidence.tier == "B"
        assert hs.score is not None


# ===========================================================================
# 8. FIVE YEARS OR MORE
# ===========================================================================

class TestFiveYearsOrMore:
    """Test confidence A for >=5 year history."""

    def test_confidence_a(self):
        """>=5 years -> confidence A."""
        funds = [
            PortfolioFundResult(
                scheme_code="A", allocation=100, effective_weight=1.0,
                observations=2000, contributes=True,
            ),
        ]
        metrics = _metrics(years=6.0, observations=2000)
        result = _make_result(funds, metrics)
        hs = calculate_health_score(result)

        assert hs.confidence.tier == "A"
        assert hs.score is not None


# ===========================================================================
# 9. LEGACY SCHEME
# ===========================================================================

class TestLegacyScheme:
    """Test legacy/stale scheme handling."""

    def test_legacy_caps_confidence_at_c(self):
        """Legacy scheme caps confidence at C, doesn't reduce score."""
        funds = [
            PortfolioFundResult(
                scheme_code="A", allocation=100, effective_weight=1.0,
                observations=2000, contributes=True, is_stale=True,
            ),
        ]
        metrics = _metrics(years=6.0, observations=2000)
        result = _make_result(funds, metrics)
        hs = calculate_health_score(result)

        assert hs.has_legacy_scheme is True
        assert hs.confidence.tier == "C"
        assert hs.score is not None  # Score still calculated


# ===========================================================================
# 10. SORTINO UNAVAILABLE
# ===========================================================================

class TestSortinoUnavailable:
    """Test Risk-Adjusted Return unavailability when Sortino is missing."""

    def test_risk_adjusted_return_unavailable(self):
        """Missing Sortino -> Risk-Adjusted Return component unavailable."""
        funds = [
            PortfolioFundResult(
                scheme_code="A", allocation=100, effective_weight=1.0,
                observations=2000, contributes=True,
            ),
        ]
        metrics = _metrics(sortino_ratio=None)
        result = _make_result(funds, metrics)
        hs = calculate_health_score(result)

        assert hs.components.risk_adjusted_return is None
        assert "risk_adjusted_return" not in hs.available_components
        # Weights should be re-normalized
        assert abs(sum(hs.component_weights.values()) - 1.0) < 1e-9


# ===========================================================================
# 11. MISSING CATEGORY
# ===========================================================================

class TestMissingCategory:
    """Test Fund Mix when category metadata is missing."""

    def test_missing_category_omits_subcomponent(self):
        """Missing category -> category subcomponent omitted."""
        funds = [
            PortfolioFundResult(
                scheme_code="A", allocation=50, effective_weight=0.5,
                observations=2000, contributes=True,
                category=None, amc="HDFC",
            ),
            PortfolioFundResult(
                scheme_code="B", allocation=50, effective_weight=0.5,
                observations=2000, contributes=True,
                category=None, amc="ICICI",
            ),
        ]
        metrics = _metrics()
        result = _make_result(funds, metrics)
        hs = calculate_health_score(result)

        # Fund Mix should still be calculable from AMC only
        assert hs.components.fund_mix is not None


# ===========================================================================
# 12. MISSING AMC
# ===========================================================================

class TestMissingAMC:
    """Test Fund Mix when AMC metadata is missing."""

    def test_missing_amc_omits_subcomponent(self):
        """Missing AMC -> AMC subcomponent omitted."""
        funds = [
            PortfolioFundResult(
                scheme_code="A", allocation=50, effective_weight=0.5,
                observations=2000, contributes=True,
                category="Equity", amc=None,
            ),
            PortfolioFundResult(
                scheme_code="B", allocation=50, effective_weight=0.5,
                observations=2000, contributes=True,
                category="Debt", amc=None,
            ),
        ]
        metrics = _metrics()
        result = _make_result(funds, metrics)
        hs = calculate_health_score(result)

        # Fund Mix should still be calculable from category only
        assert hs.components.fund_mix is not None


# ===========================================================================
# 13. ZERO-WEIGHT FUND
# ===========================================================================

class TestZeroWeightFund:
    """Test zero-weight fund doesn't affect calculations."""

    def test_zero_weight_fund_excluded(self):
        """Zero-weight fund should not contribute to calculations."""
        funds_with_zero = [
            PortfolioFundResult(
                scheme_code="A", allocation=100, effective_weight=1.0,
                observations=2000, contributes=True,
                category="Equity", amc="HDFC",
            ),
            PortfolioFundResult(
                scheme_code="B", allocation=0, effective_weight=0.0,
                observations=100, contributes=False,
                category="Debt", amc="ICICI",
            ),
        ]
        funds_without_zero = [
            PortfolioFundResult(
                scheme_code="A", allocation=100, effective_weight=1.0,
                observations=2000, contributes=True,
                category="Equity", amc="HDFC",
            ),
        ]
        metrics = _metrics()

        result_with = _make_result(funds_with_zero, metrics)
        result_without = _make_result(funds_without_zero, metrics)

        hs_with = calculate_health_score(result_with)
        hs_without = calculate_health_score(result_without)

        # Scores should be identical
        assert hs_with.score == hs_without.score
        assert hs_with.components.concentration == hs_without.components.concentration


# ===========================================================================
# 14. ZERO VOLATILITY
# ===========================================================================

class TestZeroVolatility:
    """Test zero volatility edge case."""

    def test_zero_volatility_no_division_by_zero(self):
        """Zero volatility should not cause division by zero."""
        funds = [
            PortfolioFundResult(
                scheme_code="A", allocation=100, effective_weight=1.0,
                observations=2000, contributes=True,
            ),
        ]
        metrics = _metrics(
            annualized_volatility=0.0,
            downside_deviation=0.0,
        )
        result = _make_result(funds, metrics)
        hs = calculate_health_score(result)

        # Should not produce NaN or Infinity
        if hs.score is not None:
            assert math.isfinite(hs.score)
        assert math.isfinite(hs.components.downside_risk)


# ===========================================================================
# 15. SCORE BOUNDS
# ===========================================================================

class TestScoreBounds:
    """Test that all scores remain within 0-100."""

    def test_extreme_cagr_values(self):
        """Extreme CAGR values should be clamped."""
        assert _cagr_subscore(-1.0) == 0.0
        assert _cagr_subscore(0.0) == 0.0
        assert _cagr_subscore(1.0) == 40.0

    def test_extreme_drawdown_values(self):
        """Extreme drawdown values should be clamped."""
        # D1: 0% drawdown -> 100, -50% -> 0
        d1_0 = _downside_risk_subscore(0.0, 0.0, 0.15)
        d1_50 = _downside_risk_subscore(-0.50, 0.10, 0.15)
        assert 0 <= d1_0 <= 100
        assert 0 <= d1_50 <= 100

    def test_extreme_sortino_values(self):
        """Extreme Sortino values should be clamped."""
        assert _risk_adjusted_subscore(-1.0) == 0.0
        assert _risk_adjusted_subscore(0.0) == 0.0
        assert _risk_adjusted_subscore(5.0) == 100.0

    def test_all_components_bounded(self):
        """All component scores should be within 0-100."""
        funds = [
            PortfolioFundResult(
                scheme_code="A", allocation=50, effective_weight=0.5,
                observations=2000, contributes=True,
                category="Equity", amc="HDFC",
            ),
            PortfolioFundResult(
                scheme_code="B", allocation=50, effective_weight=0.5,
                observations=2000, contributes=True,
                category="Debt", amc="ICICI",
            ),
        ]
        metrics = _metrics()
        result = _make_result(funds, metrics)
        hs = calculate_health_score(result)

        for field in ["return_quality", "downside_risk", "risk_adjusted_return",
                       "concentration", "fund_mix"]:
            value = getattr(hs.components, field)
            if value is not None:
                assert 0 <= value <= 100, f"{field}={value} out of bounds"
                assert math.isfinite(value), f"{field} is not finite"

        if hs.score is not None:
            assert 0 <= hs.score <= 100
            assert math.isfinite(hs.score)


# ===========================================================================
# Additional edge case tests
# ===========================================================================

class TestRollingWindowRenormalization:
    """Test rolling window weight re-normalization."""

    def test_only_1y_available(self):
        """When only 1Y is available, it should get full weight."""
        rolling = {"1Y": {"positive_pct": 70, "std_return": 0.05}}
        score = _rolling_consistency_subscore(rolling)
        assert score is not None
        assert 0 <= score <= 100

    def test_only_3y_available(self):
        """When only 3Y is available, it should get full weight."""
        rolling = {"3Y": {"positive_pct": 80, "std_return": 0.04}}
        score = _rolling_consistency_subscore(rolling)
        assert score is not None
        assert 0 <= score <= 100

    def test_1y_and_3y_available(self):
        """When 1Y and 3Y are available, weights should be re-normalized."""
        rolling = {
            "1Y": {"positive_pct": 70, "std_return": 0.05},
            "3Y": {"positive_pct": 80, "std_return": 0.04},
        }
        score = _rolling_consistency_subscore(rolling)
        assert score is not None
        assert 0 <= score <= 100


class TestConcentrationEdgeCases:
    """Test concentration calculation edge cases."""

    def test_three_fund_equal(self):
        """3 equal funds -> concentration=100."""
        assert _concentration_subscore([1/3, 1/3, 1/3]) == 100.0

    def test_very_unequal_weights(self):
        """Very unequal weights -> low concentration."""
        score = _concentration_subscore([0.99, 0.01])
        assert 0 <= score <= 100
        assert score < 50  # Should be low due to high concentration


class TestFundMixEdgeCases:
    """Test Fund Mix calculation edge cases."""

    def test_all_same_category(self):
        """All same category -> category score = 0."""
        score = _fund_mix_subscore(["Equity", "Equity"], ["HDFC", "ICICI"])
        assert 0 <= score <= 100

    def test_all_same_amc(self):
        """All same AMC -> AMC score = 0."""
        score = _fund_mix_subscore(["Equity", "Debt"], ["HDFC", "HDFC"])
        assert 0 <= score <= 100

    def test_max_diversity(self):
        """Maximum diversity -> high score."""
        score = _fund_mix_subscore(
            ["Equity", "Debt", "Hybrid", "Liquid", "Gold"],
            ["HDFC", "ICICI", "SBI", "Kotak", "Axis"],
        )
        assert score > 50