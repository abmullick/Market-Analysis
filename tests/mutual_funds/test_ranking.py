import pytest

from backend.models.mutual_fund import CriterionConfig, FundMetrics, RankingRequest
from backend.services.mutual_funds.ranking import RankingEngine


def _make_fund(scheme_code, one_year_return=None, three_year_cagr=None, five_year_cagr=None,
                ten_year_cagr=None, sharpe_ratio=None, sortino_ratio=None,
                annualized_volatility=None, maximum_drawdown=None, downside_deviation=None,
                rolling_return_consistency=None, category="Equity"):
    return FundMetrics(
        scheme_code=scheme_code,
        scheme_name=f"Fund {scheme_code}",
        category=category,
        one_year_return=one_year_return,
        three_year_cagr=three_year_cagr,
        five_year_cagr=five_year_cagr,
        ten_year_cagr=ten_year_cagr,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        annualized_volatility=annualized_volatility,
        maximum_drawdown=maximum_drawdown,
        downside_deviation=downside_deviation,
        rolling_return_consistency=rolling_return_consistency,
    )


def test_rank_higher_is_better():
    funds = [
        _make_fund("1", one_year_return=10.0),
        _make_fund("2", one_year_return=20.0),
        _make_fund("3", one_year_return=15.0),
    ]
    engine = RankingEngine()
    request = RankingRequest(category="Equity", criteria=[CriterionConfig(name="1Y_return", weight=100.0)])
    rankings = engine.rank(funds=funds, criteria=[c.model_dump() for c in request.criteria], auto_renormalize=False)
    assert rankings[0]["scheme_code"] == "2"
    assert rankings[0]["overall_score"] == pytest.approx(100.0, abs=1e-6)
    assert rankings[1]["scheme_code"] == "3"
    assert rankings[1]["overall_score"] == pytest.approx(50.0, abs=1e-6)
    assert rankings[2]["scheme_code"] == "1"
    assert rankings[2]["overall_score"] == pytest.approx(0.0, abs=1e-6)


def test_rank_lower_is_better():
    funds = [
        _make_fund("1", annualized_volatility=5.0),
        _make_fund("2", annualized_volatility=15.0),
        _make_fund("3", annualized_volatility=10.0),
    ]
    engine = RankingEngine()
    request = RankingRequest(category="Equity", criteria=[CriterionConfig(name="volatility", weight=100.0)])
    rankings = engine.rank(funds=funds, criteria=[c.model_dump() for c in request.criteria], auto_renormalize=False)
    assert rankings[0]["scheme_code"] == "1"
    assert rankings[0]["overall_score"] == pytest.approx(100.0, abs=1e-6)
    assert rankings[2]["scheme_code"] == "2"
    assert rankings[2]["overall_score"] == pytest.approx(0.0, abs=1e-6)


def test_rank_mixed_criteria():
    funds = [
        _make_fund("1", one_year_return=10.0, annualized_volatility=20.0),
        _make_fund("2", one_year_return=20.0, annualized_volatility=10.0),
    ]
    engine = RankingEngine()
    request = RankingRequest(
        category="Equity",
        criteria=[
            CriterionConfig(name="1Y_return", weight=50.0),
            CriterionConfig(name="volatility", weight=50.0),
        ],
    )
    rankings = engine.rank(funds=funds, criteria=[c.model_dump() for c in request.criteria], auto_renormalize=False)
    assert rankings[0]["scheme_code"] == "2"
    assert rankings[0]["overall_score"] == pytest.approx(100.0, abs=1e-6)
    assert rankings[1]["scheme_code"] == "1"
    assert rankings[1]["overall_score"] == pytest.approx(0.0, abs=1e-6)


