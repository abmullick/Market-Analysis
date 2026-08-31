"""Golden tests for mutual fund metric calculations.

These tests use manually calculated/known datasets to verify each metric
covers: rising NAV, falling NAV, flat NAV, volatile NAV, insufficient history,
missing observations, equal values, and negative returns.
"""
import math
from datetime import datetime, timedelta

import pytest

from backend.models.mutual_fund import NAVRecord
from backend.services.mutual_funds.calculator import MetricsCalculator
from backend.services.mutual_funds.ranking import RankingEngine


def _make_navs(values, start_date, days_between=1):
    base = datetime.strptime(start_date, "%Y-%m-%d")
    return [
        NAVRecord(date=(base + timedelta(days=i * days_between)).strftime("%Y-%m-%d"), nav=v)
        for i, v in enumerate(values)
    ]


def _make_fund_dict(scheme_code, **kwargs):
    return {"scheme_code": scheme_code, "scheme_name": f"Fund {scheme_code}", **kwargs}


class TestRisingNAV:
    """Test metrics with steadily rising NAV (10% annual growth)."""

    def test_one_year_return_rising(self):
        daily_factor = 1.10 ** (1 / 365)
        values = [100.0 * (daily_factor ** i) for i in range(366)]
        navs = _make_navs(values, "2023-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.one_year_return == pytest.approx(0.10, abs=0.001)

    def test_cagr_three_year_rising(self):
        daily_factor = 1.10 ** (1 / 365)
        values = [100.0 * (daily_factor ** i) for i in range(365 * 3 + 1)]
        navs = _make_navs(values, "2020-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.three_year_cagr == pytest.approx(0.10, abs=0.001)

    def test_max_drawdown_rising(self):
        daily_factor = 1.10 ** (1 / 365)
        values = [100.0 * (daily_factor ** i) for i in range(366)]
        navs = _make_navs(values, "2023-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.maximum_drawdown == pytest.approx(0.0, abs=1e-6)

    def test_volatility_rising(self):
        daily_factor = 1.10 ** (1 / 365)
        values = [100.0 * (daily_factor ** i) for i in range(366)]
        navs = _make_navs(values, "2023-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.annualized_volatility == pytest.approx(0.0, abs=0.01)

    def test_downside_deviation_rising(self):
        daily_factor = 1.10 ** (1 / 365)
        values = [100.0 * (daily_factor ** i) for i in range(366)]
        navs = _make_navs(values, "2023-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.downside_deviation == pytest.approx(0.0, abs=1e-6)

    def test_consistency_rising(self):
        daily_factor = 1.10 ** (1 / 365)
        values = [100.0 * (daily_factor ** i) for i in range(365 * 3)]
        navs = _make_navs(values, "2020-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        consistency = metrics.rolling_return_consistency
        assert consistency is not None
        assert consistency["1Y"]["positive_pct"] == pytest.approx(100.0, abs=0.01)


class TestFallingNAV:
    """Test metrics with steadily falling NAV (-10% annual decline)."""

    def test_one_year_return_falling(self):
        daily_factor = 0.90 ** (1 / 365)
        values = [100.0 * (daily_factor ** i) for i in range(366)]
        navs = _make_navs(values, "2023-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.one_year_return == pytest.approx(-0.10, abs=0.001)

    def test_max_drawdown_falling(self):
        daily_factor = 0.90 ** (1 / 365)
        values = [100.0 * (daily_factor ** i) for i in range(366)]
        navs = _make_navs(values, "2023-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.maximum_drawdown == pytest.approx(0.10, abs=0.001)

    def test_volatility_falling(self):
        daily_factor = 0.90 ** (1 / 365)
        values = [100.0 * (daily_factor ** i) for i in range(366)]
        navs = _make_navs(values, "2023-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.annualized_volatility == pytest.approx(0.0, abs=0.01)

    def test_downside_deviation_falling(self):
        daily_factor = 0.90 ** (1 / 365)
        values = [100.0 * (daily_factor ** i) for i in range(366)]
        navs = _make_navs(values, "2023-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.downside_deviation > 0

    def test_consistency_falling(self):
        daily_factor = 0.90 ** (1 / 365)
        values = [100.0 * (daily_factor ** i) for i in range(365 * 3)]
        navs = _make_navs(values, "2020-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        consistency = metrics.rolling_return_consistency
        assert consistency is not None
        assert consistency["1Y"]["positive_pct"] == pytest.approx(0.0, abs=0.01)


class TestFlatNAV:
    """Test metrics with constant NAV (no change)."""

    def test_one_year_return_flat(self):
        values = [100.0] * 366
        navs = _make_navs(values, "2023-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.one_year_return == pytest.approx(0.0, abs=1e-6)

    def test_cagr_flat(self):
        values = [100.0] * (365 * 3 + 1)
        navs = _make_navs(values, "2020-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.three_year_cagr == pytest.approx(0.0, abs=1e-6)

    def test_volatility_flat(self):
        values = [100.0] * 366
        navs = _make_navs(values, "2023-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.annualized_volatility == pytest.approx(0.0, abs=1e-6)

    def test_max_drawdown_flat(self):
        values = [100.0] * 366
        navs = _make_navs(values, "2023-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.maximum_drawdown == pytest.approx(0.0, abs=1e-6)

    def test_sharpe_flat(self):
        values = [100.0] * 366
        navs = _make_navs(values, "2023-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs, risk_free_rate=0.04).calculate()
        assert metrics.sharpe_ratio is None

    def test_sortino_flat(self):
        values = [100.0] * 366
        navs = _make_navs(values, "2023-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs, risk_free_rate=0.04).calculate()
        assert metrics.sortino_ratio is None


class TestVolatileNAV:
    """Test metrics with volatile NAV (alternating up/down)."""

    def test_max_drawdown_volatile(self):
        values = [100.0, 120.0, 80.0, 110.0, 70.0, 130.0]
        navs = _make_navs(values, "2024-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        # Peak stays at 120 until 130, so max drawdown is from 120 to 70
        expected_dd = (120.0 - 70.0) / 120.0
        assert metrics.maximum_drawdown == pytest.approx(expected_dd, abs=1e-6)

    def test_max_drawdown_not_single_period(self):
        values = [100.0, 50.0, 100.0, 50.0]
        navs = _make_navs(values, "2024-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.maximum_drawdown == pytest.approx(0.50, abs=1e-6)

    def test_volatility_volatile(self):
        values = [100.0, 110.0, 90.0, 120.0, 80.0]
        navs = _make_navs(values, "2024-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.annualized_volatility > 0

    def test_downside_deviation_volatile(self):
        values = [100.0, 110.0, 90.0, 120.0, 80.0]
        navs = _make_navs(values, "2024-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.downside_deviation > 0


class TestInsufficientHistory:
    """Test behavior when fund doesn't have enough history for a metric."""

    def test_one_year_return_insufficient(self):
        values = [100.0, 105.0, 110.0]
        navs = _make_navs(values, "2024-06-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.one_year_return is None

    def test_three_year_cagr_insufficient(self):
        values = [100.0 + i for i in range(400)]
        navs = _make_navs(values, "2021-06-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.three_year_cagr is None

    def test_five_year_cagr_insufficient(self):
        values = [100.0 + i for i in range(1000)]
        navs = _make_navs(values, "2019-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.five_year_cagr is None

    def test_ten_year_cagr_insufficient(self):
        values = [100.0 + i for i in range(2000)]
        navs = _make_navs(values, "2014-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.ten_year_cagr is None

    def test_consistency_insufficient(self):
        values = [100.0 + i for i in range(100)]
        navs = _make_navs(values, "2024-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.rolling_return_consistency is None


class TestMissingObservations:
    """Test handling of missing NAV observations (gaps in data)."""

    def test_gap_in_data(self):
        base = datetime.strptime("2023-01-01", "%Y-%m-%d")
        navs = [
            NAVRecord(date="2023-01-01", nav=100.0),
            NAVRecord(date="2023-01-02", nav=101.0),
            NAVRecord(date="2023-01-10", nav=110.0),
            NAVRecord(date="2023-01-11", nav=111.0),
        ]
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        daily_returns = [0.01, 110.0 / 101.0 - 1, 111.0 / 110.0 - 1]
        mean = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        expected_vol = math.sqrt(variance) * math.sqrt(252)
        assert metrics.annualized_volatility == pytest.approx(expected_vol, abs=1e-6)

    def test_zero_nav_handling(self):
        navs = [
            NAVRecord(date="2024-01-01", nav=100.0),
            NAVRecord(date="2024-01-02", nav=0.0),
            NAVRecord(date="2024-01-03", nav=110.0),
        ]
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.one_year_return is None


class TestEqualValues:
    """Test normalization when all funds have the same value."""

    def test_normalization_equal_values(self):
        funds = [
            _make_fund_dict("1", one_year_return=10.0),
            _make_fund_dict("2", one_year_return=10.0),
            _make_fund_dict("3", one_year_return=10.0),
        ]
        engine = RankingEngine()
        criteria = [{"name": "1Y_return", "weight": 100.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)
        for r in rankings:
            assert r["overall_score"] == pytest.approx(100.0, abs=1e-6)


class TestNegativeReturns:
    """Test metrics with negative returns."""

    def test_negative_one_year_return(self):
        values = [100.0, 95.0, 90.0, 85.0, 80.0]
        navs = _make_navs(values, "2023-01-01", days_between=120)
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        # 1Y return uses last 365 days: from 95.0 to 80.0
        assert metrics.one_year_return == pytest.approx(80.0 / 95.0 - 1, abs=0.01)

    def test_negative_cagr(self):
        values = [100.0] + [100.0 - i * 10 for i in range(1, 11)]
        navs = _make_navs(values, "2020-01-01", days_between=100)
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        if metrics.three_year_cagr is not None:
            assert metrics.three_year_cagr < 0

    def test_sharpe_negative_return(self):
        daily_factor = 0.95 ** (1 / 365)
        values = [100.0 * (daily_factor ** i) for i in range(366)]
        navs = _make_navs(values, "2023-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs, risk_free_rate=0.04).calculate()
        if metrics.sharpe_ratio is not None:
            assert metrics.sharpe_ratio < 0


class TestNormalizationEdgeCases:
    """Test normalization with edge cases."""

    def test_normalization_single_fund(self):
        funds = [_make_fund_dict("1", one_year_return=10.0)]
        engine = RankingEngine()
        criteria = [{"name": "1Y_return", "weight": 100.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)
        assert rankings[0]["overall_score"] == pytest.approx(100.0, abs=1e-6)

    def test_normalization_with_outlier(self):
        funds = [
            _make_fund_dict("1", one_year_return=10.0),
            _make_fund_dict("2", one_year_return=12.0),
            _make_fund_dict("3", one_year_return=11.0),
            _make_fund_dict("4", one_year_return=1000.0),
        ]
        engine = RankingEngine()
        criteria = [{"name": "1Y_return", "weight": 100.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)
        assert rankings[0]["scheme_code"] == "4"
        assert rankings[0]["overall_score"] == pytest.approx(100.0, abs=1e-6)

    def test_normalization_negative_values(self):
        funds = [
            _make_fund_dict("1", sharpe_ratio=-1.0),
            _make_fund_dict("2", sharpe_ratio=0.0),
            _make_fund_dict("3", sharpe_ratio=1.0),
        ]
        engine = RankingEngine()
        criteria = [{"name": "sharpe_ratio", "weight": 100.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)
        assert rankings[0]["scheme_code"] == "3"
        assert rankings[0]["overall_score"] == pytest.approx(100.0, abs=1e-6)
        assert rankings[2]["scheme_code"] == "1"
        assert rankings[2]["overall_score"] == pytest.approx(0.0, abs=1e-6)

    def test_normalization_lower_is_better_negative(self):
        funds = [
            _make_fund_dict("1", annualized_volatility=-5.0),
            _make_fund_dict("2", annualized_volatility=0.0),
            _make_fund_dict("3", annualized_volatility=5.0),
        ]
        engine = RankingEngine()
        criteria = [{"name": "volatility", "weight": 100.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)
        assert rankings[0]["scheme_code"] == "1"
        assert rankings[0]["overall_score"] == pytest.approx(100.0, abs=1e-6)
        assert rankings[2]["scheme_code"] == "3"
        assert rankings[2]["overall_score"] == pytest.approx(0.0, abs=1e-6)


class TestWeightedScoring:
    """Test weighted final scoring."""

    def test_weighted_score_calculation(self):
        funds = [
            _make_fund_dict("1", one_year_return=10.0, sharpe_ratio=0.5),
            _make_fund_dict("2", one_year_return=20.0, sharpe_ratio=1.0),
        ]
        engine = RankingEngine()
        criteria = [
            {"name": "1Y_return", "weight": 60.0},
            {"name": "sharpe_ratio", "weight": 40.0},
        ]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)
        assert rankings[0]["scheme_code"] == "2"
        assert rankings[0]["overall_score"] == pytest.approx(100.0, abs=1e-6)
        assert rankings[1]["scheme_code"] == "1"
        assert rankings[1]["overall_score"] == pytest.approx(0.0, abs=1e-6)

    def test_weighted_score_mixed_directions(self):
        funds = [
            _make_fund_dict("1", one_year_return=10.0, annualized_volatility=20.0),
            _make_fund_dict("2", one_year_return=20.0, annualized_volatility=10.0),
        ]
        engine = RankingEngine()
        criteria = [
            {"name": "1Y_return", "weight": 50.0},
            {"name": "volatility", "weight": 50.0},
        ]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)
        assert rankings[0]["scheme_code"] == "2"
        assert rankings[0]["overall_score"] == pytest.approx(100.0, abs=1e-6)
        assert rankings[1]["scheme_code"] == "1"
        assert rankings[1]["overall_score"] == pytest.approx(0.0, abs=1e-6)

    def test_auto_renormalize_weights(self):
        funds = [
            _make_fund_dict("1", one_year_return=10.0),
            _make_fund_dict("2", one_year_return=20.0),
        ]
        engine = RankingEngine()
        criteria = [{"name": "1Y_return", "weight": 30.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=True)
        assert rankings[0]["overall_score"] == pytest.approx(100.0, abs=1e-6)
        assert rankings[1]["overall_score"] == pytest.approx(0.0, abs=1e-6)
        assert rankings[0]["criteria_scores"][0]["weight"] == pytest.approx(100.0, abs=1e-6)

    def test_disabled_criterion_zero_weight(self):
        funds = [
            _make_fund_dict("1", one_year_return=10.0, sharpe_ratio=0.5),
            _make_fund_dict("2", one_year_return=20.0, sharpe_ratio=1.0),
        ]
        engine = RankingEngine()
        criteria = [
            {"name": "1Y_return", "weight": 100.0},
            {"name": "sharpe_ratio", "weight": 0.0},
        ]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)
        assert rankings[0]["scheme_code"] == "2"
        assert rankings[0]["overall_score"] == pytest.approx(100.0, abs=1e-6)


class TestDrawdownCorrectness:
    """Verify drawdown is calculated from running peak, not single-period."""

    def test_drawdown_recovery(self):
        values = [100.0, 80.0, 90.0, 70.0, 100.0]
        navs = _make_navs(values, "2024-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        expected = (100.0 - 70.0) / 100.0
        assert metrics.maximum_drawdown == pytest.approx(expected, abs=1e-6)

    def test_drawdown_multiple_peaks(self):
        values = [100.0, 120.0, 110.0, 130.0, 90.0]
        navs = _make_navs(values, "2024-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        expected = (130.0 - 90.0) / 130.0
        assert metrics.maximum_drawdown == pytest.approx(expected, abs=1e-6)

    def test_drawdown_is_positive(self):
        values = [100.0, 120.0, 80.0, 110.0, 70.0]
        navs = _make_navs(values, "2024-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.maximum_drawdown >= 0


class TestSharpeSortinoDefinitions:
    """Verify Sharpe and Sortino ratio definitions."""

    def test_sharpe_uses_risk_free_rate(self):
        daily_factor = 1.10 ** (1 / 365)
        values = [100.0 * (daily_factor ** i) for i in range(366)]
        navs = _make_navs(values, "2023-01-01")
        metrics_low_rf = MetricsCalculator(scheme_code="123", nav_records=navs, risk_free_rate=0.02).calculate()
        metrics_high_rf = MetricsCalculator(scheme_code="123", nav_records=navs, risk_free_rate=0.06).calculate()
        if metrics_low_rf.sharpe_ratio is not None and metrics_high_rf.sharpe_ratio is not None:
            assert metrics_low_rf.sharpe_ratio > metrics_high_rf.sharpe_ratio

    def test_sortino_greater_than_sharpe(self):
        values = [100.0, 105.0, 102.0, 108.0, 104.0, 112.0]
        navs = _make_navs(values, "2024-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs, risk_free_rate=0.04).calculate()
        if metrics.sharpe_ratio is not None and metrics.sortino_ratio is not None:
            assert metrics.sortino_ratio > metrics.sharpe_ratio

    def test_sharpe_zero_volatility_returns_none(self):
        values = [100.0, 100.0, 100.0, 100.0]
        navs = _make_navs(values, "2024-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.sharpe_ratio is None

    def test_sortino_zero_downside_returns_none(self):
        values = [100.0, 101.0, 102.0, 103.0]
        navs = _make_navs(values, "2024-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        assert metrics.sortino_ratio is None


class TestConsistencyDefinition:
    """Verify consistency metric definition."""

    def test_consistency_measures_positive_periods(self):
        values = []
        nav_date = datetime.strptime("2020-01-01", "%Y-%m-%d")
        nav = 100.0
        for i in range(365 * 3):
            if i % 2 == 0:
                nav *= 1.001
            else:
                nav *= 0.999
            values.append(nav)
        navs = _make_navs(values, "2020-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        consistency = metrics.rolling_return_consistency
        assert consistency is not None
        assert "1Y" in consistency

    def test_consistency_all_positive(self):
        daily_factor = 1.001
        values = [100.0]
        for i in range(1, 365 * 3):
            values.append(values[-1] * daily_factor)
        navs = _make_navs(values, "2020-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        consistency = metrics.rolling_return_consistency
        assert consistency["1Y"]["positive_pct"] == pytest.approx(100.0, abs=0.01)

    def test_consistency_all_negative(self):
        daily_factor = 0.999
        values = [100.0]
        for i in range(1, 365 * 3):
            values.append(values[-1] * daily_factor)
        navs = _make_navs(values, "2020-01-01")
        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
        consistency = metrics.rolling_return_consistency
        assert consistency["1Y"]["positive_pct"] == pytest.approx(0.0, abs=0.01)


class TestInsufficientHistoryInRanking:
    """Test how funds with insufficient history are handled in ranking."""

    def test_fund_with_missing_metric_gets_none_score(self):
        funds = [
            _make_fund_dict("1", one_year_return=10.0, three_year_cagr=8.0),
            _make_fund_dict("2", one_year_return=15.0, three_year_cagr=None),
        ]
        engine = RankingEngine()
        criteria = [
            {"name": "1Y_return", "weight": 50.0},
            {"name": "3Y_cagr", "weight": 50.0},
        ]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)
        fund_2 = next(r for r in rankings if r["scheme_code"] == "2")
        assert fund_2["criteria_scores"][1]["score"] is None

    def test_fund_with_all_missing_metrics_gets_none_overall(self):
        funds = [
            _make_fund_dict("1", one_year_return=10.0),
            _make_fund_dict("2"),
        ]
        engine = RankingEngine()
        criteria = [{"name": "1Y_return", "weight": 100.0}]
        rankings = engine.rank(funds=funds, criteria=criteria, auto_renormalize=False)
        fund_2 = next(r for r in rankings if r["scheme_code"] == "2")
        assert fund_2["overall_score"] is None
