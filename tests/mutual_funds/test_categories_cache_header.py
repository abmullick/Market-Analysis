"""Regression test: /categories sends a conservative browser-cache policy.

Optimization 5 (Priority 1): /categories is global read-only reference data,
identical for all users, so the browser may reuse it for a short period.
The header is client-directive only — no server-side response caching.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models.mutual_fund import MutualFund
from backend.routes.mutual_funds import router
from backend.routes import mutual_funds as routes
from backend.services.mutual_funds.category_normalizer import normalize_category


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix="/api/mutual-funds")
    return TestClient(app)


def _scheme(code, category):
    return MutualFund(
        scheme_code=code,
        scheme_name=f"Fund {code}",
        amc="AMC",
        category=category,
        nav=100.0,
        nav_date="2026-01-01",
    )


def test_categories_cache_control_header(client, monkeypatch):
    async def _schemes():
        return [
            _scheme("1", "Equity Scheme - Large Cap Fund"),
            _scheme("2", "Equity Scheme - Large Cap Fund"),
            _scheme("3", "Hybrid Scheme - Balanced Fund"),
        ]

    monkeypatch.setattr(routes.fetcher, "get_all_schemes", _schemes)

    resp = client.get("/api/mutual-funds/categories")
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "private, max-age=300"
    # body unchanged (categories normalized to canonical form, as before)
    assert resp.json()["categories"] == sorted({
        normalize_category("Equity Scheme - Large Cap Fund"),
        normalize_category("Hybrid Scheme - Balanced Fund"),
    })