def test_auto_renormalize():
    funds = [
        _make_fund("1", one_year_return=10.0),
        _make_fund("2", one_year_return=20.0),
    ]
    engine = RankingEngine()
    request = RankingRequest(
        category="Equity",
        criteria=[CriterionConfig(name="1Y_return", weight=30.0)],
        auto_renormalize=True,
    )
    rankings = engine.rank(funds=funds, criteria=[c.model_dump() for c in request.criteria], auto_renormalize=True)
    assert rankings[0]["overall_score"] == pytest.approx(100.0, abs=1e-6)
    assert rankings[1]["overall_score"] == pytest.approx(0.0, abs=1e-6)
    assert rankings[0]["criteria_scores"][0]["weight"] == pytest.approx(100.0, abs=1e-6)


def test_renormalize_requires_positive_sum():
    engine = RankingEngine()
    funds = [_make_fund("1", one_year_return=10.0)]
    request = RankingRequest(category="Equity", criteria=[CriterionConfig(name="1Y_return", weight=0.0)])
    with pytest.raises(ValueError, match="Sum of weights must be greater than zero"):
        engine.rank(funds=funds, criteria=[c.model_dump() for c in request.criteria], auto_renormalize=True)


def test_no_auto_renormalize_requires_sum_100():
    engine = RankingEngine()
    funds = [_make_fund("1", one_year_return=10.0)]
    request = RankingRequest(category="Equity", criteria=[CriterionConfig(name="1Y_return", weight=50.0)])
    with pytest.raises(ValueError, match="Weights must sum to 100"):
        engine.rank(funds=funds, criteria=[c.model_dump() for c in request.criteria], auto_renormalize=False)


def test_negative_weight_rejected():
    engine = RankingEngine()
    funds = [_make_fund("1", one_year_return=10.0)]
    request = RankingRequest(category="Equity", criteria=[CriterionConfig(name="1Y_return", weight=-10.0)])
    with pytest.raises(ValueError, match="Weight must be non-negative"):
        engine.rank(funds=funds, criteria=[c.model_dump() for c in request.criteria], auto_renormalize=False)


def test_unknown_criterion_rejected():
    engine = RankingEngine()
    funds = [_make_fund("1", one_year_return=10.0)]
    request = RankingRequest(category="Equity", criteria=[CriterionConfig(name="bad_criterion", weight=100.0)])
    with pytest.raises(ValueError, match="Unknown criterion"):
        engine.rank(funds=funds, criteria=[c.model_dump() for c in request.criteria], auto_renormalize=False)


def test_missing_metric_returns_none():
    funds = [
        _make_fund("1", one_year_return=10.0),
        _make_fund("2"),
    ]
    engine = RankingEngine()
    request = RankingRequest(category="Equity", criteria=[CriterionConfig(name="1Y_return", weight=100.0)])
    rankings = engine.rank(funds=funds, criteria=[c.model_dump() for c in request.criteria], auto_renormalize=False)
    assert rankings[0]["scheme_code"] == "1"
    assert rankings[0]["overall_score"] == pytest.approx(100.0, abs=1e-6)
    assert rankings[1]["scheme_code"] == "2"
    assert rankings[1]["overall_score"] is None
    assert rankings[1]["criteria_scores"][0]["score"] is None


def test_consistency_criterion():
    funds = [
        _make_fund("1", rolling_return_consistency={"1Y": {"positive_pct": 80.0}}),
        _make_fund("2", rolling_return_consistency={"1Y": {"positive_pct": 60.0}}),
    ]
    engine = RankingEngine()
    request = RankingRequest(category="Equity", criteria=[CriterionConfig(name="consistency", weight=100.0)])
    rankings = engine.rank(funds=funds, criteria=[c.model_dump() for c in request.criteria], auto_renormalize=False)
    assert rankings[0]["scheme_code"] == "1"
    assert rankings[0]["overall_score"] == pytest.approx(100.0, abs=1e-6)
    assert rankings[1]["scheme_code"] == "2"
    assert rankings[1]["overall_score"] == pytest.approx(0.0, abs=1e-6)


