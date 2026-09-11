"""Tests for the mutual-fund portfolio analysis engine.

Uses deterministic synthetic NAV series so expected portfolio results can be
verified exactly. Methodology constants mirror the existing fund-level
MetricsCalculator conventions (365.25-day years, sqrt(252) annualization,
4% risk-free rate, MAR = 0).
"""

import math
import statistics
from datetime import date, timedelta

import pytest

from backend.models.mutual_fund import NAVRecord
from backend.services.portfolio.mf_analysis import (
    PortfolioAnalysisError,
    calculate_portfolio_analysis,
    validate_allocations,
)

DAYS = 40  # common observation count for success cases (> MIN_COMMON_OBSERVATIONS)


def make_navs(values, start=(2020, 1, 1)):
    d0 = date(*start)
    return [
        NAVRecord(date=(d0 + timedelta(days=i)).isoformat(), nav=float(v))
        for i, v in enumerate(values)
    ]


def growing_navs(n, daily=0.01, start_nav=100.0, start=(2020, 1, 1)):
    v = start_nav
    values = []
    for _ in range(n):
        values.append(v)
        v *= 1 + daily
    return make_navs(values, start)


def constant_navs(n, nav=100.0, start=(2020, 1, 1)):
    return make_navs([nav] * n, start)


def run(funds):
    return calculate_portfolio_analysis(
        [{"scheme_code": c, "allocation": a, "navs": navs} for c, a, navs in funds]
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestAllocationValidation:
    def test_valid_two_fund_100(self):
        validate_allocations(
            [{"scheme_code": "A", "allocation": 50}, {"scheme_code": "B", "allocation": 50}]
        )

    def test_valid_three_fund_two_dp(self):
        validate_allocations(
            [
                {"scheme_code": "A", "allocation": 33.33},
                {"scheme_code": "B", "allocation": 33.33},
                {"scheme_code": "C", "allocation": 33.34},
            ]
        )

    def test_too_few_funds(self):
        with pytest.raises(PortfolioAnalysisError) as e:
            validate_allocations([{"scheme_code": "A", "allocation": 100}])
        assert e.value.code == "invalid_fund_count"

    def test_too_many_funds(self):
        funds = [{"scheme_code": str(i), "allocation": 100 / 11} for i in range(11)]
        with pytest.raises(PortfolioAnalysisError) as e:
            validate_allocations(funds)
        assert e.value.code == "invalid_fund_count"

    def test_weights_below_100(self):
        with pytest.raises(PortfolioAnalysisError) as e:
            validate_allocations(
                [{"scheme_code": "A", "allocation": 40}, {"scheme_code": "B", "allocation": 40}]
            )
        assert e.value.code == "allocation_total"

    def test_weights_above_100(self):
        with pytest.raises(PortfolioAnalysisError) as e:
            validate_allocations(
                [{"scheme_code": "A", "allocation": 60}, {"scheme_code": "B", "allocation": 60}]
            )
        assert e.value.code == "allocation_total"

    def test_negative_allocation(self):
        with pytest.raises(PortfolioAnalysisError) as e:
            validate_allocations(
                [{"scheme_code": "A", "allocation": 110}, {"scheme_code": "B", "allocation": -10}]
            )
        assert e.value.code == "invalid_allocation"

    def test_non_numeric_allocation(self):
        with pytest.raises(PortfolioAnalysisError) as e:
            validate_allocations(
                [{"scheme_code": "A", "allocation": "50"}, {"scheme_code": "B", "allocation": 50}]
            )
        assert e.value.code == "invalid_allocation"

    def test_duplicate_fund(self):
        with pytest.raises(PortfolioAnalysisError) as e:
            validate_allocations(
                [{"scheme_code": "A", "allocation": 50}, {"scheme_code": "A", "allocation": 50}]
            )
        assert e.value.code == "duplicate_fund"


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------


class TestPortfolioCalculation:
    def test_two_fund_equal_weights_growth_series(self):
        # A grows 1%/day; B flat. 50/50 rebalanced => portfolio grows 0.5%/day.
        result = run(
            [
                ("A", 50, growing_navs(DAYS, daily=0.01)),
                ("B", 50, constant_navs(DAYS)),
            ]
        )
        assert result.metrics.observations == DAYS
        assert result.series[0].value == 100.0
        expected = 100.0 * (1.005 ** (DAYS - 1))
        assert result.series[-1].value == pytest.approx(expected, rel=1e-12)
        assert result.metrics.total_return == pytest.approx(1.005 ** (DAYS - 1) - 1)

    def test_three_fund_weighted_returns(self):
        # A +1%/day, B flat, C -0.5%/day, weights 40/30/30 => 0.25%/day.
        result = run(
            [
                ("A", 40, growing_navs(DAYS, daily=0.01)),
                ("B", 30, constant_navs(DAYS)),
                ("C", 30, growing_navs(DAYS, daily=-0.005)),
            ]
        )
        expected = 100.0 * (1.0025 ** (DAYS - 1))
        assert result.series[-1].value == pytest.approx(expected, rel=1e-12)

    def test_portfolio_cagr_36525_convention(self):
        # A at 100% (B zero-weight, allowed alongside >=2 entries).
        result = run([("A", 100, growing_navs(DAYS)), ("B", 0, constant_navs(2))])
        start = date(2020, 1, 1)
        end = start + timedelta(days=DAYS - 1)
        years = (end - start).days / 365.25
        expected = (1.01 ** (DAYS - 1)) ** (1 / years) - 1
        assert result.metrics.cagr == pytest.approx(expected, rel=1e-12)
        assert result.metrics.years == pytest.approx(years)

    def test_portfolio_volatility_sharpe_sortino(self):
        # Alternating +1%/-1% daily returns, single fund at 100%.
        values = [100.0]
        for i in range(1, DAYS):
            values.append(values[-1] * (1.01 if i % 2 else 0.99))
        navs = make_navs(values)
        result = run([("A", 100, navs), ("B", 0, constant_navs(2))])

        rets = [values[i] / values[i - 1] - 1 for i in range(1, DAYS)]
        expected_vol = statistics.stdev(rets) * math.sqrt(252)
        years = (DAYS - 1) / 365.25
        expected_cagr = (values[-1] / values[0]) ** (1 / years) - 1
        downside = math.sqrt(sum(min(r, 0) ** 2 for r in rets) / len(rets)) * math.sqrt(252)

        assert result.metrics.annualized_volatility == pytest.approx(expected_vol, rel=1e-12)
        assert result.metrics.cagr == pytest.approx(expected_cagr, rel=1e-12)
        assert result.metrics.sharpe_ratio == pytest.approx((expected_cagr - 0.04) / expected_vol, rel=1e-9)
        assert result.metrics.downside_deviation == pytest.approx(downside, rel=1e-12)
        assert result.metrics.sortino_ratio == pytest.approx((expected_cagr - 0.04) / downside, rel=1e-9)

    def test_zero_volatility_metrics_none(self):
        # Constant NAV => 0 volatility => Sharpe/Sortino undefined (None).
        result = run([("A", 100, constant_navs(DAYS)), ("B", 0, constant_navs(2))])
        assert result.metrics.annualized_volatility == 0.0
        assert result.metrics.sharpe_ratio is None
        assert result.metrics.sortino_ratio is None
        assert result.metrics.downside_deviation == 0.0
        assert result.metrics.cagr == pytest.approx(0.0)

    def test_maximum_drawdown(self, monkeypatch):
        from backend.services.portfolio import mf_analysis

        monkeypatch.setattr(mf_analysis, "MIN_COMMON_OBSERVATIONS", 2)
        result = run(
            [
                ("A", 100, make_navs([100, 110, 99, 105, 120, 60, 90, 130])),
                ("B", 0, constant_navs(2)),
            ]
        )
        assert result.metrics.maximum_drawdown == pytest.approx((120 - 60) / 120)


# ---------------------------------------------------------------------------
# Date alignment & data sufficiency
# ---------------------------------------------------------------------------


class TestDateAlignment:
    def test_different_inception_dates_intersection(self):
        # Fund B starts 10 days later: portfolio series must start at B's
        # first date (intersection), not pad/interpolate A's earlier dates.
        result = run(
            [
                ("A", 50, growing_navs(DAYS + 10)),
                ("B", 50, growing_navs(DAYS, start=(2020, 1, 11))),
            ]
        )
        assert result.series[0].date == "2020-01-11"
        assert result.metrics.observations == DAYS
        assert result.metrics.start_date == "2020-01-11"

    def test_missing_nav_dates_not_interpolated(self):
        # Fund A is missing 5 dates in the middle; those dates are dropped
        # from the portfolio entirely (no forward-fill).
        a_navs = growing_navs(DAYS)
        a_navs = a_navs[:20] + a_navs[25:]  # remove 5 middle dates
        result = run(
            [
                ("A", 50, a_navs),
                ("B", 50, constant_navs(DAYS)),
            ]
        )
        assert result.metrics.observations == DAYS - 5
        # Dates removed from fund A (indices 20..24) must not appear in series.
        dropped = {n.date for n in growing_navs(DAYS)[20:25]}
        series_dates = {p.date for p in result.series}
        assert dropped.isdisjoint(series_dates)

    def test_zero_weight_fund_does_not_constrain_history(self):
        # Zero-weight fund has only a few observations; it must not shrink
        # the common history of the contributing funds.
        result = run(
            [
                ("A", 60, growing_navs(DAYS)),
                ("B", 40, constant_navs(DAYS)),
                ("Z", 0, constant_navs(3)),
            ]
        )
        assert result.metrics.observations == DAYS
        assert [w for w in result.warnings if "Z" in w]
        z = next(f for f in result.funds if f.scheme_code == "Z")
        assert z.contributes is False

    def test_insufficient_common_history(self):
        with pytest.raises(PortfolioAnalysisError) as e:
            run(
                [
                    ("A", 50, growing_navs(20)),
                    ("B", 50, growing_navs(20, start=(2021, 1, 1))),
                ]
            )
        assert e.value.code == "insufficient_common_history"

    def test_fund_with_no_history(self):
        with pytest.raises(PortfolioAnalysisError) as e:
            run(
                [
                    ("A", 50, growing_navs(DAYS)),
                    ("B", 50, []),
                ]
            )
        assert e.value.code == "insufficient_fund_history"
        assert "B" in e.value.message

    def test_fund_results_reported_for_all(self):
        result = run(
            [
                ("A", 60, growing_navs(DAYS)),
                ("B", 40, growing_navs(DAYS, start=(2020, 1, 5))),
            ]
        )
        by_code = {f.scheme_code: f for f in result.funds}
        assert by_code["A"].observations == DAYS
        assert by_code["B"].observations == DAYS  # B's own history length
        assert by_code["A"].effective_weight == pytest.approx(0.6)
        assert by_code["B"].effective_weight == pytest.approx(0.4)
        assert result.metrics.observations == DAYS - 4  # intersection

    def test_duplicate_dates_deduped(self):
        # Duplicate observations for the same date (e.g. combined pages) must not
        # create duplicate common dates or double-counted returns.
        navs = growing_navs(DAYS)
        duplicated = navs[:10] + navs  # first 10 dates appear twice
        result = run([("A", 50, duplicated), ("B", 50, navs)])
        assert result.metrics.observations == DAYS
        dates = [p.date for p in result.series]
        assert len(dates) == len(set(dates))

    def test_common_end_is_earliest_latest_date(self):
        # Fund B stops publishing earlier; the portfolio must end at B's last date.
        navs_a = growing_navs(DAYS + 50)  # longer history
        navs_b = growing_navs(DAYS)       # ends earlier
        result = run([("A", 50, navs_a), ("B", 50, navs_b)])
        assert result.metrics.end_date == navs_b[-1].date
        assert result.metrics.observations == DAYS

    def test_metrics_use_full_common_period_over_1000(self):
        # >1000 common observations with different inceptions and latest dates:
        # the full common period must be used, not truncated to ~1000 records.
        n_a = 1500
        navs_a = growing_navs(n_a, start=(2015, 1, 1))
        # Fund B starts 100 observations later and ends 70 observations earlier.
        navs_b = growing_navs(n_a - 100 - 70, start=(2015, 4, 11))  # +100 days
        result = run([("A", 50, navs_a), ("B", 50, navs_b)])
        assert result.metrics.observations == n_a - 100 - 70  # intersection size
        assert result.metrics.start_date == navs_b[0].date
        assert result.metrics.end_date == navs_b[-1].date
        assert len(result.series) == n_a - 100 - 70


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


class TestEndpoint:
    @pytest.fixture
    def client(self, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.routes import portfolio as portfolio_route

        class FakeDataset:
            is_available = True

            async def ensure_dataset(self):  # must never be called when available
                raise AssertionError("ensure_dataset called although dataset available")

        monkeypatch.setattr(portfolio_route, "get_tigzig_dataset", lambda: FakeDataset())

        class FakeFetcher:
            async def get_nav_history(self, scheme_code, lookback_years=None):
                if scheme_code == "MISSING":
                    return []
                return growing_navs(DAYS)

        monkeypatch.setattr(portfolio_route, "_get_fetcher", lambda: FakeFetcher())
        app = FastAPI()
        app.include_router(portfolio_route.router, prefix="/api/portfolio")
        return TestClient(app)

    def test_endpoint_requests_complete_history(self, client, monkeypatch):
        from backend.routes import portfolio as portfolio_route

        lookbacks = []

        async def fake_fetch(code, lookback_years=None):
            lookbacks.append(lookback_years)
            return growing_navs(DAYS)

        class F:
            get_nav_history = staticmethod(fake_fetch)

        monkeypatch.setattr(portfolio_route, "_get_fetcher", lambda: F())
        resp = client.post(
            "/api/portfolio/mutual-fund-analysis",
            json={"funds": [{"scheme_code": "A", "allocation": 50},
                            {"scheme_code": "B", "allocation": 50}]},
        )
        assert resp.status_code == 200
        # lookback_years=None → complete available history, no window clipping
        assert lookbacks == [None, None]

    def test_endpoint_full_history_over_1000_records(self, monkeypatch):
        # A history far larger than any legacy 1000-record cap must be used whole.
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.routes import portfolio as portfolio_route

        n = 1200

        class FakeDataset:
            is_available = True

            async def ensure_dataset(self):
                raise AssertionError("ensure_dataset called although dataset available")

        monkeypatch.setattr(portfolio_route, "get_tigzig_dataset", lambda: FakeDataset())

        class BigFetcher:
            async def get_nav_history(self, scheme_code, lookback_years=None):
                return growing_navs(n)

        monkeypatch.setattr(portfolio_route, "_get_fetcher", lambda: BigFetcher())
        app = FastAPI()
        app.include_router(portfolio_route.router, prefix="/api/portfolio")
        resp = TestClient(app).post(
            "/api/portfolio/mutual-fund-analysis",
            json={"funds": [{"scheme_code": "A", "allocation": 50},
                            {"scheme_code": "B", "allocation": 50}]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["metrics"]["observations"] == n
        assert len(body["series"]) == n

    def test_endpoint_ensures_tigzig_when_unavailable(self, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.routes import portfolio as portfolio_route

        ensured = []

        class FakeDataset:
            is_available = False

            async def ensure_dataset(self):
                ensured.append(True)
                return True

        monkeypatch.setattr(portfolio_route, "get_tigzig_dataset", lambda: FakeDataset())

        class FakeFetcher:
            async def get_nav_history(self, scheme_code, lookback_years=None):
                return growing_navs(DAYS)

        monkeypatch.setattr(portfolio_route, "_get_fetcher", lambda: FakeFetcher())
        app = FastAPI()
        app.include_router(portfolio_route.router, prefix="/api/portfolio")
        resp = TestClient(app).post(
            "/api/portfolio/mutual-fund-analysis",
            json={"funds": [{"scheme_code": "A", "allocation": 50},
                            {"scheme_code": "B", "allocation": 50}]},
        )
        assert resp.status_code == 200
        assert ensured == [True]

    def test_endpoint_ensure_failure_still_analyzes_via_fallback(self, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.routes import portfolio as portfolio_route

        class FakeDataset:
            is_available = False

            async def ensure_dataset(self):
                raise RuntimeError("download failed")

        monkeypatch.setattr(portfolio_route, "get_tigzig_dataset", lambda: FakeDataset())

        class FakeFetcher:
            async def get_nav_history(self, scheme_code, lookback_years=None):
                return growing_navs(DAYS)

        monkeypatch.setattr(portfolio_route, "_get_fetcher", lambda: FakeFetcher())
        app = FastAPI()
        app.include_router(portfolio_route.router, prefix="/api/portfolio")
        resp = TestClient(app).post(
            "/api/portfolio/mutual-fund-analysis",
            json={"funds": [{"scheme_code": "A", "allocation": 50},
                            {"scheme_code": "B", "allocation": 50}]},
        )
        # Graceful degradation: analysis still succeeds via the fallback source.
        assert resp.status_code == 200

    def test_endpoint_valid_portfolio(self, client):
        resp = client.post(
            "/api/portfolio/mutual-fund-analysis",
            json={"funds": [{"scheme_code": "A", "allocation": 50},
                            {"scheme_code": "B", "allocation": 50}]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["metrics"]["observations"] == DAYS
        assert len(body["series"]) == DAYS
        assert body["series"][0]["value"] == 100.0

    def test_endpoint_fetches_unique_scheme_once(self, client, monkeypatch):
        from backend.routes import portfolio as portfolio_route

        calls = []

        async def fake_fetch(code, lookback_years=None):
            calls.append(code)
            return growing_navs(DAYS)

        class F:
            get_nav_history = staticmethod(fake_fetch)

        monkeypatch.setattr(portfolio_route, "_get_fetcher", lambda: F())
        resp = client.post(
            "/api/portfolio/mutual-fund-analysis",
            json={"funds": [{"scheme_code": "A", "allocation": 50},
                            {"scheme_code": "A", "allocation": 50}]},
        )
        assert resp.status_code == 400  # duplicate rejected before fetch
        assert calls == []

    def test_endpoint_validation_error_400(self, client):
        resp = client.post(
            "/api/portfolio/mutual-fund-analysis",
            json={"funds": [{"scheme_code": "A", "allocation": 40},
                            {"scheme_code": "B", "allocation": 40}]},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "allocation_total"

    def test_endpoint_missing_nav_error_400(self, client):
        resp = client.post(
            "/api/portfolio/mutual-fund-analysis",
            json={"funds": [{"scheme_code": "A", "allocation": 50},
                            {"scheme_code": "MISSING", "allocation": 50}]},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "insufficient_fund_history"


# ---------------------------------------------------------------------------
# Health Score (Phase 3A)
# ---------------------------------------------------------------------------


class TestHealthScore:
    """Deterministic tests for the additive Health Score component."""

    def test_score_none_when_history_under_one_year(self):
        from backend.services.portfolio.health_score import calculate_health_score
        from backend.models.portfolio import (
            PortfolioMetricsData, PortfolioFundResult, PortfolioAnalysisResult,
        )

        metrics = PortfolioMetricsData(
            cagr=0.50, annualized_volatility=0.20, sharpe_ratio=2.0,
            sortino_ratio=3.0, downside_deviation=0.10,
            maximum_drawdown=-0.10, observations=100, years=0.5,
            start_date="2020-01-01", end_date="2020-07-01",
        )
        result = PortfolioAnalysisResult(
            funds=[PortfolioFundResult(
                scheme_code="A", allocation=100, effective_weight=1.0,
                observations=100, contributes=True,
            )],
            metrics=metrics, series=[], warnings=[],
        )
        hs = calculate_health_score(result)
        assert hs.score is None
        assert hs.score_withheld is True
        assert hs.confidence.tier == "D"
        assert "less than 1 year" in (hs.withholding_reason or "")

    def test_cagr_subscore_piecewise(self):
        from backend.services.portfolio.health_score import _cagr_subscore
        assert _cagr_subscore(-0.05) == 0.0
        assert _cagr_subscore(0.0) == 0.0
        assert _cagr_subscore(0.06) == 12.5
        assert _cagr_subscore(0.12) == 25.0
        assert _cagr_subscore(0.16) == 32.5
        assert _cagr_subscore(0.20) == 40.0
        assert _cagr_subscore(0.50) == 40.0

    def test_return_quality_blends_r1_r2(self):
        from backend.services.portfolio.health_score import calculate_health_score
        from backend.models.portfolio import (
            PortfolioMetricsData, PortfolioFundResult, PortfolioAnalysisResult,
        )
        metrics = PortfolioMetricsData(
            cagr=0.16, annualized_volatility=0.15, sharpe_ratio=1.0,
            sortino_ratio=1.5, downside_deviation=0.08,
            maximum_drawdown=-0.20, observations=2000, years=5.0,
        )
        result = PortfolioAnalysisResult(
            funds=[
                PortfolioFundResult(scheme_code="A", allocation=60, effective_weight=0.6, observations=2000, contributes=True),
                PortfolioFundResult(scheme_code="B", allocation=40, effective_weight=0.4, observations=2000, contributes=True),
            ],
            metrics=metrics, series=[], warnings=[],
            rolling_consistency={
                "1Y": {"positive_pct": 70, "std_return": 0.05},
                "3Y": {"positive_pct": 80, "std_return": 0.04},
                "5Y": {"positive_pct": 90, "std_return": 0.03},
            },
        )
        hs = calculate_health_score(result)
        assert hs.score is not None
        assert 0 <= hs.score <= 100
        assert hs.components.return_quality is not None

    def test_rolling_only_1y_available_renormalizes(self):
        from backend.services.portfolio.health_score import calculate_health_score
        from backend.models.portfolio import (
            PortfolioMetricsData, PortfolioFundResult, PortfolioAnalysisResult,
        )
        metrics = PortfolioMetricsData(cagr=0.10, years=1.5, observations=500)
        result = PortfolioAnalysisResult(
            funds=[PortfolioFundResult(scheme_code="A", allocation=100, effective_weight=1.0, observations=500, contributes=True)],
            metrics=metrics, series=[], warnings=[],
            rolling_consistency={"1Y": {"positive_pct": 60, "std_return": 0.05}},
        )
        hs = calculate_health_score(result)
        assert hs.score is not None
        assert hs.score_withheld is False

    def test_downside_risk_and_drawdown(self):
        from backend.services.portfolio.health_score import _downside_risk_subscore
        assert _downside_risk_subscore(0.0, 0.05, 0.10) == 75.0
        assert _downside_risk_subscore(-0.50, 0.10, 0.10) == 0.0

    def test_risk_adjusted_omitted_when_sortino_missing_renormalizes(self):
        from backend.services.portfolio.health_score import calculate_health_score
        from backend.models.portfolio import (
            PortfolioMetricsData, PortfolioFundResult, PortfolioAnalysisResult,
        )
        metrics = PortfolioMetricsData(
            cagr=0.10, annualized_volatility=0.15, sortino_ratio=None,
            downside_deviation=0.10, maximum_drawdown=-0.20, observations=2000, years=5.0,
        )
        result = PortfolioAnalysisResult(
            funds=[PortfolioFundResult(scheme_code="A", allocation=100, effective_weight=1.0, observations=2000, contributes=True)],
            metrics=metrics, series=[], warnings=[],
        )
        hs = calculate_health_score(result)
        assert "risk_adjusted_return" not in hs.available_components
        assert hs.components.risk_adjusted_return is None
        assert abs(sum(hs.component_weights.values()) - 1.0) < 1e-9

    def test_concentration_hhi(self):
        from backend.services.portfolio.health_score import _concentration_subscore
        assert _concentration_subscore([0.5, 0.5]) == 100.0
        assert _concentration_subscore([1.0]) == 0.0
        assert _concentration_subscore([0.6, 0.4]) == pytest.approx(96.0, rel=0.001)

    def test_fund_mix_category_and_amc(self):
        from backend.services.portfolio.health_score import _fund_mix_subscore
        score = _fund_mix_subscore(["Equity", "Debt", "Equity"], ["HDFC", "HDFC", "ICICI"])
        assert 0 <= score <= 100

    def test_single_fund_portfolio_flags(self):
        from backend.services.portfolio.health_score import calculate_health_score
        from backend.models.portfolio import (
            PortfolioMetricsData, PortfolioFundResult, PortfolioAnalysisResult,
        )
        metrics = PortfolioMetricsData(cagr=0.10, years=5.0, observations=2000)
        result = PortfolioAnalysisResult(
            funds=[PortfolioFundResult(scheme_code="A", allocation=100, effective_weight=1.0, observations=2000, contributes=True)],
            metrics=metrics, series=[], warnings=[],
        )
        hs = calculate_health_score(result)
        assert hs.single_fund_portfolio is True
        assert hs.components.concentration == 0.0
        assert hs.components.fund_mix == 0.0

    def test_legacy_scheme_caps_confidence_at_c(self):
        from backend.services.portfolio.health_score import calculate_health_score
        from backend.models.portfolio import (
            PortfolioMetricsData, PortfolioFundResult, PortfolioAnalysisResult,
        )
        metrics = PortfolioMetricsData(cagr=0.15, years=6.0, observations=2000)
        result = PortfolioAnalysisResult(
            funds=[PortfolioFundResult(
                scheme_code="A", allocation=100, effective_weight=1.0,
                observations=2000, contributes=True, is_stale=True,
            )],
            metrics=metrics, series=[], warnings=[],
        )
        hs = calculate_health_score(result)
        assert hs.has_legacy_scheme is True
        assert hs.confidence.tier == "C"
        assert "no longer publishes NAVs" in hs.confidence.label

    def test_history_confidence_tiers(self):
        from backend.services.portfolio.health_score import _history_confidence
        assert _history_confidence(6.0, False)[0] == "A"
        assert _history_confidence(4.0, False)[0] == "B"
        assert _history_confidence(2.0, False)[0] == "C"
        assert _history_confidence(0.5, False)[0] == "D"
        assert _history_confidence(6.0, True)[0] == "C"