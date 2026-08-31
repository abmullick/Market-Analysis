import asyncio
import time
from datetime import datetime, timedelta

import pytest

from backend.services.mutual_funds.cache import MetricsCache
from backend.services.mutual_funds.lookback import (
    CRITERIA_LOOKBACK_YEARS,
    get_date_range_for_lookback,
    get_required_lookback_years,
)


class TestLookbackCalculation:
    def test_single_criterion_1y(self):
        assert get_required_lookback_years(["1Y_return"]) == 1

    def test_single_criterion_10y(self):
        assert get_required_lookback_years(["10Y_cagr"]) == 10

    def test_multiple_criteria_max_lookback(self):
        assert get_required_lookback_years(["1Y_return", "3Y_cagr", "5Y_cagr"]) == 5

    def test_all_period_criteria(self):
        assert get_required_lookback_years(["1Y_return", "10Y_cagr"]) == 10

    def test_mixed_criteria(self):
        assert get_required_lookback_years(["1Y_return", "3Y_cagr", "5Y_cagr", "10Y_cagr"]) == 10

    def test_unknown_criterion_defaults_to_1(self):
        assert get_required_lookback_years(["unknown_criterion"]) == 1

    def test_date_range_calculation(self):
        end_date = datetime(2026, 8, 30)
        start_date, end = get_date_range_for_lookback(5, end_date)
        expected_start = end_date - timedelta(days=int(5 * 365.25) + 90)
        assert abs((start_date - expected_start).days) <= 1

    def test_date_range_with_buffer(self):
        end_date = datetime(2026, 8, 30)
        start_date, end = get_date_range_for_lookback(1, end_date)
        days = (end_date - start_date).days
        assert days >= 365 + 90


class TestMetricsCache:
    def test_cache_miss(self):
        cache = MetricsCache(ttl_seconds=3600)
        result = cache.get("12345", 5)
        assert result is None

    def test_cache_hit(self):
        cache = MetricsCache(ttl_seconds=3600)
        metrics = {"scheme_code": "12345", "one_year_return": 0.1}
        cache.put("12345", 5, metrics)
        result = cache.get("12345", 5)
        assert result == metrics

    def test_cache_different_lookback(self):
        cache = MetricsCache(ttl_seconds=3600)
        metrics_5y = {"scheme_code": "12345", "five_year_cagr": 0.15}
        metrics_10y = {"scheme_code": "12345", "ten_year_cagr": 0.12}
        cache.put("12345", 5, metrics_5y)
        cache.put("12345", 10, metrics_10y)
        assert cache.get("12345", 5) == metrics_5y
        assert cache.get("12345", 10) == metrics_10y

    def test_cache_different_schemes(self):
        cache = MetricsCache(ttl_seconds=3600)
        metrics_a = {"scheme_code": "11111"}
        metrics_b = {"scheme_code": "22222"}
        cache.put("11111", 5, metrics_a)
        cache.put("22222", 5, metrics_b)
        assert cache.get("11111", 5) == metrics_a
        assert cache.get("22222", 5) == metrics_b

    def test_cache_expiry(self):
        cache = MetricsCache(ttl_seconds=0)
        metrics = {"scheme_code": "12345"}
        cache.put("12345", 5, metrics)
        time.sleep(0.01)
        result = cache.get("12345", 5)
        assert result is None

    def test_cache_invalidate_all(self):
        cache = MetricsCache(ttl_seconds=3600)
        cache.put("12345", 5, {"scheme_code": "12345"})
        cache.put("67890", 5, {"scheme_code": "67890"})
        cache.invalidate()
        assert cache.get("12345", 5) is None
        assert cache.get("67890", 5) is None

    def test_cache_invalidate_single_scheme(self):
        cache = MetricsCache(ttl_seconds=3600)
        cache.put("12345", 5, {"scheme_code": "12345"})
        cache.put("12345", 10, {"scheme_code": "12345"})
        cache.put("67890", 5, {"scheme_code": "67890"})
        cache.invalidate("12345")
        assert cache.get("12345", 5) is None
        assert cache.get("12345", 10) is None
        assert cache.get("67890", 5) is not None

    def test_cache_stats(self):
        cache = MetricsCache(ttl_seconds=3600)
        cache.put("12345", 5, {"scheme_code": "12345"})
        cache.get("12345", 5)
        cache.get("99999", 5)
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
