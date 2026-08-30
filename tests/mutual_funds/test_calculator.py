from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from backend.models.mutual_fund import NAVRecord
from backend.services.mutual_funds.calculator import MetricsCalculator


def _make_navs(values, start_date, days_between=1):
    base = datetime.strptime(start_date, "%Y-%m-%d")
    return [
        NAVRecord(date=(base + timedelta(days=i * days_between)).strftime("%Y-%m-%d"), nav=v)
        for i, v in enumerate(values)
    ]


def test_insufficient_data_single_point():
    navs = _make_navs([100.0], "2024-01-01")
    metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
    assert metrics.one_year_return is None
    assert metrics.annualized_volatility is None
    assert metrics.maximum_drawdown is None
    assert metrics.rolling_return_consistency is None


def test_minimal_data_insufficient_for_one_year():
    navs = _make_navs([100.0, 110.0], "2024-01-01")
    metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
    assert metrics.one_year_return is None
    assert metrics.three_year_cagr is None
    assert metrics.annualized_volatility is None
    assert metrics.maximum_drawdown == pytest.approx(0.0)
    assert metrics.sharpe_ratio is None
    assert metrics.sortino_ratio is None


def test_period_returns_and_cagr():
    values = [100.0 + i for i in range(366)]
    navs = _make_navs(values, "2023-01-01")
    metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
    assert metrics.one_year_return == pytest.approx(values[-1] / values[0] - 1, abs=1e-6)
    assert metrics.three_year_cagr is None


def test_cagr_three_year():
    values = [100.0] * 1100
    values[-1] = 200.0
    navs = _make_navs(values, "2020-01-01")
    metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
    expected = (200.0 / 100.0) ** (1 / 3.0) - 1
    assert metrics.three_year_cagr == pytest.approx(expected, rel=1e-3)


def test_cagr_insufficient_history():
    navs = _make_navs([100.0, 110.0], "2024-01-01")
    metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
    assert metrics.three_year_cagr is None
    assert metrics.five_year_cagr is None
    assert metrics.ten_year_cagr is None


def test_annualized_volatility():
    navs = _make_navs([100.0, 90.0, 110.0], "2024-01-01")
    metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
    daily_returns = [-0.10, 110.0 / 90.0 - 1]
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    expected = (variance ** 0.5) * (252 ** 0.5)
    assert metrics.annualized_volatility == pytest.approx(expected, abs=1e-6)


def test_max_drawdown():
    navs = _make_navs([100.0, 110.0, 90.0, 120.0], "2024-01-01")
    metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
    expected = (110.0 - 90.0) / 110.0
    assert metrics.maximum_drawdown == pytest.approx(expected, abs=1e-6)


def test_max_drawdown_no_decline():
    navs = _make_navs([100.0, 110.0, 120.0], "2024-01-01")
    metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
    assert metrics.maximum_drawdown == pytest.approx(0.0, abs=1e-6)


def test_downside_deviation():
    navs = _make_navs([100.0, 90.0, 110.0], "2024-01-01")
    metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
    daily_returns = [-0.10, 110.0 / 90.0 - 1]
    squared_downside = sum(min(r, 0) ** 2 for r in daily_returns)
    mean_sq = squared_downside / len(daily_returns)
    expected = (mean_sq ** 0.5) * (252 ** 0.5)
    assert metrics.downside_deviation == pytest.approx(expected, abs=1e-6)


def test_downside_deviation_all_positive():
    navs = _make_navs([100.0, 110.0, 120.0], "2024-01-01")
    metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
    assert metrics.downside_deviation == pytest.approx(0.0, abs=1e-6)


def test_sharpe_and_sortino():
    navs = _make_navs([100.0, 105.0, 102.0, 108.0], "2024-01-01")
    metrics = MetricsCalculator(scheme_code="123", nav_records=navs, risk_free_rate=0.04).calculate()
    assert metrics.annualized_volatility is not None
    assert metrics.sharpe_ratio is not None
    assert metrics.sortino_ratio is not None
    assert metrics.sharpe_ratio < metrics.sortino_ratio


def test_sharpe_zero_volatility():
    navs = _make_navs([100.0, 100.0, 100.0], "2024-01-01")
    metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
    assert metrics.annualized_volatility == pytest.approx(0.0, abs=1e-6)
    assert metrics.sharpe_ratio is None
    assert metrics.sortino_ratio is None


def test_rolling_consistency_monotonic_growth():
    daily_factor = 1.10 ** (1 / 365)
    values = [100.0 * (daily_factor ** i) for i in range(365 * 6)]
    navs = _make_navs(values, "2018-01-01")
    metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
    consistency = metrics.rolling_return_consistency
    assert consistency is not None
    one_y = consistency["1Y"]
    assert one_y is not None
    assert one_y["windows"] > 0
    assert one_y["positive_pct"] == pytest.approx(100.0, abs=0.01)
    assert one_y["mean_return"] == pytest.approx(0.10, abs=0.001)
    assert one_y["std_return"] == pytest.approx(0.0, abs=0.001)


def test_rolling_consistency_insufficient_windows():
    navs = _make_navs([100.0, 110.0], "2024-01-01")
    metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
    assert metrics.rolling_return_consistency is None


def test_metrics_scheme_code_and_dates():
    navs = _make_navs([100.0, 110.0], "2024-01-01")
    metrics = MetricsCalculator(scheme_code="456", nav_records=navs).calculate()
    assert metrics.scheme_code == "456"
    assert metrics.data_start_date == "2024-01-01"
    assert metrics.data_end_date == "2024-01-02"
    assert metrics.data_points == 2
    assert metrics.calculated_at is not None


def test_zero_start_nav():
    navs = _make_navs([0.0, 110.0], "2024-01-01")
    metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()
    assert metrics.one_year_return is None
    assert metrics.maximum_drawdown == pytest.approx(0.0, abs=1e-6)
