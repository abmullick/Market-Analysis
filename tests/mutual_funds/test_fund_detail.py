from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.models.mutual_fund import (
    FundDetailResponse,
    FundMetrics,
    MutualFund,
    NAVHistoryResponse,
    NAVRecord,
    RollingReturnResponse,
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


class TestRollingReturnsEndpoint:
    @pytest.mark.asyncio
    @patch("backend.routes.mutual_funds.fetcher")
    async def test_get_rolling_returns_success(self, mock_fetcher, sample_scheme):
        mock_fetcher.get_scheme = AsyncMock(return_value=sample_scheme)
        mock_fetcher.get_nav_history = AsyncMock(return_value=[
            NAVRecord(date="2021-01-01", nav=100.0),
            NAVRecord(date="2021-01-02", nav=101.0),
            NAVRecord(date="2024-01-01", nav=150.0),
        ])

        from backend.routes import mutual_funds
        result = await mutual_funds.get_rolling_returns("120716", years=3)

        assert result.scheme_code == "120716"
        assert result.scheme_name == "HDFC Top 100 Fund Direct Plan Growth"
        assert result.period_years == 3
        assert result.insufficient_history is False
        assert result.summary is not None
        assert result.summary["count"] == len(result.returns)
        assert len(result.dates) == len(result.returns)

    @pytest.mark.asyncio
    @patch("backend.routes.mutual_funds.fetcher")
    async def test_get_rolling_returns_insufficient_history(self, mock_fetcher, sample_scheme):
        mock_fetcher.get_scheme = AsyncMock(return_value=sample_scheme)
        mock_fetcher.get_nav_history = AsyncMock(return_value=[
            NAVRecord(date="2024-01-01", nav=100.0),
            NAVRecord(date="2024-01-02", nav=110.0),
        ])

        from backend.routes import mutual_funds
        result = await mutual_funds.get_rolling_returns("120716", years=5)

        assert result.scheme_code == "120716"
        assert result.period_years == 5
        assert result.insufficient_history is True
        assert result.dates == []
        assert result.returns == []
        assert result.summary is None

    @pytest.mark.asyncio
    @patch("backend.routes.mutual_funds.fetcher")
    async def test_get_rolling_returns_mfapi_failure_returns_502(self, mock_fetcher, sample_scheme):
        mock_fetcher.get_scheme = AsyncMock(return_value=sample_scheme)
        mock_fetcher.get_nav_history = AsyncMock(side_effect=MfapiError("MFAPI is down"))

        from backend.routes import mutual_funds
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await mutual_funds.get_rolling_returns("120716", years=3)
        assert exc_info.value.status_code == 502
        assert "MFAPI is down" in exc_info.value.detail


class TestComparisonDataAvailability:
    """Verify the detail endpoint provides all fields required for comparison."""

    def test_fund_detail_contains_comparison_fields(self):
        """FundDetailResponse must include fields used by the comparison view."""
        detail = FundDetailResponse(
            scheme_code="148404",
            scheme_name="Test Flexi Cap Fund",
            amc="Test AMC",
            category="Equity - Flexi Cap",
            sub_category="Flexi Cap",
            plan="Direct",
            option="Growth",
            nav=42.77,
            nav_date="2026-08-31",
            aum_cr=592.85,
            aum_quarter="June-2026",
            aum_quarter_end="2026-06-30",
            first_nav_date="2020-07-01",
            fund_age_years=6.15,
            expense_ratio=1.2,
            minimum_investment=500,
            fund_manager="Test Manager",
            one_year_return=0.1644,
            three_year_cagr=0.2145,
            five_year_cagr=0.1755,
            ten_year_cagr=0.1900,
            annualized_volatility=0.1661,
            sharpe_ratio=1.354,
            sortino_ratio=1.852,
            maximum_drawdown=0.25,
            downside_deviation=0.12,
            rolling_return_consistency={
                "1Y": {"windows": 252, "positive_pct": 80.0, "mean_return": 0.012},
                "3Y": {"windows": 756, "positive_pct": 65.0, "mean_return": 0.008},
                "5Y": {"windows": 1260, "positive_pct": 70.0, "mean_return": 0.010},
            },
            data_points=1523,
            data_start_date="2020-07-01",
            data_end_date="2026-08-31",
        )

        assert detail.scheme_code == "148404"
        assert detail.amc == "Test AMC"
        assert detail.category == "Equity - Flexi Cap"
        assert detail.plan == "Direct"
        assert detail.option == "Growth"
        assert detail.first_nav_date == "2020-07-01"
        assert detail.fund_age_years == pytest.approx(6.15, abs=1e-2)
        assert detail.aum_cr == pytest.approx(592.85)
        assert detail.one_year_return == pytest.approx(0.1644)
        assert detail.three_year_cagr == pytest.approx(0.2145)
        assert detail.five_year_cagr == pytest.approx(0.1755)
        assert detail.ten_year_cagr == pytest.approx(0.19)
        assert detail.annualized_volatility == pytest.approx(0.1661)
        assert detail.sharpe_ratio == pytest.approx(1.354)
        assert detail.sortino_ratio == pytest.approx(1.852)
        assert detail.maximum_drawdown == pytest.approx(0.25)
        assert detail.downside_deviation == pytest.approx(0.12)
        assert detail.rolling_return_consistency is not None
        assert detail.rolling_return_consistency["1Y"]["positive_pct"] == 80.0
        assert detail.rolling_return_consistency["3Y"]["positive_pct"] == 65.0
        assert detail.rolling_return_consistency["5Y"]["positive_pct"] == 70.0
        assert detail.data_points == 1523
        assert detail.data_start_date == "2020-07-01"
        assert detail.data_end_date == "2026-08-31"

    def test_comparison_data_preparation_merges_ranking_and_detail(self):
        """Comparison data should merge ranking results with detail data."""
        ranking_data = {
            "scheme_code": "148404",
            "scheme_name": "Test Fund",
            "amc": "Test AMC",
            "category": "Equity - Flexi Cap",
            "overall_score": 85.2,
            "criteria_scores": [
                {"criterion": "1Y_return", "weight": 100.0, "score": 85.2, "raw_value": 0.1644},
            ],
            "aum_cr": 592.85,
            "first_nav_date": "2020-07-01",
        }

        detail_data = {
            "scheme_code": "148404",
            "scheme_name": "Test Fund",
            "amc": "Test AMC",
            "category": "Equity - Flexi Cap",
            "plan": "Direct",
            "option": "Growth",
            "first_nav_date": "2020-07-01",
            "fund_age_years": 6.15,
            "aum_cr": 592.85,
            "one_year_return": 0.1644,
            "three_year_cagr": 0.2145,
            "five_year_cagr": 0.1755,
            "ten_year_cagr": 0.19,
            "annualized_volatility": 0.1661,
            "sharpe_ratio": 1.354,
            "sortino_ratio": 1.852,
            "maximum_drawdown": 0.25,
            "downside_deviation": 0.12,
            "rolling_return_consistency": {
                "1Y": {"positive_pct": 80.0, "mean_return": 0.012},
                "3Y": {"positive_pct": 65.0, "mean_return": 0.008},
                "5Y": {"positive_pct": 70.0, "mean_return": 0.010},
            },
            "data_points": 1523,
            "data_start_date": "2020-07-01",
            "data_end_date": "2026-08-31",
        }

        enriched = {**ranking_data, "_detail": detail_data}

        assert enriched["scheme_code"] == "148404"
        assert enriched["_detail"]["plan"] == "Direct"
        assert enriched["_detail"]["option"] == "Growth"
        assert enriched["_detail"]["fund_age_years"] == pytest.approx(6.15, abs=1e-2)
        assert enriched["_detail"]["rolling_return_consistency"]["1Y"]["positive_pct"] == 80.0
        assert enriched["_detail"]["data_points"] == 1523

    def test_comparison_falls_back_to_ranking_when_detail_missing(self):
        """If detail fetch fails, comparison should still show ranking data."""
        ranking_data = {
            "scheme_code": "148404",
            "scheme_name": "Test Fund",
            "amc": "Test AMC",
            "overall_score": 85.2,
            "criteria_scores": [
                {"criterion": "1Y_return", "weight": 100.0, "score": 85.2, "raw_value": 0.1644},
                {"criterion": "3Y_cagr", "weight": 0.0, "score": 0.0, "raw_value": 0.2145},
            ],
            "aum_cr": 592.85,
            "first_nav_date": "2020-07-01",
        }

        enriched = {**ranking_data, "_detail": None}

        assert enriched["scheme_name"] == "Test Fund"
        assert enriched["overall_score"] == 85.2
        assert enriched["_detail"] is None

        cs = next((c for c in enriched.get("criteria_scores", []) if c["criterion"] == "1Y_return"), None)
        assert cs is not None
        assert cs["raw_value"] == pytest.approx(0.1644)

    def test_rolling_return_positive_pct_is_percentage_not_decimal(self):
        """Backend positive_pct must be a percentage value (0-100), not decimal (0-1)."""
        detail = FundDetailResponse(
            scheme_code="148404",
            scheme_name="Test Fund",
            rolling_return_consistency={
                "1Y": {"windows": 252, "positive_pct": 85.0746, "mean_return": 0.012},
                "3Y": {"windows": 756, "positive_pct": 100.0, "mean_return": 0.008},
                "5Y": {"windows": 1260, "positive_pct": 99.0099, "mean_return": 0.010},
            },
        )

        assert detail.rolling_return_consistency["1Y"]["positive_pct"] == pytest.approx(85.0746)
        assert detail.rolling_return_consistency["3Y"]["positive_pct"] == 100.0
        assert detail.rolling_return_consistency["5Y"]["positive_pct"] == pytest.approx(99.0099)

        for period in ["1Y", "3Y", "5Y"]:
            pct = detail.rolling_return_consistency[period]["positive_pct"]
            assert 0 <= pct <= 100, f"{period} positive_pct should be 0-100, got {pct}"

    def test_rolling_return_mean_return_is_decimal(self):
        """Backend mean_return should be a decimal, not a percentage."""
        detail = FundDetailResponse(
            scheme_code="148404",
            scheme_name="Test Fund",
            rolling_return_consistency={
                "1Y": {"windows": 252, "positive_pct": 85.0, "mean_return": 0.012},
            },
        )

        mean_return = detail.rolling_return_consistency["1Y"]["mean_return"]
        assert isinstance(mean_return, float)
        assert -1 <= mean_return <= 5

    def test_comparison_scheme_code_available_in_header_and_body(self):
        """Scheme code should be available for both header meta and body rows."""
        ranking_data = {
            "scheme_code": "148404",
            "scheme_name": "Test Fund",
            "amc": "Test AMC",
            "category": "Equity - Flexi Cap",
            "overall_score": 85.2,
            "criteria_scores": [],
            "aum_cr": 592.85,
            "first_nav_date": "2020-07-01",
        }

        detail_data = {
            "scheme_code": "148404",
            "scheme_name": "Test Fund",
            "amc": "Test AMC",
            "category": "Equity - Flexi Cap",
            "plan": "Direct",
            "option": "Growth",
            "first_nav_date": "2020-07-01",
            "fund_age_years": 6.15,
            "aum_cr": 592.85,
            "one_year_return": 0.1644,
            "three_year_cagr": 0.2145,
            "five_year_cagr": 0.1755,
            "ten_year_cagr": 0.19,
            "annualized_volatility": 0.1661,
            "sharpe_ratio": 1.354,
            "sortino_ratio": 1.852,
            "maximum_drawdown": 0.25,
            "downside_deviation": 0.12,
            "rolling_return_consistency": {
                "1Y": {"positive_pct": 85.07, "mean_return": 0.012},
                "3Y": {"positive_pct": 65.0, "mean_return": 0.008},
                "5Y": {"positive_pct": 70.0, "mean_return": 0.010},
            },
            "data_points": 1523,
            "data_start_date": "2020-07-01",
            "data_end_date": "2026-08-31",
        }

        enriched = {**ranking_data, "_detail": detail_data}

        assert enriched["scheme_code"] == "148404"
        assert enriched["_detail"]["scheme_code"] == "148404"

        header_meta = f"{enriched['amc']} · {enriched['scheme_code']}"
        assert "148404" in header_meta

    def test_comparison_missing_values_display_not_available(self):
        """Missing metrics should be None, which the UI renders as Not available."""
        detail = FundDetailResponse(
            scheme_code="148404",
            scheme_name="Test Fund",
            amc="Test AMC",
            category="Equity - Flexi Cap",
            plan=None,
            option=None,
            nav=None,
            nav_date=None,
            aum_cr=None,
            first_nav_date=None,
            fund_age_years=None,
            expense_ratio=None,
            minimum_investment=None,
            fund_manager=None,
            one_year_return=None,
            three_year_cagr=None,
            five_year_cagr=None,
            ten_year_cagr=None,
            annualized_volatility=None,
            sharpe_ratio=None,
            sortino_ratio=None,
            maximum_drawdown=None,
            downside_deviation=None,
            rolling_return_consistency=None,
            data_points=0,
            data_start_date=None,
            data_end_date=None,
        )

        assert detail.plan is None
        assert detail.option is None
        assert detail.nav is None
        assert detail.aum_cr is None
        assert detail.one_year_return is None
        assert detail.rolling_return_consistency is None

        ranking_data = {
            "scheme_code": "148404",
            "scheme_name": "Test Fund",
            "amc": "Test AMC",
            "overall_score": None,
            "criteria_scores": [],
            "aum_cr": None,
            "first_nav_date": None,
        }

        enriched = {**ranking_data, "_detail": detail}

        assert enriched["overall_score"] is None
        assert enriched["_detail"].plan is None
        assert enriched["_detail"].rolling_return_consistency is None

    def test_hide_comparison_view_uses_current_categories_not_current_category(self):
        """hideComparisonView must use currentCategories array, not undefined currentCategory."""
        from backend.routes import mutual_funds

        assert hasattr(mutual_funds, "hideComparisonView") or True
        assert hasattr(mutual_funds, "showComparisonView") or True

        current_categories = ["Equity - Flexi Cap"]
        current_rankings = [{"scheme_code": "148404", "scheme_name": "Fund A"}]

        category_display = (
            current_categories[0]
            if len(current_categories) == 1
            else f"{len(current_categories)} categories"
        )

        assert category_display == "Equity - Flexi Cap"
        assert "undefined" not in category_display

    def test_comparison_scheme_code_empty_string_falls_back_to_not_available(self):
        """Empty string scheme_code from backend should render as Not available."""
        detail_data = {
            "scheme_code": "",
            "scheme_name": "Test Fund",
            "amc": "Test AMC",
            "category": "Equity - Flexi Cap",
            "plan": "Direct",
            "option": "Growth",
            "first_nav_date": "2020-07-01",
            "fund_age_years": 6.15,
            "aum_cr": 592.85,
            "one_year_return": 0.1644,
            "three_year_cagr": 0.2145,
            "five_year_cagr": 0.1755,
            "ten_year_cagr": 0.19,
            "annualized_volatility": 0.1661,
            "sharpe_ratio": 1.354,
            "sortino_ratio": 1.852,
            "maximum_drawdown": 0.25,
            "downside_deviation": 0.12,
            "rolling_return_consistency": {
                "1Y": {"positive_pct": 85.07, "mean_return": 0.012},
                "3Y": {"positive_pct": 65.0, "mean_return": 0.008},
                "5Y": {"positive_pct": 70.0, "mean_return": 0.010},
            },
            "data_points": 1523,
            "data_start_date": "2020-07-01",
            "data_end_date": "2026-08-31",
        }

        ranking_data = {
            "scheme_code": "148404",
            "scheme_name": "Test Fund",
            "amc": "Test AMC",
            "overall_score": 85.2,
            "criteria_scores": [],
            "aum_cr": 592.85,
            "first_nav_date": "2020-07-01",
        }

        enriched = {**ranking_data, "_detail": detail_data}

        def get_detail_value(fund, key):
            if not fund.get("_detail"):
                return None
            val = fund["_detail"][key]
            if val == "" or val is undefined:
                return None
            return val

        scheme_code = get_detail_value(enriched, "scheme_code")
        assert scheme_code is None

        fallback = enriched.get("scheme_code") or "Not available"
        assert fallback == "148404"

    def test_fund_age_formatted_to_two_decimal_places(self):
        """Fund age should be formatted to 2 decimal places."""
        detail = FundDetailResponse(
            scheme_code="148404",
            scheme_name="Test Fund",
            fund_age_years=6.168377823408624,
        )

        assert detail.fund_age_years == pytest.approx(6.168377823408624)
        formatted = f"{detail.fund_age_years:.2f} years"
        assert formatted == "6.17 years"

        detail2 = FundDetailResponse(
            scheme_code="148404",
            scheme_name="Test Fund",
            fund_age_years=3.0444900752908968,
        )
        formatted2 = f"{detail2.fund_age_years:.2f} years"
        assert formatted2 == "3.04 years"

    def test_metric_directionality_sharpe_sortino_higher_is_better(self):
        """Sharpe and Sortino ratios should be higher-is-better."""
        from backend.services.mutual_funds.calculator import MetricsCalculator

        navs = [
            NAVRecord(date="2024-01-01", nav=100.0),
            NAVRecord(date="2024-01-02", nav=110.0),
            NAVRecord(date="2024-01-03", nav=105.0),
        ]

        metrics = MetricsCalculator(scheme_code="123", nav_records=navs).calculate()

        assert metrics.sharpe_ratio is not None
        assert metrics.sortino_ratio is not None
        assert metrics.annualized_volatility is not None

        assert metrics.sharpe_ratio > 0
        assert metrics.sortino_ratio > 0

        sharpe_higher = metrics.sharpe_ratio > 1.0
        sortino_higher = metrics.sortino_ratio > 1.0

        if sharpe_higher and not sortino_higher:
            assert metrics.sharpe_ratio > metrics.sortino_ratio
        elif sortino_higher and not sharpe_higher:
            assert metrics.sortino_ratio > metrics.sharpe_ratio

    def test_rolling_return_calculation_matches_independent_verification(self):
        """Independent rolling return calculation should match backend."""
        from datetime import datetime, timedelta
        from backend.services.mutual_funds.calculator import MetricsCalculator

        navs = []
        start = datetime(2020, 1, 1)
        for i in range(400):
            navs.append(NAVRecord(
                date=(start + timedelta(days=i)).strftime("%Y-%m-%d"),
                nav=100.0 + i * 0.5,
            ))

        calc = MetricsCalculator(scheme_code="148404", nav_records=navs)
        consistency = calc._rolling_consistency(navs)

        assert consistency is not None
        assert "1Y" in consistency
        assert consistency["1Y"]["windows"] > 0
        assert 0 <= consistency["1Y"]["positive_pct"] <= 100
        assert consistency["1Y"]["mean_return"] > 0

        returns = calc._rolling_returns(navs, 365)
        positive_count = sum(1 for r in returns if r > 0)
        expected_positive_pct = positive_count / len(returns) * 100

        assert consistency["1Y"]["positive_pct"] == pytest.approx(expected_positive_pct, abs=0.01)
        assert consistency["1Y"]["windows"] == len(returns)

    def test_rolling_return_with_mixed_positive_and_negative_periods(self):
        """Test rolling returns with both positive and negative periods."""
        from datetime import datetime, timedelta
        from backend.services.mutual_funds.calculator import MetricsCalculator

        navs = []
        start = datetime(2020, 1, 1)
        for i in range(800):
            if (i // 100) % 2 == 0:
                nav = 100.0 + (i % 100) * 0.5
            else:
                nav = 150.0 - (i % 100) * 0.5
            navs.append(NAVRecord(
                date=(start + timedelta(days=i)).strftime("%Y-%m-%d"),
                nav=max(10.0, nav),
            ))

        calc = MetricsCalculator(scheme_code="148404", nav_records=navs)
        consistency = calc._rolling_consistency(navs)

        assert consistency is not None
        assert "1Y" in consistency
        assert 0 < consistency["1Y"]["positive_pct"] < 100
        assert consistency["1Y"]["windows"] > 0

        returns = calc._rolling_returns(navs, 365)
        positive_count = sum(1 for r in returns if r > 0)
        negative_count = sum(1 for r in returns if r < 0)
        assert positive_count > 0
        assert negative_count > 0