def test_ranks_tied_scores():
    funds = [
        _make_fund("1", one_year_return=10.0),
        _make_fund("2", one_year_return=10.0),
    ]
    engine = RankingEngine()
    request = RankingRequest(category="Equity", criteria=[CriterionConfig(name="1Y_return", weight=100.0)])
    rankings = engine.rank(funds=funds, criteria=[c.model_dump() for c in request.criteria], auto_renormalize=False)
    assert rankings[0]["overall_score"] == pytest.approx(100.0, abs=1e-6)
    assert rankings[1]["overall_score"] == pytest.approx(100.0, abs=1e-6)
    assert rankings[0]["rank"] == 1
    assert rankings[1]["rank"] == 2


def test_empty_funds_or_criteria():
    engine = RankingEngine()
    funds = [_make_fund("1", one_year_return=10.0)]
    assert engine.rank(funds=funds, criteria=[], auto_renormalize=False) == []
    assert engine.rank(funds=[], criteria=[{"name": "1Y_return", "weight": 100.0}], auto_renormalize=False) == []


def test_multiple_criteria_weighted():
    funds = [
        _make_fund("1", one_year_return=10.0, sharpe_ratio=1.0, annualized_volatility=20.0),
        _make_fund("2", one_year_return=20.0, sharpe_ratio=0.5, annualized_volatility=10.0),
    ]
    engine = RankingEngine()
    request = RankingRequest(
        category="Equity",
        criteria=[
            CriterionConfig(name="1Y_return", weight=40.0),
            CriterionConfig(name="sharpe_ratio", weight=30.0),
            CriterionConfig(name="volatility", weight=30.0),
        ],
    )
    rankings = engine.rank(funds=funds, criteria=[c.model_dump() for c in request.criteria], auto_renormalize=False)
    assert rankings[0]["scheme_code"] == "2"
    assert rankings[0]["overall_score"] > 0


def test_ranking_propagates_nav_and_nav_date():
    """Ranking response should include nav and nav_date from source fund data."""
    engine = RankingEngine()
    funds = [
        {
            "scheme_code": "1",
            "scheme_name": "Test Fund A",
            "nav": 45.67,
            "nav_date": "2024-01-15",
            "one_year_return": 10.0,
        },
        {
            "scheme_code": "2",
            "scheme_name": "Test Fund B",
            "nav": 1234.56,
            "nav_date": "2024-01-14",
            "one_year_return": 20.0,
        },
    ]
    criteria = [{"name": "1Y_return", "weight": 100.0}]
    rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

    assert rankings[0]["nav"] == 1234.56
    assert rankings[0]["nav_date"] == "2024-01-14"
    assert rankings[1]["nav"] == 45.67
    assert rankings[1]["nav_date"] == "2024-01-15"


def test_ranking_propagates_data_points():
    """Ranking response should include data_points from source fund data."""
    engine = RankingEngine()
    funds = [
        {
            "scheme_code": "1",
            "scheme_name": "Test Fund A",
            "data_points": 1500,
            "one_year_return": 10.0,
        },
        {
            "scheme_code": "2",
            "scheme_name": "Test Fund B",
            "data_points": 2500,
            "one_year_return": 20.0,
        },
    ]
    criteria = [{"name": "1Y_return", "weight": 100.0}]
    rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

    assert rankings[0]["data_points"] == 2500
    assert rankings[1]["data_points"] == 1500


def test_ranking_handles_missing_metadata():
    """Missing nav, nav_date, and data_points should be None in ranking response."""
    engine = RankingEngine()
    funds = [
        {
            "scheme_code": "1",
            "scheme_name": "Test Fund",
            "one_year_return": 10.0,
        },
    ]
    criteria = [{"name": "1Y_return", "weight": 100.0}]
    rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

    assert rankings[0]["nav"] is None
    assert rankings[0]["nav_date"] is None
    assert rankings[0]["data_points"] is None


