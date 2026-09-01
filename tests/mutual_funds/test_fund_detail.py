from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.models.mutual_fund import (
    FundDetailResponse,
    FundMetrics,
    MutualFund,
    NAVHistoryResponse,
    NAVRecord,
)
from backend.services.mutual_funds.cache import MetricsCache
from backend.services.data.mfapi import MfapiError


@pytest.fixture
def sample_scheme():
    return MutualFund(
        scheme_code="120716",
        scheme_name="HDFC Top 100 Fund Direct Plan Growth",
        amc="HDFC Mutual Fund",
        category="Equity Scheme - Large Cap Fund",
        nav=850.1234,
        nav_date="2024-12-31",
        expense_ratio=1.2,
        minimum_investment=5000,
        fund_manager="Prashant Jain",
    )


@pytest.fixture
def sample_metrics():
    return {
        "scheme_code": "120716",
        "scheme_name": "HDFC Top 100 Fund Direct Plan Growth",
        "calculated_at": "2024-12-31T00:00:00Z",
        "data_start_date": "2014-01-01",
        "data_end_date": "2024-12-31",
        "data_points": 2500,
        "years_available": 10.5,
        "one_year_return": 0.15,
        "three_year_cagr": 0.12,
        "five_year_cagr": 0.14,
        "ten_year_cagr": 0.13,
        "annualized_volatility": 0.18,
        "sharpe_ratio": 1.2,
        "sortino_ratio": 1.5,
        "maximum_drawdown": 0.25,
        "downside_deviation": 0.12,
        "rolling_return_consistency": {
            "1Y": {"windows": 100, "positive_pct": 75.0, "mean_return": 0.02, "std_return": 0.05},
            "3Y": {"windows": 50, "positive_pct": 80.0, "mean_return": 0.08, "std_return": 0.10},
        },
    }


@pytest.fixture
def sample_metadata():
    return {
        "aaum_cr_quarterly_avg": 25000.5,
        "aaum_quarter": "Q3 FY24",
        "aaum_quarter_end": "2024-09-30",
        "first_date": "2014-01-01",
    }


class TestFundDetailResponse:
    def test_create_minimal(self):
        detail = FundDetailResponse(scheme_code="120716", scheme_name="Test Fund")
        assert detail.scheme_code == "120716"
        assert detail.scheme_name == "Test Fund"
        assert detail.nav is None
        assert detail.one_year_return is None

    def test_create_full(self):
        detail = FundDetailResponse(
            scheme_code="120716",
            scheme_name="Test Fund",
            amc="Test AMC",
            category="Equity",
            nav=100.0,
            nav_date="2024-12-31",
            aum_cr=5000.0,
            first_nav_date="2020-01-01",
            fund_age_years=4.5,
            one_year_return=0.15,
            three_year_cagr=0.12,
        )
        assert detail.amc == "Test AMC"
        assert detail.aum_cr == 5000.0
        assert detail.fund_age_years == 4.5
        assert detail.one_year_return == 0.15


class TestNAVHistoryResponse:
    def test_create(self):
        response = NAVHistoryResponse(
            scheme_code="120716",
            scheme_name="Test Fund",
            dates=["2024-01-01", "2024-01-02"],
            navs=[100.0, 101.0],
        )
        assert len(response.dates) == 2
        assert len(response.navs) == 2


class TestExtractPlan:
    def test_direct(self):
        from backend.routes.mutual_funds import _extract_plan
        assert _extract_plan("HDFC Fund Direct Plan Growth") == "Direct"

    def test_regular(self):
        from backend.routes.mutual_funds import _extract_plan
        assert _extract_plan("HDFC Fund Regular Plan Growth") == "Regular"

    def test_none(self):
        from backend.routes.mutual_funds import _extract_plan
        assert _extract_plan("HDFC Fund Growth") is None

    def test_empty(self):
        from backend.routes.mutual_funds import _extract_plan
        assert _extract_plan("") is None

    def test_none_input(self):
        from backend.routes.mutual_funds import _extract_plan
        assert _extract_plan(None) is None


class TestExtractOption:
    def test_growth(self):
        from backend.routes.mutual_funds import _extract_option
        assert _extract_option("HDFC Fund Direct Plan Growth") == "Growth"

    def test_idcw(self):
        from backend.routes.mutual_funds import _extract_option
        assert _extract_option("HDFC Fund Direct Plan IDCW") == "IDCW"

    def test_dividend(self):
        from backend.routes.mutual_funds import _extract_option
        assert _extract_option("HDFC Fund Regular Plan Dividend") == "IDCW"

    def test_none(self):
        from backend.routes.mutual_funds import _extract_option
        assert _extract_option("HDFC Fund Direct Plan") is None

    def test_empty(self):
        from backend.routes.mutual_funds import _extract_option
        assert _extract_option("") is None


