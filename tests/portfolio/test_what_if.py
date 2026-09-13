"""Tests for the What-If Allocation feature (temporary historical scenario).

Mirrors the conventions in test_mf_portfolio.py: deterministic synthetic NAV
series, a fake fetcher/dataset for endpoint tests, and the existing
PortfolioAnalysisError code contract. The What-If engine reuses
calculate_portfolio_analysis unchanged — these tests verify the wiring
(validation, comparison, route) rather than re-testing the metrics formulas.
"""

from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models.mutual_fund import NAVRecord
from backend.services.portfolio.mf_analysis import calculate_portfolio_analysis
from backend.services.portfolio.what_if import (
    WhatIfError,
    compare_portfolio_results,
    validate_scenario_allocations,
)

DAYS = 40  # > MIN_COMMON_OBSERVATIONS


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


def noisy_navs(n, daily=0.01, amplitude=0.004, start_nav=100.0, start=(2020, 1, 1)):
    """Growing series with alternating +/- noise so volatility/Sharpe are
    non-null (a perfectly smooth series has zero daily-return variance)."""
    v = start_nav
    values = []
    for i in range(n):
        values.append(v)
        wobble = amplitude if i % 2 == 0 else -amplitude
        v *= 1 + daily + wobble
    return make_navs(values, start)


def run(funds):
    return calculate_portfolio_analysis(
        [{"scheme_code": c, "allocation": a, "navs": navs} for c, a, navs in funds]
    )


# ---------------------------------------------------------------------------
# validate_scenario_allocations — unit tests
# ---------------------------------------------------------------------------


class TestValidateScenarioAllocations:
    def test_valid_100_total(self):
        validate_scenario_allocations(
            ["A", "B"],
            [{"scheme_code": "A", "allocation": 70}, {"scheme_code": "B", "allocation": 30}],
        )

    def test_floating_point_near_100_accepted(self):
        validate_scenario_allocations(
            ["A", "B"],
            [{"scheme_code": "A", "allocation": 70.0}, {"scheme_code": "B", "allocation": 29.999999}],
        )

    def test_below_100_rejected(self):
        with pytest.raises(WhatIfError) as e:
            validate_scenario_allocations(
                ["A", "B"],
                [{"scheme_code": "A", "allocation": 60}, {"scheme_code": "B", "allocation": 35}],
            )
        assert e.value.code == "ALLOC_TOTAL"

    def test_above_100_rejected(self):
        with pytest.raises(WhatIfError) as e:
            validate_scenario_allocations(
                ["A", "B"],
                [{"scheme_code": "A", "allocation": 70}, {"scheme_code": "B", "allocation": 35}],
            )
        assert e.value.code == "ALLOC_TOTAL"

    def test_negative_allocation_rejected(self):
        with pytest.raises(WhatIfError) as e:
            validate_scenario_allocations(
                ["A", "B"],
                [{"scheme_code": "A", "allocation": 110}, {"scheme_code": "B", "allocation": -10}],
            )
        assert e.value.code == "ALLOC_INVALID"

    def test_unknown_fund_rejected(self):
        with pytest.raises(WhatIfError) as e:
            validate_scenario_allocations(
                ["A", "B"],
                [{"scheme_code": "A", "allocation": 50}, {"scheme_code": "C", "allocation": 50}],
            )
        assert e.value.code == "SCENARIO_FUND_NOT_IN_PORTFOLIO"

    def test_missing_fund_rejected(self):
        # Current portfolio has A and B; scenario only reallocates A — a
        # partial reallocation is not a valid What-If scenario.
        with pytest.raises(WhatIfError) as e:
            validate_scenario_allocations(
                ["A", "B"],
                [{"scheme_code": "A", "allocation": 100}],
            )
        assert e.value.code == "SCENARIO_MISSING_FUND"

    def test_duplicate_scenario_fund_rejected(self):
        with pytest.raises(WhatIfError) as e:
            validate_scenario_allocations(
                ["A", "B"],
                [
                    {"scheme_code": "A", "allocation": 50},
                    {"scheme_code": "A", "allocation": 20},
                    {"scheme_code": "B", "allocation": 30},
                ],
            )
        assert e.value.code == "ALLOC_DUPLICATE"


