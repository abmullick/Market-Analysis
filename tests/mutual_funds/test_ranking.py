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
