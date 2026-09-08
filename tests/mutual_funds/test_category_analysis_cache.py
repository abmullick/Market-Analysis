"""Regression tests for the category-analysis endpoint cache ordering.

Optimization 4: on a warm category-analysis cache, the endpoint must return the
cached analysis using the lightweight scheme lookup, WITHOUT running the
expensive full fund-detail computation (metrics lookup, metadata, AUM
aggregation) or any peer batch calculation. On a cache miss the full
computation path must still run unchanged.
"""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models.mutual_fund import CategoryMetricPercentile
from backend.routes.mutual_funds import router
from backend.routes import mutual_funds as routes


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix="/api/mutual-funds")
    return TestClient(app)


def _scheme(code="120716", category="Large Cap Fund"):
    return SimpleNamespace(
        scheme_code=code,
        scheme_name=f"Fund {code}",
        amc="AMC",
        category=category,
        sub_category=None,
        nav=100.0,
        nav_date="2026-01-01",
        expense_ratio=None,
        minimum_investment=None,
        fund_manager=None,
        asset_allocation=None,
        top_holdings=None,
    )


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value
    return _inner


def _never(name):
    async def _fail(*args, **kwargs):
        raise AssertionError(f"{name} must not run on a warm category-analysis cache")
    return _fail


CACHED_ANALYSIS = {
    "metrics": [
        {"metric": "1Y_return", "label": "1Y Return", "fund_value": 0.12,
         "percentile": 55.0, "category_count": 10, "rank": 5},
    ],
}


def test_warm_category_cache_skips_expensive_detail(client, monkeypatch):
    """Cache hit must serve the cached analysis without full-detail work."""
    monkeypatch.setattr(routes.fetcher, "get_scheme", _async_return(_scheme()))
    monkeypatch.setattr(
        routes, "get_cached_category_analysis", lambda category: CACHED_ANALYSIS
    )
    monkeypatch.setattr(routes, "get_fund_detail", _never("get_fund_detail"))
    monkeypatch.setattr(routes.fetcher, "get_metrics_batch", _never("get_metrics_batch"))
    monkeypatch.setattr(
        routes.fetcher, "get_ranking_candidates_by_category",
        _never("get_ranking_candidates_by_category"),
    )

    resp = client.get("/api/mutual-funds/120716/category-analysis")
    assert resp.status_code == 200
    body = resp.json()
    assert body["scheme_code"] == "120716"
    assert body["scheme_name"] == "Fund 120716"
    assert body["category"] == "Large Cap Fund"
    # cached metrics pass through the same response model as before
    expected = [CategoryMetricPercentile(**m).model_dump() for m in CACHED_ANALYSIS["metrics"]]
    assert body["metrics"] == expected


def test_cold_cache_still_computes_percentiles(client, monkeypatch):
    """Cache miss must fall back to the full (unchanged) computation path."""
    monkeypatch.setattr(routes.fetcher, "get_scheme", _async_return(_scheme()))
    monkeypatch.setattr(routes, "get_cached_category_analysis", lambda category: None)

    detail = SimpleNamespace(
        scheme_code="120716",
        scheme_name="Fund 120716",
        category="Large Cap Fund",
    )

    peers = [
        {"scheme_code": "999", "scheme_name": "Peer"},
        {"scheme_code": "120716", "scheme_name": "Fund 120716"},
    ]

    async def _candidates(category):
        return peers

    async def _batch(funds, criteria):
        # one metrics dict per fund, in order
        return [{"one_year_return": 0.1 + i * 0.01} for i, _ in enumerate(funds)]

    monkeypatch.setattr(routes, "get_fund_detail", _async_return(detail))
    monkeypatch.setattr(routes.fetcher, "get_ranking_candidates_by_category", _candidates)
    monkeypatch.setattr(routes.fetcher, "get_metrics_batch", _batch)

    put_calls = []

    def _put(category, data, *args, **kwargs):
        put_calls.append((category, data))

    monkeypatch.setattr(routes, "cache_put_category_analysis", _put)

    resp = client.get("/api/mutual-funds/120716/category-analysis")
    assert resp.status_code == 200
    body = resp.json()
    assert body["scheme_code"] == "120716"
    assert len(body["metrics"]) > 0
    # result must have been written to the shared category-analysis cache
    assert len(put_calls) == 1


def test_scheme_failure_maps_to_502(client, monkeypatch):
    """Scheme lookup failure keeps the same 502 behavior as before."""

    async def _boom(code):
        raise RuntimeError("scheme unavailable")

    monkeypatch.setattr(routes.fetcher, "get_scheme", _boom)

    resp = client.get("/api/mutual-funds/120716/category-analysis")
    assert resp.status_code == 502
    assert "Failed to fetch fund detail" in resp.json()["detail"]


def test_missing_category_maps_to_400(client, monkeypatch):
    """A fund without category information still yields the same 400."""
    monkeypatch.setattr(routes.fetcher, "get_scheme", _async_return(_scheme(category=None)))

    resp = client.get("/api/mutual-funds/120716/category-analysis")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Fund has no category information"