# ---------------------------------------------------------------------------
# compare_portfolio_results — unit tests
# ---------------------------------------------------------------------------


class TestCompareResults:
    def test_current_allocation_as_scenario_matches_exactly(self):
        """Financial-correctness check: submitting the CURRENT weights as the
        What-If scenario must reproduce identical metrics (same funds, same
        NAVs, same methodology) — proves there is no second calculation path.
        """
        navs_a = noisy_navs(DAYS, daily=0.01)
        navs_b = noisy_navs(DAYS, daily=0.004)

        current = run([("A", 50, navs_a), ("B", 50, navs_b)])
        scenario = run([("A", 50, navs_a), ("B", 50, navs_b)])

        comparison = compare_portfolio_results(current, scenario)

        assert comparison["deltas"]["cagr"] == pytest.approx(0.0, abs=1e-9)
        assert comparison["deltas"]["volatility"] == pytest.approx(0.0, abs=1e-9)
        assert comparison["deltas"]["sharpe"] == pytest.approx(0.0, abs=1e-9)
        assert comparison["deltas"]["max_drawdown"] == pytest.approx(0.0, abs=1e-9)
        assert comparison["current"]["metrics"] == comparison["scenario"]["metrics"]

    def test_different_weights_produce_different_metrics(self):
        navs_a = growing_navs(DAYS, daily=0.01)
        navs_b = growing_navs(DAYS, daily=0.001)

        current = run([("A", 50, navs_a), ("B", 50, navs_b)])
        scenario = run([("A", 70, navs_a), ("B", 30, navs_b)])

        comparison = compare_portfolio_results(current, scenario)

        # Tilting toward the higher-growth fund raises CAGR.
        assert comparison["deltas"]["cagr"] > 0
        assert comparison["scenario"]["allocations"] == [
            {"scheme_code": "A", "allocation": 70.0},
            {"scheme_code": "B", "allocation": 30.0},
        ]
        assert comparison["current"]["allocations"] == [
            {"scheme_code": "A", "allocation": 50.0},
            {"scheme_code": "B", "allocation": 50.0},
        ]

    def test_running_scenario_does_not_mutate_current_result(self):
        navs_a = growing_navs(DAYS, daily=0.01)
        navs_b = growing_navs(DAYS, daily=0.001)

        current = run([("A", 50, navs_a), ("B", 50, navs_b)])
        cagr_before = current.metrics.cagr

        scenario = run([("A", 90, navs_a), ("B", 10, navs_b)])
        compare_portfolio_results(current, scenario)

        assert current.metrics.cagr == cagr_before
        assert [f.allocation for f in current.funds] == [50.0, 50.0]

    def test_growth_series_rebased_to_100(self):
        navs_a = growing_navs(DAYS, daily=0.01)
        navs_b = growing_navs(DAYS, daily=0.001)

        current = run([("A", 50, navs_a), ("B", 50, navs_b)])
        scenario = run([("A", 70, navs_a), ("B", 30, navs_b)])
        comparison = compare_portfolio_results(current, scenario)

        series = comparison["growth_series"]
        assert series[0]["current"] == pytest.approx(100.0)
        assert series[0]["scenario"] == pytest.approx(100.0)
        assert len(series) == len(current.series)


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