class TestFundDetailEndpoint:
    @pytest.mark.asyncio
    @patch("backend.routes.mutual_funds.get_tigzig_metadata")
    @patch("backend.routes.mutual_funds.fetcher")
    async def test_get_fund_detail_success(self, mock_fetcher, mock_metadata_class, sample_scheme, sample_metrics, sample_metadata):
        mock_fetcher.get_scheme = AsyncMock(return_value=sample_scheme)
        mock_fetcher.get_nav_history = AsyncMock(return_value=[])

        mock_metadata_service = MagicMock()
        mock_metadata_service.get_metadata = AsyncMock(return_value={})
        mock_metadata_service.lookup = MagicMock(return_value=sample_metadata)
        mock_metadata_class.return_value = mock_metadata_service

        with patch("backend.routes.mutual_funds.metrics_cache") as mock_cache:
            mock_cache.get.return_value = sample_metrics

            from backend.routes.mutual_funds import get_fund_detail
            result = await get_fund_detail("120716")

            assert result.scheme_code == "120716"
            assert result.scheme_name == "HDFC Top 100 Fund Direct Plan Growth"
            assert result.amc == "HDFC Mutual Fund"
            assert result.nav == 850.1234
            assert result.aum_cr == 25000.5
            assert result.first_nav_date == "2014-01-01"
            assert result.one_year_return == 0.15
            assert result.plan == "Direct"
            assert result.option == "Growth"

    @pytest.mark.asyncio
    @patch("backend.routes.mutual_funds.get_tigzig_metadata")
    @patch("backend.routes.mutual_funds.fetcher")
    async def test_get_fund_detail_no_metadata(self, mock_fetcher, mock_metadata_class, sample_scheme):
        mock_fetcher.get_scheme = AsyncMock(return_value=sample_scheme)
        mock_fetcher.get_nav_history = AsyncMock(return_value=[
            NAVRecord(date="2020-01-01", nav=100.0),
            NAVRecord(date="2024-12-31", nav=200.0),
        ])

        mock_metadata_service = MagicMock()
        mock_metadata_service.get_metadata = AsyncMock(return_value={})
        mock_metadata_service.lookup = MagicMock(return_value=None)
        mock_metadata_class.return_value = mock_metadata_service

        with patch("backend.routes.mutual_funds.metrics_cache") as mock_cache, \
             patch("backend.routes.mutual_funds.MetricsCalculator") as mock_calc:
            mock_cache.get.return_value = None

            mock_metrics = FundMetrics(
                scheme_code="120716",
                data_points=100,
                data_start_date="2020-01-01",
                data_end_date="2024-12-31",
            )
            mock_calc.return_value.calculate.return_value = mock_metrics

            from backend.routes.mutual_funds import get_fund_detail
            result = await get_fund_detail("120716")

            assert result.scheme_code == "120716"
            assert result.aum_cr is None
            assert result.first_nav_date is None


class TestNAVHistoryEndpoint:
    @pytest.mark.asyncio
    @patch("backend.routes.mutual_funds.fetcher")
    async def test_get_nav_history(self, mock_fetcher, sample_scheme):
        mock_fetcher.get_scheme = AsyncMock(return_value=sample_scheme)
        mock_fetcher.get_nav_history = AsyncMock(return_value=[
            NAVRecord(date="2024-01-01", nav=100.0),
            NAVRecord(date="2024-01-02", nav=101.0),
            NAVRecord(date="2024-01-03", nav=102.0),
        ])

        from backend.routes import mutual_funds
        result = await mutual_funds.get_nav_history_chart("120716", years=1)

        assert result.scheme_code == "120716"
        assert result.scheme_name == "HDFC Top 100 Fund Direct Plan Growth"
        assert len(result.dates) == 3
        assert len(result.navs) == 3
        assert result.navs[0] == 100.0

    @pytest.mark.asyncio
    @patch("backend.routes.mutual_funds.fetcher")
    async def test_get_nav_history_mfapi_failure_returns_502(self, mock_fetcher, sample_scheme):
        mock_fetcher.get_scheme = AsyncMock(return_value=sample_scheme)
        mock_fetcher.get_nav_history = AsyncMock(side_effect=MfapiError("MFAPI is down"))

        from backend.routes import mutual_funds
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await mutual_funds.get_nav_history_chart("120716", years=10)
        assert exc_info.value.status_code == 502
        assert "MFAPI is down" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("backend.routes.mutual_funds.fetcher")
    async def test_get_nav_history_empty_list_succeeds(self, mock_fetcher, sample_scheme):
        mock_fetcher.get_scheme = AsyncMock(return_value=sample_scheme)
        mock_fetcher.get_nav_history = AsyncMock(return_value=[])

        from backend.routes import mutual_funds
        result = await mutual_funds.get_nav_history_chart("120716", years=10)

        assert result.scheme_code == "120716"
        assert result.dates == []
        assert result.navs == []


class TestMetricsCacheReuse:
    def test_cache_hit_returns_cached_metrics(self):
        cache = MetricsCache(ttl_seconds=3600)
        cached_metrics = {"one_year_return": 0.15, "sharpe_ratio": 1.2}
        cache.put("120716", 10, cached_metrics)

        result = cache.get("120716", 10)
        assert result == cached_metrics

    def test_cache_miss_returns_none(self):
        cache = MetricsCache(ttl_seconds=3600)
        result = cache.get("999999", 10)
        assert result is None

    def test_cache_hit_avoids_recalculation(self):
        cache = MetricsCache(ttl_seconds=3600)
        cached_metrics = {"one_year_return": 0.15, "sharpe_ratio": 1.2}
        cache.put("120716", 10, cached_metrics)

        assert cache.get("120716", 10) is not None
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 0
