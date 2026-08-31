"""Tests for mutual fund frontend presentation and API response formatting.

Verifies:
- Raw metric values have correct units in API response
- Score vs raw value distinction is clear
- AMC is included in ranking response
- N/A metrics are handled correctly
"""
import pytest

from backend.services.mutual_funds.ranking import RankingEngine


class TestRankingResponseFields:
    """Verify API response includes all necessary display fields."""

    def test_ranking_includes_amc(self):
        """Ranking response should include AMC name for display."""
        engine = RankingEngine()
        funds = [
            {
                "scheme_code": "1",
                "scheme_name": "Test Fund A",
                "amc": "AMC Alpha",
                "category": "Equity",
                "one_year_return": 10.0,
            },
            {
                "scheme_code": "2",
                "scheme_name": "Test Fund B",
                "amc": "AMC Beta",
                "category": "Equity",
                "one_year_return": 20.0,
            },
        ]
        criteria = [{"name": "1Y_return", "weight": 100.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        assert len(rankings) == 2
        for r in rankings:
            assert "amc" in r, "Ranking response should include amc field"
            assert r["amc"] is not None, "AMC should not be None"
            assert r["amc"] in ["AMC Alpha", "AMC Beta"]

    def test_ranking_includes_category(self):
        """Ranking response should include category."""
        engine = RankingEngine()
        funds = [
            {
                "scheme_code": "1",
                "scheme_name": "Test Fund",
                "category": "Equity - Large Cap",
                "one_year_return": 10.0,
            },
        ]
        criteria = [{"name": "1Y_return", "weight": 100.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        assert rankings[0]["category"] == "Equity - Large Cap"

    def test_ranking_overall_score_is_float(self):
        """Overall score should be a float (0-100), not a percentage string."""
        engine = RankingEngine()
        funds = [
            {
                "scheme_code": "1",
                "scheme_name": "Test Fund",
                "one_year_return": 10.0,
            },
            {
                "scheme_code": "2",
                "scheme_name": "Test Fund 2",
                "one_year_return": 20.0,
            },
        ]
        criteria = [{"name": "1Y_return", "weight": 100.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        assert isinstance(rankings[0]["overall_score"], float)
        assert rankings[0]["overall_score"] == 100.0
        assert rankings[1]["overall_score"] == 0.0

    def test_ranking_criteria_scores_include_raw_value(self):
        """Each criterion score should include raw_value for frontend display."""
        engine = RankingEngine()
        funds = [
            {
                "scheme_code": "1",
                "scheme_name": "Test Fund",
                "one_year_return": 0.15,
                "three_year_cagr": 0.12,
                "sharpe_ratio": 1.5,
                "annualized_volatility": 0.18,
                "maximum_drawdown": 0.25,
                "downside_deviation": 0.12,
                "rolling_return_consistency": {"1Y": {"positive_pct": 85.0}},
            },
        ]
        criteria = [
            {"name": "1Y_return", "weight": 20.0},
            {"name": "3Y_cagr", "weight": 20.0},
            {"name": "sharpe_ratio", "weight": 20.0},
            {"name": "volatility", "weight": 20.0},
            {"name": "maximum_drawdown", "weight": 20.0},
        ]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        criteria_scores = rankings[0]["criteria_scores"]
        assert len(criteria_scores) == 5

        for cs in criteria_scores:
            assert "raw_value" in cs, f"Missing raw_value for {cs['criterion']}"
            assert cs["raw_value"] is not None


class TestMetricUnits:
    """Verify backend metric units match frontend expectations."""

    def test_returns_are_decimals_not_percentages(self):
        """Backend returns should be decimals (e.g., 0.18 for 18%), frontend multiplies by 100."""
        engine = RankingEngine()
        funds = [
            {
                "scheme_code": "1",
                "scheme_name": "Test Fund",
                "one_year_return": 0.18,
                "three_year_cagr": 0.22,
                "five_year_cagr": 0.15,
                "ten_year_cagr": 0.10,
            },
        ]
        criteria = [
            {"name": "1Y_return", "weight": 25.0},
            {"name": "3Y_cagr", "weight": 25.0},
            {"name": "5Y_cagr", "weight": 25.0},
            {"name": "10Y_cagr", "weight": 25.0},
        ]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        for cs in rankings[0]["criteria_scores"]:
            if cs["criterion"] in ["1Y_return", "3Y_cagr", "5Y_cagr", "10Y_cagr"]:
                assert cs["raw_value"] < 1.0, f"{cs['criterion']} should be decimal, got {cs['raw_value']}"
                assert cs["raw_value"] >= -1.0

    def test_volatility_is_decimal(self):
        """Backend volatility should be decimal (e.g., 0.17 for 17%)."""
        engine = RankingEngine()
        funds = [
            {
                "scheme_code": "1",
                "scheme_name": "Test Fund",
                "annualized_volatility": 0.17,
                "downside_deviation": 0.12,
            },
        ]
        criteria = [
            {"name": "volatility", "weight": 50.0},
            {"name": "downside_deviation", "weight": 50.0},
        ]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        for cs in rankings[0]["criteria_scores"]:
            if cs["criterion"] == "volatility":
                assert cs["raw_value"] == 0.17
            elif cs["criterion"] == "downside_deviation":
                assert cs["raw_value"] == 0.12

    def test_max_drawdown_is_decimal(self):
        """Backend max_drawdown should be decimal (e.g., 0.2373 for 23.73%)."""
        engine = RankingEngine()
        funds = [
            {
                "scheme_code": "1",
                "scheme_name": "Test Fund",
                "maximum_drawdown": 0.2373,
            },
        ]
        criteria = [{"name": "maximum_drawdown", "weight": 100.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        assert rankings[0]["criteria_scores"][0]["raw_value"] == 0.2373

    def test_sharpe_sortino_are_unitless(self):
        """Sharpe and Sortino should be unitless ratios."""
        engine = RankingEngine()
        funds = [
            {
                "scheme_code": "1",
                "scheme_name": "Test Fund",
                "sharpe_ratio": 1.36,
                "sortino_ratio": 1.86,
            },
        ]
        criteria = [
            {"name": "sharpe_ratio", "weight": 50.0},
            {"name": "sortino_ratio", "weight": 50.0},
        ]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        for cs in rankings[0]["criteria_scores"]:
            if cs["criterion"] == "sharpe_ratio":
                assert cs["raw_value"] == 1.36
            elif cs["criterion"] == "sortino_ratio":
                assert cs["raw_value"] == 1.86

    def test_consistency_is_percentage(self):
        """Consistency positive_pct should be a percentage (e.g., 85.0 for 85%)."""
        engine = RankingEngine()
        funds = [
            {
                "scheme_code": "1",
                "scheme_name": "Test Fund",
                "rolling_return_consistency": {"1Y": {"positive_pct": 85.0}},
            },
        ]
        criteria = [{"name": "consistency", "weight": 100.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        assert rankings[0]["criteria_scores"][0]["raw_value"] == 85.0


class TestNAHandling:
    """Verify N/A metrics are handled correctly."""

    def test_none_metric_produces_none_score(self):
        """None raw_value should produce None score."""
        engine = RankingEngine()
        funds = [
            {
                "scheme_code": "1",
                "scheme_name": "Test Fund",
                "one_year_return": None,
            },
        ]
        criteria = [{"name": "1Y_return", "weight": 100.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        assert rankings[0]["overall_score"] is None
        assert rankings[0]["criteria_scores"][0]["score"] is None
        assert rankings[0]["criteria_scores"][0]["raw_value"] is None

    def test_missing_metric_key_produces_none(self):
        """Missing metric key should produce None score."""
        engine = RankingEngine()
        funds = [
            {
                "scheme_code": "1",
                "scheme_name": "Test Fund",
                # No one_year_return key
            },
        ]
        criteria = [{"name": "1Y_return", "weight": 100.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        assert rankings[0]["overall_score"] is None
        assert rankings[0]["criteria_scores"][0]["score"] is None
        assert rankings[0]["criteria_scores"][0]["raw_value"] is None

    def test_partial_metrics_ranked(self):
        """Fund with some N/A metrics should still be ranked on available metrics."""
        engine = RankingEngine()
        funds = [
            {
                "scheme_code": "1",
                "scheme_name": "Fund A",
                "one_year_return": 10.0,
                "three_year_cagr": None,
            },
            {
                "scheme_code": "2",
                "scheme_name": "Fund B",
                "one_year_return": 20.0,
                "three_year_cagr": 15.0,
            },
        ]
        criteria = [
            {"name": "1Y_return", "weight": 50.0},
            {"name": "3Y_cagr", "weight": 50.0},
        ]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        # Fund A should still be ranked (has 1Y return)
        assert rankings[0]["overall_score"] is not None
        # Fund B should be ranked higher (has both metrics)
        assert rankings[0]["scheme_code"] == "2"