class TestWhatIfEndpoint:
    @pytest.fixture(autouse=True)
    def _disable_benchmarks(self, monkeypatch):
        # Benchmark comparison is tested separately with stubbed providers;
        # disabled here so tests are deterministic and offline.
        from backend.routes import portfolio as portfolio_route

        monkeypatch.setattr(portfolio_route, "build_benchmark_data", lambda series: None)

    @pytest.fixture
    def client(self, monkeypatch):
        from backend.routes import portfolio as portfolio_route

        class FakeDataset:
            is_available = True

            async def ensure_dataset(self):
                raise AssertionError("ensure_dataset called although dataset available")

        monkeypatch.setattr(portfolio_route, "get_tigzig_dataset", lambda: FakeDataset())

        # A and B grow at different rates so different weightings between them
        # actually change the portfolio result (needed by the
        # different-weights/no-contamination tests below).
        fund_daily_rate = {"A": 0.01, "B": 0.004}

        class FakeFetcher:
            async def get_nav_history(self, scheme_code, lookback_years=None):
                if scheme_code == "MISSING":
                    return []
                return growing_navs(DAYS, daily=fund_daily_rate.get(scheme_code, 0.01))

        monkeypatch.setattr(portfolio_route, "_get_fetcher", lambda: FakeFetcher())
        app = FastAPI()
        app.include_router(portfolio_route.router, prefix="/api/portfolio")
        return TestClient(app)

    def _payload(self, scenario):
        return {
            "funds": [
                {"scheme_code": "A", "allocation": 50},
                {"scheme_code": "B", "allocation": 50},
            ],
            "scenario_allocations": scenario,
        }

    def test_valid_scenario_produces_results(self, client):
        resp = client.post(
            "/api/portfolio/mutual-fund-analysis/what-if",
            json=self._payload(
                [{"scheme_code": "A", "allocation": 70}, {"scheme_code": "B", "allocation": 30}]
            ),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["current"]["allocations"] == [
            {"scheme_code": "A", "allocation": 50.0},
            {"scheme_code": "B", "allocation": 50.0},
        ]
        assert body["scenario"]["allocations"] == [
            {"scheme_code": "A", "allocation": 70.0},
            {"scheme_code": "B", "allocation": 30.0},
        ]
        assert "cagr" in body["deltas"]
        assert len(body["growth_series"]) == DAYS

    def test_scenario_below_100_rejected(self, client):
        resp = client.post(
            "/api/portfolio/mutual-fund-analysis/what-if",
            json=self._payload(
                [{"scheme_code": "A", "allocation": 60}, {"scheme_code": "B", "allocation": 35}]
            ),
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "ALLOC_TOTAL"

    def test_scenario_above_100_rejected(self, client):
        resp = client.post(
            "/api/portfolio/mutual-fund-analysis/what-if",
            json=self._payload(
                [{"scheme_code": "A", "allocation": 80}, {"scheme_code": "B", "allocation": 30}]
            ),
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "ALLOC_TOTAL"

    def test_scenario_negative_allocation_rejected(self, client):
        resp = client.post(
            "/api/portfolio/mutual-fund-analysis/what-if",
            json=self._payload(
                [{"scheme_code": "A", "allocation": 110}, {"scheme_code": "B", "allocation": -10}]
            ),
        )
        # Pydantic's Field(ge=0) on PortfolioWhatIfAllocation rejects negative
        # allocations at the request-parsing layer (422) before reaching the
        # WhatIfError validation path.
        assert resp.status_code == 422

    def test_scenario_unknown_fund_rejected(self, client):
        resp = client.post(
            "/api/portfolio/mutual-fund-analysis/what-if",
            json=self._payload(
                [{"scheme_code": "A", "allocation": 50}, {"scheme_code": "C", "allocation": 50}]
            ),
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "SCENARIO_FUND_NOT_IN_PORTFOLIO"

    def test_scenario_missing_fund_rejected(self, client):
        resp = client.post(
            "/api/portfolio/mutual-fund-analysis/what-if",
            json=self._payload([{"scheme_code": "A", "allocation": 100}]),
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "SCENARIO_MISSING_FUND"

    def test_scenario_floating_point_near_100_accepted(self, client):
        resp = client.post(
            "/api/portfolio/mutual-fund-analysis/what-if",
            json=self._payload(
                [
                    {"scheme_code": "A", "allocation": 70.0},
                    {"scheme_code": "B", "allocation": 29.999999},
                ]
            ),
        )
        assert resp.status_code == 200

    def test_current_weights_as_scenario_match_existing_analysis(self, client):
        """End-to-end version of the financial-correctness check: the
        existing /mutual-fund-analysis endpoint and the What-If endpoint
        (scenario == current weights) must agree on every metric."""
        funds = {
            "funds": [
                {"scheme_code": "A", "allocation": 50},
                {"scheme_code": "B", "allocation": 50},
            ]
        }
        baseline = client.post("/api/portfolio/mutual-fund-analysis", json=funds)
        assert baseline.status_code == 200
        baseline_metrics = baseline.json()["metrics"]

        what_if = client.post(
            "/api/portfolio/mutual-fund-analysis/what-if",
            json=self._payload(
                [{"scheme_code": "A", "allocation": 50}, {"scheme_code": "B", "allocation": 50}]
            ),
        )
        assert what_if.status_code == 200
        body = what_if.json()
        assert body["current"]["metrics"] == baseline_metrics
        assert body["scenario"]["metrics"] == baseline_metrics
        assert body["deltas"]["cagr"] == pytest.approx(0.0, abs=1e-9)
        assert body["deltas"]["max_drawdown"] == pytest.approx(0.0, abs=1e-9)

    def test_insufficient_history_handled(self, client):
        resp = client.post(
            "/api/portfolio/mutual-fund-analysis/what-if",
            json={
                "funds": [
                    {"scheme_code": "A", "allocation": 50},
                    {"scheme_code": "MISSING", "allocation": 50},
                ],
                "scenario_allocations": [
                    {"scheme_code": "A", "allocation": 70},
                    {"scheme_code": "MISSING", "allocation": 30},
                ],
            },
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "insufficient_fund_history"

    def test_running_what_if_does_not_modify_actual_portfolio(self, client):
        """A What-If run must not change the caller's reported current
        allocation on a subsequent normal analysis request."""
        funds = {
            "funds": [
                {"scheme_code": "A", "allocation": 50},
                {"scheme_code": "B", "allocation": 50},
            ]
        }
        client.post(
            "/api/portfolio/mutual-fund-analysis/what-if",
            json=self._payload(
                [{"scheme_code": "A", "allocation": 90}, {"scheme_code": "B", "allocation": 10}]
            ),
        )
        after = client.post("/api/portfolio/mutual-fund-analysis", json=funds)
        assert after.status_code == 200
        alloc_by_code = {f["scheme_code"]: f["allocation"] for f in after.json()["funds"]}
        assert alloc_by_code == {"A": 50.0, "B": 50.0}

    def test_multiple_requests_do_not_contaminate_each_other(self, client):
        resp1 = client.post(
            "/api/portfolio/mutual-fund-analysis/what-if",
            json=self._payload(
                [{"scheme_code": "A", "allocation": 90}, {"scheme_code": "B", "allocation": 10}]
            ),
        )
        resp2 = client.post(
            "/api/portfolio/mutual-fund-analysis/what-if",
            json=self._payload(
                [{"scheme_code": "A", "allocation": 10}, {"scheme_code": "B", "allocation": 90}]
            ),
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["scenario"]["allocations"] == [
            {"scheme_code": "A", "allocation": 90.0},
            {"scheme_code": "B", "allocation": 10.0},
        ]
        assert resp2.json()["scenario"]["allocations"] == [
            {"scheme_code": "A", "allocation": 10.0},
            {"scheme_code": "B", "allocation": 90.0},
        ]
        # Both requests report the SAME (unmodified) current allocation.
        assert resp1.json()["current"]["allocations"] == resp2.json()["current"]["allocations"]
        # Different scenario weights produce different CAGR deltas.
        assert resp1.json()["deltas"]["cagr"] != resp2.json()["deltas"]["cagr"]