def test_ranking_scores_unchanged_with_metadata():
    """Adding metadata fields should not change ranking scores."""
    engine = RankingEngine()
    funds_without_meta = [
        {"scheme_code": "1", "scheme_name": "Fund A", "one_year_return": 10.0},
        {"scheme_code": "2", "scheme_name": "Fund B", "one_year_return": 20.0},
    ]
    funds_with_meta = [
        {"scheme_code": "1", "scheme_name": "Fund A", "nav": 100.0, "nav_date": "2024-01-01", "data_points": 500, "one_year_return": 10.0},
        {"scheme_code": "2", "scheme_name": "Fund B", "nav": 200.0, "nav_date": "2024-01-02", "data_points": 600, "one_year_return": 20.0},
    ]
    criteria = [{"name": "1Y_return", "weight": 100.0}]

    rankings_without = engine.rank(funds=funds_without_meta, criteria=criteria, auto_renormalize=False)
    rankings_with = engine.rank(funds=funds_with_meta, criteria=criteria, auto_renormalize=False)

    assert rankings_without[0]["overall_score"] == rankings_with[0]["overall_score"]
    assert rankings_without[1]["overall_score"] == rankings_with[1]["overall_score"]


class TestRankingResponseStructure:
    """Verify ranking response has all fields needed for frontend output filtering."""

    def test_ranking_includes_criteria_raw_values(self):
        """Each criterion score must include raw_value for filtering."""
        engine = RankingEngine()
        funds = [
            {
                "scheme_code": "1",
                "scheme_name": "Test Fund",
                "one_year_return": 0.15,
                "three_year_cagr": 0.12,
                "sharpe_ratio": 1.5,
                "annualized_volatility": 0.18,
            },
        ]
        criteria = [
            {"name": "1Y_return", "weight": 25.0},
            {"name": "3Y_cagr", "weight": 25.0},
            {"name": "sharpe_ratio", "weight": 25.0},
            {"name": "volatility", "weight": 25.0},
        ]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        cs_map = {cs["criterion"]: cs for cs in rankings[0]["criteria_scores"]}
        assert cs_map["1Y_return"]["raw_value"] == 0.15
        assert cs_map["3Y_cagr"]["raw_value"] == 0.12
        assert cs_map["sharpe_ratio"]["raw_value"] == 1.5
        assert cs_map["volatility"]["raw_value"] == 0.18

    def test_ranking_includes_category(self):
        """Ranking response should include category for each fund."""
        engine = RankingEngine()
        funds = [
            {
                "scheme_code": "1",
                "scheme_name": "Test Fund A",
                "category": "Equity - Large Cap",
                "one_year_return": 10.0,
            },
            {
                "scheme_code": "2",
                "scheme_name": "Test Fund B",
                "category": "Equity - Large Cap",
                "one_year_return": 20.0,
            },
        ]
        criteria = [{"name": "1Y_return", "weight": 100.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        assert rankings[0]["category"] == "Equity - Large Cap"
        assert rankings[1]["category"] == "Equity - Large Cap"

    def test_ranking_returns_decimal_for_percentage_metrics(self):
        """Backend returns decimals for percentage metrics (0.18 = 18%)."""
        engine = RankingEngine()
        funds = [
            {
                "scheme_code": "1",
                "scheme_name": "Test Fund",
                "one_year_return": 0.18,
                "annualized_volatility": 0.17,
                "maximum_drawdown": 0.25,
            },
        ]
        criteria = [
            {"name": "1Y_return", "weight": 33.3},
            {"name": "volatility", "weight": 33.3},
            {"name": "maximum_drawdown", "weight": 33.4},
        ]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        cs_map = {cs["criterion"]: cs for cs in rankings[0]["criteria_scores"]}
        assert cs_map["1Y_return"]["raw_value"] == 0.18
        assert cs_map["volatility"]["raw_value"] == 0.17
        assert cs_map["maximum_drawdown"]["raw_value"] == 0.25

    def test_ranking_overall_score_is_zero_to_hundred(self):
        """Overall score should be on a 0-100 scale."""
        engine = RankingEngine()
        funds = [
            {"scheme_code": "1", "scheme_name": "Fund A", "one_year_return": 10.0},
            {"scheme_code": "2", "scheme_name": "Fund B", "one_year_return": 20.0},
        ]
        criteria = [{"name": "1Y_return", "weight": 100.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)

        assert rankings[0]["overall_score"] == 100.0
        assert rankings[1]["overall_score"] == 0.0


class TestClientSideFilterLogic:
    """Simulate client-side filtering logic to verify correctness."""

    def _make_ranking(self, scheme_code, overall_score=None, **criteria_raw):
        """Create a mock ranking result for filter testing.

        criteria_raw keys should match backend criterion names:
        1Y_return, 3Y_cagr, 5Y_cagr, 10Y_cagr, sharpe_ratio, sortino_ratio,
        volatility, maximum_drawdown, downside_deviation, consistency
        """
        criteria_scores = [
            {"criterion": k, "weight": 100.0, "score": 50.0, "raw_value": v}
            for k, v in criteria_raw.items()
        ]
        return {
            "scheme_code": scheme_code,
            "scheme_name": f"Fund {scheme_code}",
            "overall_score": overall_score,
            "criteria_scores": criteria_scores,
            "nav": None,
            "data_points": None,
        }

    def _filter_rankings(self, rankings, filters):
        """Apply client-side filters with AND logic.

        filters: list of (criterion_key, operator, input_value, unit)
        """
        result = rankings
        for criterion_key, op, input_val, unit in filters:
            if unit == "percent":
                backend_val = input_val / 100
            else:
                backend_val = input_val

            def passes(r):
                if criterion_key == "overall_score":
                    raw = r.get("overall_score")
                elif criterion_key == "aum_cr":
                    raw = r.get("aum_cr")
                else:
                    cs = next((c for c in r.get("criteria_scores", []) if c["criterion"] == criterion_key), None)
                    raw = cs["raw_value"] if cs else None
                if raw is None:
                    return False
                if op == ">=":
                    return raw >= backend_val
                if op == "<=":
                    return raw <= backend_val
                return True

            result = [r for r in result if passes(r)]
        return result

    def test_filter_by_1y_return(self):
        """Filter by 1Y Return >= 20% should keep only funds with raw_value >= 0.20."""
        rankings = [
            self._make_ranking("1", **{"1Y_return": 0.15}),
            self._make_ranking("2", **{"1Y_return": 0.25}),
            self._make_ranking("3", **{"1Y_return": 0.20}),
        ]
        filtered = self._filter_rankings(rankings, [("1Y_return", ">=", 20, "percent")])
        assert len(filtered) == 2
        assert [r["scheme_code"] for r in filtered] == ["2", "3"]

    def test_filter_by_3y_cagr(self):
        """Filter by 3Y CAGR <= 15% should keep only funds with raw_value <= 0.15."""
        rankings = [
            self._make_ranking("1", **{"3Y_cagr": 0.10}),
            self._make_ranking("2", **{"3Y_cagr": 0.20}),
            self._make_ranking("3", **{"3Y_cagr": 0.15}),
        ]
        filtered = self._filter_rankings(rankings, [("3Y_cagr", "<=", 15, "percent")])
        assert len(filtered) == 2
        assert [r["scheme_code"] for r in filtered] == ["1", "3"]

    def test_filter_by_sharpe_ratio(self):
        """Filter by Sharpe >= 1.0 should keep only funds with raw_value >= 1.0."""
        rankings = [
            self._make_ranking("1", **{"sharpe_ratio": 0.8}),
            self._make_ranking("2", **{"sharpe_ratio": 1.2}),
            self._make_ranking("3", **{"sharpe_ratio": 1.0}),
        ]
        filtered = self._filter_rankings(rankings, [("sharpe_ratio", ">=", 1.0, "ratio")])
        assert len(filtered) == 2
        assert [r["scheme_code"] for r in filtered] == ["2", "3"]

    def test_filter_by_overall_score(self):
        """Filter by Overall Score >= 70 should keep only funds with score >= 70."""
        rankings = [
            self._make_ranking("1", overall_score=65.0),
            self._make_ranking("2", overall_score=75.0),
            self._make_ranking("3", overall_score=70.0),
        ]
        filtered = self._filter_rankings(rankings, [("overall_score", ">=", 70, "score")])
        assert len(filtered) == 2
        assert [r["scheme_code"] for r in filtered] == ["2", "3"]

    def test_multiple_filters_and_logic(self):
        """Multiple filters should combine with AND logic."""
        rankings = [
            self._make_ranking("1", overall_score=80.0, **{"1Y_return": 0.25, "sharpe_ratio": 1.2}),
            self._make_ranking("2", overall_score=60.0, **{"1Y_return": 0.25, "sharpe_ratio": 1.2}),
            self._make_ranking("3", overall_score=80.0, **{"1Y_return": 0.15, "sharpe_ratio": 1.2}),
            self._make_ranking("4", overall_score=80.0, **{"1Y_return": 0.25, "sharpe_ratio": 0.8}),
        ]
        filtered = self._filter_rankings(rankings, [
            ("overall_score", ">=", 70, "score"),
            ("1Y_return", ">=", 20, "percent"),
            ("sharpe_ratio", ">=", 1.0, "ratio"),
        ])
        assert len(filtered) == 1
        assert filtered[0]["scheme_code"] == "1"

    def test_na_values_excluded_by_filter(self):
        """Funds with N/A values for a filtered criterion should be excluded."""
        rankings = [
            self._make_ranking("1", **{"1Y_return": 0.25}),
            self._make_ranking("2"),
        ]
        filtered = self._filter_rankings(rankings, [("1Y_return", ">=", 20, "percent")])
        assert len(filtered) == 1
        assert filtered[0]["scheme_code"] == "1"

    def test_clear_filters_restores_all(self):
        """Clearing filters should restore all ranking results."""
        rankings = [
            self._make_ranking("1", **{"1Y_return": 0.15}),
            self._make_ranking("2", **{"1Y_return": 0.25}),
        ]
        filtered = self._filter_rankings(rankings, [("1Y_return", ">=", 20, "percent")])
        assert len(filtered) == 1
        cleared = self._filter_rankings(rankings, [])
        assert len(cleared) == 2

    def test_decimal_backend_compared_correctly_to_percentage_input(self):
        """Backend decimal 0.20 should pass filter for >= 20% input."""
        rankings = [
            self._make_ranking("1", **{"1Y_return": 0.19}),
            self._make_ranking("2", **{"1Y_return": 0.20}),
            self._make_ranking("3", **{"1Y_return": 0.21}),
        ]
        filtered = self._filter_rankings(rankings, [("1Y_return", ">=", 20, "percent")])
        assert len(filtered) == 2
        assert [r["scheme_code"] for r in filtered] == ["2", "3"]

    def test_filtering_does_not_modify_original_rankings(self):
        """Filtering should not modify the original ranking results."""
        rankings = [
            self._make_ranking("1", **{"1Y_return": 0.15}),
            self._make_ranking("2", **{"1Y_return": 0.25}),
        ]
        original_len = len(rankings)
        filtered = self._filter_rankings(rankings, [("1Y_return", ">=", 20, "percent")])
        assert len(rankings) == original_len
        assert len(filtered) == 1

    def test_filter_by_aum(self):
        """Filter by AUM >= 1000 Cr should keep only funds with aum_cr >= 1000."""
        rankings = [
            {"scheme_code": "1", "aum_cr": 500.0, "criteria_scores": []},
            {"scheme_code": "2", "aum_cr": 1500.0, "criteria_scores": []},
            {"scheme_code": "3", "aum_cr": 1000.0, "criteria_scores": []},
        ]
        filtered = self._filter_rankings(rankings, [("aum_cr", ">=", 1000, "currency")])
        assert len(filtered) == 2
        assert [r["scheme_code"] for r in filtered] == ["2", "3"]

    def test_aum_filter_excludes_missing_aum(self):
        """Funds without AUM should be excluded when filtering by AUM."""
        rankings = [
            {"scheme_code": "1", "aum_cr": 1500.0, "criteria_scores": []},
            {"scheme_code": "2", "aum_cr": None, "criteria_scores": []},
            {"scheme_code": "3", "criteria_scores": []},
        ]
        filtered = self._filter_rankings(rankings, [("aum_cr", ">=", 1000, "currency")])
        assert len(filtered) == 1
        assert filtered[0]["scheme_code"] == "1"
