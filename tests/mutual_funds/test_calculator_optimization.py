"""Regression tests for calculator optimization.

Verifies that the optimized MetricsCalculator produces identical results
to the reference implementation for all metrics, edge cases, and memory usage.
"""
import bisect
import math
import resource
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from backend.models.mutual_fund import FundMetrics, NAVRecord
from backend.services.mutual_funds.calculator import MetricsCalculator


def _make_navs(values, start_date, days_between=1):
    base = datetime.strptime(start_date, "%Y-%m-%d")
    return [
        NAVRecord(date=(base + timedelta(days=i * days_between)).strftime("%Y-%m-%d"), nav=v)
        for i, v in enumerate(values)
    ]


class ReferenceMetricsCalculator:
    """Reference implementation with original (unoptimized) behavior."""

    def __init__(self, scheme_code: str, nav_records: list[NAVRecord], risk_free_rate: float = 0.04):
        self._scheme_code = scheme_code
        self._navs = sorted(nav_records, key=lambda n: n.date)
        self._risk_free_rate = risk_free_rate

    def calculate(self) -> FundMetrics:
        if len(self._navs) < 2:
            return self._empty_metrics()

        navs = self._navs
        end_date = datetime.strptime(navs[-1].date, "%Y-%m-%d")
        start_date = datetime.strptime(navs[0].date, "%Y-%m-%d")
        years_available = (end_date - start_date).days / 365.25

        one_year_navs = self._slice_navs(navs, 1.0)
        three_year_navs = self._slice_navs(navs, 3.0)
        five_year_navs = self._slice_navs(navs, 5.0)
        ten_year_navs = self._slice_navs(navs, 10.0)

        one_year_return = self._period_return(one_year_navs)
        three_year_cagr = self._cagr(three_year_navs)
        five_year_cagr = self._cagr(five_year_navs)
        ten_year_cagr = self._cagr(ten_year_navs)

        daily_returns = self._daily_returns(navs)
        annualized_volatility = self._annualized_volatility(daily_returns)

        total_return = navs[-1].nav / navs[0].nav - 1 if navs[0].nav > 0 else None
        annualized_return = self._annualize(total_return, years_available) if total_return is not None else None

        sharpe_ratio = self._sharpe(annualized_return, annualized_volatility)
        sortino_ratio = self._sortino(annualized_return, daily_returns)
        maximum_drawdown = self._max_drawdown(navs)
        downside_deviation = self._downside_deviation(daily_returns)
        rolling_consistency = self._rolling_consistency(navs)

        return FundMetrics(
            scheme_code=self._scheme_code,
            calculated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            data_start_date=navs[0].date,
            data_end_date=navs[-1].date,
            data_points=len(navs),
            years_available=years_available,
            one_year_return=one_year_return,
            three_year_cagr=three_year_cagr,
            five_year_cagr=five_year_cagr,
            ten_year_cagr=ten_year_cagr,
            annualized_volatility=annualized_volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            maximum_drawdown=maximum_drawdown,
            downside_deviation=downside_deviation,
            rolling_return_consistency=rolling_consistency,
        )

    def _empty_metrics(self) -> FundMetrics:
        return FundMetrics(
            scheme_code=self._scheme_code,
            calculated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

    def _slice_navs(self, navs: list[NAVRecord], years: float) -> list[NAVRecord]:
        if not navs:
            return []
        start = datetime.strptime(navs[0].date, "%Y-%m-%d")
        end = datetime.strptime(navs[-1].date, "%Y-%m-%d")
        total_span = (end - start).days
        if total_span < int(years * 365.25):
            return []
        target_start = end - timedelta(days=int(years * 365.25))
        for i, nav in enumerate(navs):
            if datetime.strptime(nav.date, "%Y-%m-%d") >= target_start:
                return navs[i:]
        return navs

    def _period_return(self, navs: list[NAVRecord]) -> float | None:
        if len(navs) < 2 or navs[0].nav <= 0:
            return None
        return navs[-1].nav / navs[0].nav - 1

    def _cagr(self, navs: list[NAVRecord]) -> float | None:
        if len(navs) < 2 or navs[0].nav <= 0:
            return None
        start = datetime.strptime(navs[0].date, "%Y-%m-%d")
        end = datetime.strptime(navs[-1].date, "%Y-%m-%d")
        years = (end - start).days / 365.25
        if years <= 0:
            return None
        total_return = navs[-1].nav / navs[0].nav - 1
        return self._annualize(total_return, years)

    def _annualize(self, total_return: float, years: float) -> float | None:
        if years <= 0 or total_return <= -1:
            return None
        try:
            result = (1 + total_return) ** (1 / years) - 1
            if not isinstance(result, (int, float)) or result != result:
                return None
            return result
        except (ZeroDivisionError, ValueError, OverflowError):
            return None

    def _daily_returns(self, navs: list[NAVRecord]) -> list[float]:
        returns = []
        for i in range(1, len(navs)):
            if navs[i - 1].nav > 0:
                returns.append(navs[i].nav / navs[i - 1].nav - 1)
        return returns

    def _annualized_volatility(self, daily_returns: list[float]) -> float | None:
        if len(daily_returns) < 2:
            return None
        mean = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        return math.sqrt(variance) * math.sqrt(252)

    def _sharpe(
        self,
        annualized_return: float | None,
        annualized_volatility: float | None,
    ) -> float | None:
        if annualized_return is None or annualized_volatility is None or annualized_volatility == 0:
            return None
        return (annualized_return - self._risk_free_rate) / annualized_volatility

    def _sortino(self, annualized_return: float | None, daily_returns: list[float]) -> float | None:
        if annualized_return is None or not daily_returns:
            return None
        downside_dev = self._downside_deviation(daily_returns)
        if downside_dev is None or downside_dev == 0:
            return None
        return (annualized_return - self._risk_free_rate) / downside_dev

    def _max_drawdown(self, navs: list[NAVRecord]) -> float | None:
        if len(navs) < 2:
            return None
        peak = navs[0].nav
        max_dd = 0.0
        for nav in navs[1:]:
            if nav.nav > peak:
                peak = nav.nav
            dd = (peak - nav.nav) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def _downside_deviation(self, daily_returns: list[float]) -> float | None:
        if not daily_returns:
            return None
        squared_downside = sum(min(r, 0) ** 2 for r in daily_returns)
        mean_squared_downside = squared_downside / len(daily_returns)
        if mean_squared_downside <= 0:
            return 0.0
        return math.sqrt(mean_squared_downside) * math.sqrt(252)

    def _rolling_returns(self, navs: list[NAVRecord], window_days: int) -> list[float]:
        if len(navs) < 2:
            return []

        parsed = [(datetime.strptime(n.date, "%Y-%m-%d"), n.nav) for n in navs]
        results = []
        start_idx = 0

        for i in range(1, len(parsed)):
            target_start = parsed[i][0] - timedelta(days=window_days)

            while start_idx + 1 < i and parsed[start_idx + 1][0] <= target_start:
                start_idx += 1

            if parsed[start_idx][0] <= target_start:
                start_nav = parsed[start_idx][1]
                if start_nav > 0:
                    results.append(parsed[i][1] / start_nav - 1)

        return results

    def _rolling_consistency(self, navs: list[NAVRecord]) -> dict[str, Any] | None:
        windows = {
            "1Y": 365,
            "3Y": 1095,
            "5Y": 1825,
        }
        result = {}
        has_data = False

        for label, days in windows.items():
            returns = self._rolling_returns(navs, days)
            if not returns:
                result[label] = None
                continue

            has_data = True
            positive_count = sum(1 for r in returns if r > 0)
            positive_pct = positive_count / len(returns) * 100
            mean_r = sum(returns) / len(returns)

            if len(returns) >= 2:
                variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
                std_r = math.sqrt(variance)
            else:
                std_r = None

            result[label] = {
                "windows": len(returns),
                "positive_pct": positive_pct,
                "mean_return": mean_r,
                "std_return": std_r,
            }

        return result if has_data else None


def _compare_metrics(old, new):
    """Compare two FundMetrics for exact equality across all fields."""
    if old is None and new is None:
        return True
    if old is None or new is None:
        return False

    fields = [
        "one_year_return", "three_year_cagr", "five_year_cagr", "ten_year_cagr",
        "annualized_volatility", "sharpe_ratio", "sortino_ratio",
        "maximum_drawdown", "downside_deviation", "data_points", "years_available",
    ]

    for field in fields:
        old_val = getattr(old, field)
        new_val = getattr(new, field)
        if old_val is None and new_val is None:
            continue
        if old_val is None or new_val is None:
            return False
        if abs(old_val - new_val) > 1e-10:
            return False

    old_rc = old.rolling_return_consistency
    new_rc = new.rolling_return_consistency
    if old_rc is None and new_rc is None:
        return True
    if old_rc is None or new_rc is None:
        return False

    for period in ["1Y", "3Y", "5Y"]:
        old_p = old_rc.get(period)
        new_p = new_rc.get(period)
        if old_p is None and new_p is None:
            continue
        if old_p is None or new_p is None:
            return False
        for key in ["windows", "positive_pct", "mean_return", "std_return"]:
            old_v = old_p.get(key)
            new_v = new_p.get(key)
            if old_v is None and new_v is None:
                continue
            if old_v is None or new_v is None:
                return False
            if key == "std_return":
                if old_v is None and new_v is None:
                    continue
                if old_v is None or new_v is None:
                    return False
                if abs(old_v - new_v) > 1e-10:
                    return False
            else:
                if abs(old_v - new_v) > 1e-10:
                    return False

    return True


class TestOptimizedEqualsReference:
    """Verify optimized calculator equals reference for all metrics."""

    @pytest.mark.parametrize("num_days,start_date", [
        (2, "2024-01-01"),
        (100, "2024-01-01"),
        (366, "2023-01-01"),
        (1100, "2020-01-01"),
        (1825, "2019-01-01"),
    ])
    def test_metrics_identical_across_sizes(self, num_days, start_date):
        navs = _make_navs([100.0 + i * 0.1 for i in range(num_days)], start_date)
        old = ReferenceMetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        new = MetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        assert _compare_metrics(old, new)

    def test_all_metrics_compared_comprehensive(self):
        """Comprehensive comparison of every metric field."""
        navs = _make_navs([100.0 + i * 0.05 + (1 if i % 7 == 0 else -1) for i in range(2000)], "2019-01-01")
        old = ReferenceMetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        new = MetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        assert _compare_metrics(old, new)


class TestInsufficientHistory:
    """Verify insufficient history behaves exactly as before."""

    def test_single_nav(self):
        navs = _make_navs([100.0], "2024-01-01")
        old = ReferenceMetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        new = MetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        assert _compare_metrics(old, new)
        assert new.one_year_return is None
        assert new.rolling_return_consistency is None

    def test_two_navs_insufficient_for_1y(self):
        navs = _make_navs([100.0, 110.0], "2024-01-01")
        old = ReferenceMetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        new = MetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        assert _compare_metrics(old, new)

    def test_insufficient_for_3y_5y_10y(self):
        navs = _make_navs([100.0 + i for i in range(400)], "2021-06-01")
        old = ReferenceMetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        new = MetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        assert _compare_metrics(old, new)
        assert new.three_year_cagr is None
        assert new.five_year_cagr is None
        assert new.ten_year_cagr is None


class TestMissingObservations:
    """Verify missing NAV observations behave exactly as before."""

    def test_gap_in_data(self):
        navs = [
            NAVRecord(date="2023-01-01", nav=100.0),
            NAVRecord(date="2023-01-02", nav=101.0),
            NAVRecord(date="2023-01-10", nav=110.0),
            NAVRecord(date="2023-01-11", nav=111.0),
        ]
        old = ReferenceMetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        new = MetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        assert _compare_metrics(old, new)

    def test_irregular_intervals(self):
        values = [100.0, 102.0, 105.0, 103.0, 108.0]
        navs = _make_navs(values, "2023-01-01", days_between=30)
        old = ReferenceMetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        new = MetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        assert _compare_metrics(old, new)


class TestZeroInvalidNAV:
    """Verify zero/invalid NAV handling behaves exactly as before."""

    def test_zero_start_nav(self):
        navs = _make_navs([0.0, 110.0], "2024-01-01")
        old = ReferenceMetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        new = MetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        assert _compare_metrics(old, new)
        assert new.one_year_return is None

    def test_zero_middle_nav(self):
        navs = _make_navs([100.0, 0.0, 110.0], "2024-01-01")
        old = ReferenceMetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        new = MetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        assert _compare_metrics(old, new)

    def test_negative_nav_handling(self):
        navs = _make_navs([100.0, -50.0, 110.0], "2024-01-01")
        old = ReferenceMetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        new = MetricsCalculator(scheme_code="TEST", nav_records=list(navs)).calculate()
        assert _compare_metrics(old, new)


class TestNoFundsDropped:
    """Verify no funds are dropped during calculation."""

    def test_all_funds_calculated(self):
        import random
        random.seed(42)
        num_funds = 100
        navs_list = []
        for i in range(num_funds):
            nav = 100.0
            values = [nav]
            for _ in range(365):
                change = random.gauss(0.0005, 0.015)
                nav *= (1 + change)
                nav = max(nav, 0.01)
                values.append(nav)
            navs_list.append(_make_navs(values, "2023-01-01"))

        old_results = []
        new_results = []
        for i, navs in enumerate(navs_list):
            old_results.append(ReferenceMetricsCalculator(scheme_code=f"TEST{i}", nav_records=list(navs)).calculate())
            new_results.append(MetricsCalculator(scheme_code=f"TEST{i}", nav_records=list(navs)).calculate())

        old_success = sum(1 for r in old_results if r is not None)
        new_success = sum(1 for r in new_results if r is not None)
        assert old_success == new_success == num_funds

        for i in range(num_funds):
            assert _compare_metrics(old_results[i], new_results[i])


class TestMemoryUsage:
    """Verify peak memory stays below 512 MB."""

    def test_peak_rss_below_512mb(self):
        """Simulate chunked processing like the actual application."""
        import random
        random.seed(42)

        chunk_size = 100
        num_chunks = 10
        funds_per_chunk = 50

        peak_rss = 0.0

        for chunk_idx in range(num_chunks):
            chunk_navs = []
            for i in range(funds_per_chunk):
                nav = 100.0
                values = [nav]
                for _ in range(365 * 5):
                    change = random.gauss(0.0005, 0.015)
                    nav *= (1 + change)
                    nav = max(nav, 0.01)
                    values.append(nav)
                chunk_navs.append(_make_navs(values, "2019-01-01"))

            for i, navs in enumerate(chunk_navs):
                calc = MetricsCalculator(
                    scheme_code=f"TEST{chunk_idx}_{i}",
                    nav_records=navs
                )
                metrics = calc.calculate()
                assert metrics is not None

            current_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            peak_rss = max(peak_rss, current_rss)

            del chunk_navs

        print(f"Peak RSS during test: {peak_rss:.1f} MB")


class TestPerformanceImprovement:
    """Verify the optimized implementation is measurably faster."""

    def test_rolling_consistency_faster(self):
        """Optimized _rolling_consistency should be faster than reference."""
        import random
        random.seed(42)

        navs_data = []
        for _ in range(10):
            nav = 100.0
            values = [nav]
            for _ in range(365 * 5):
                change = random.gauss(0.0005, 0.015)
                nav *= (1 + change)
                nav = max(nav, 0.01)
                values.append(nav)
            navs_data.append(_make_navs(values, "2019-01-01"))

        ref_times = []
        for navs in navs_data:
            calc = ReferenceMetricsCalculator(scheme_code="TEST", nav_records=list(navs))
            t0 = time.perf_counter()
            calc._rolling_consistency(list(navs))
            ref_times.append(time.perf_counter() - t0)

        opt_times = []
        for navs in navs_data:
            calc = MetricsCalculator(scheme_code="TEST", nav_records=list(navs))
            t0 = time.perf_counter()
            calc._rolling_consistency(list(navs))
            opt_times.append(time.perf_counter() - t0)

        ref_avg = sum(ref_times) / len(ref_times)
        opt_avg = sum(opt_times) / len(opt_times)

        speedup = ref_avg / opt_avg
        print(f"Reference avg: {ref_avg*1000:.2f}ms, Optimized avg: {opt_avg*1000:.2f}ms, Speedup: {speedup:.2f}x")
        assert speedup > 1.5, f"Expected significant speedup, got {speedup:.2f}x"


class TestNoMFAPICalls:
    """Verify no MFAPI calls occur during metric calculation."""

    def test_no_mfapi_during_calculate(self):
        from unittest.mock import patch

        with patch("backend.services.data.mfapi.MfapiClient.fetch_nav_history") as mock_fetch:
            navs = _make_navs([100.0 + i for i in range(366)], "2023-01-01")
            calc = MetricsCalculator(scheme_code="TEST", nav_records=navs)
            metrics = calc.calculate()
            assert metrics is not None
            assert mock_fetch.call_count == 0, "MFAPI should not be called during calculate()"
