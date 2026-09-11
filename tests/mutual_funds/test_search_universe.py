"""Tests for AMFI-universe based scheme search (replaces MFAPI /mf/search).

Verifies that search matches against the full cached AMFI universe (name,
AMC, category, scheme code), can return more than 15 matches, paginates,
preserves the existing response shape, and never touches MFAPI search or
NAV/metric endpoints.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models.mutual_fund import MutualFund
from backend.routes.mutual_funds import router
from backend.services.mutual_funds.fetcher import MutualFundFetcher
from backend.config.settings import Settings


@pytest.fixture
def fetcher():
    return MutualFundFetcher(settings=Settings())


def _make_universe():
    """Synthetic AMFI universe: 20 'flexi' equity funds across 2 AMCs,
    plus some non-matching funds."""
    universe = []
    code = 100000
    for i in range(1, 21):
        amc = "Alpha AMC" if i <= 10 else "Beta AMC"
        universe.append(MutualFund(
            scheme_code=str(code),
            scheme_name=f"Flexi Cap Fund {i:02d} - Direct Growth",
            amc=amc,
            category="Equity Scheme - Flexi Cap Fund",
            nav_date="08-Sep-2026",
        ))
        code += 1
    # Non-matching funds.
    universe.append(MutualFund(
        scheme_code=str(code),
        scheme_name="Large Cap Fund - Direct Growth",
        amc="Gamma AMC",
        category="Equity Scheme - Large Cap Fund",
        nav_date="08-Sep-2026",
    ))
    return universe


class TestLegacySchemeLifecycle:
    """Phase 2D.4 — current vs retired/legacy scheme handling.

    The lifecycle signal is AMFI-reported: each scheme line carries the date
    AMFI last published a NAV for it. Schemes whose last NAV lags well behind
    the newest NAV date in the universe are stale/retired. No inference is
    made from NAV-history length, and no hard-coded scheme mappings exist.
    """

    def _lifecycle_universe(self):
        return [
            # Current scheme (NAV published on the newest universe date).
            MutualFund(scheme_code="118652", scheme_name="Nippon India Multi Cap Fund",
                       amc="Nippon India Mutual Fund",
                       category="Equity Scheme - Multi Cap Fund",
                       nav_date="08-Sep-2026"),
            # Retired/legacy twin (AMFI keeps it listed with its final NAV).
            MutualFund(scheme_code="106253", scheme_name="Nippon India Multi Cap Fund",
                       amc="Nippon India Mutual Fund",
                       category="Equity Scheme - Multi Cap Fund",
                       nav_date="25-Apr-2017"),
            # Recently delayed publication (within the 14-day grace) — NOT stale.
            MutualFund(scheme_code="122639", scheme_name="Parag Parikh Flexi Cap Fund",
                       amc="Parag Parikh Mutual Fund",
                       category="Equity Scheme - Flexi Cap Fund",
                       nav_date="27-Aug-2026"),
            # No NAV date reported at all — must not be classified stale.
            MutualFund(scheme_code="999999", scheme_name="Some Fund Without Date",
                       amc="Some AMC", category="Equity Scheme - Other",
                       nav_date=None),
        ]

    def test_stale_scheme_flagged(self, fetcher):
        with _patch_universe(fetcher, self._lifecycle_universe()):
            results = asyncio.run(fetcher.search_schemes("Multi Cap"))
        by_code = {r.scheme_code: r for r in results}
        assert by_code["106253"].is_stale is True
        assert by_code["106253"].nav_date == "25-Apr-2017"

    def test_current_scheme_not_flagged(self, fetcher):
        with _patch_universe(fetcher, self._lifecycle_universe()):
            results = asyncio.run(fetcher.search_schemes("Multi Cap"))
        by_code = {r.scheme_code: r for r in results}
        assert by_code["118652"].is_stale is False

    def test_recent_publication_within_grace_not_stale(self, fetcher):
        # 12 days behind the newest NAV date → within the grace window.
        with _patch_universe(fetcher, self._lifecycle_universe()):
            results = asyncio.run(fetcher.search_schemes("Parag Parikh"))
        assert results[0].is_stale is False

    def test_missing_nav_date_not_classified_stale(self, fetcher):
        with _patch_universe(fetcher, self._lifecycle_universe()):
            results = asyncio.run(fetcher.search_schemes("Without Date"))
        assert results[0].is_stale is False

    def test_current_schemes_ranked_before_legacy(self, fetcher):
        with _patch_universe(fetcher, self._lifecycle_universe()):
            results = asyncio.run(fetcher.search_schemes("Multi Cap"))
        codes = [r.scheme_code for r in results]
        # Same name, same AMC: the current scheme must come first.
        assert codes.index("118652") < codes.index("106253")

    def test_search_response_shape_preserved_with_lifecycle(self, client, fetcher):
        with _patch_universe(fetcher, self._lifecycle_universe()):
            resp = client.get("/api/mutual-funds/search", params={"q": "Multi Cap"})
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"query", "count", "results", "total"}
        assert set(body["results"][0].keys()) == {
            "scheme_code", "scheme_name", "amc", "category", "sub_category",
            "nav_date", "is_stale", "first_nav_date", "is_active",
        }

    def test_exact_code_search_still_works(self, fetcher):
        with _patch_universe(fetcher, self._lifecycle_universe()):
            results = asyncio.run(fetcher.search_schemes("106253"))
        assert [r.scheme_code for r in results] == ["106253"]


@pytest.fixture
def client(fetcher):
    app = FastAPI()
    app.include_router(router, prefix="/api/mutual-funds")
    with patch("backend.routes.mutual_funds.fetcher", fetcher):
        yield TestClient(app)


def _patch_universe(fetcher, universe):
    return patch.object(fetcher, "get_all_schemes", new_callable=AsyncMock, return_value=universe)


def test_search_returns_more_than_15_matches(fetcher):
    """The old MFAPI hard cap was 15; universe search must return all matches."""
    with _patch_universe(fetcher, _make_universe()):
        results = asyncio.run(fetcher.search_schemes("flexi cap"))
    assert len(results) == 20


def test_search_matches_scheme_name(fetcher):
    universe = _make_universe()
    with _patch_universe(fetcher, universe):
        results = asyncio.run(fetcher.search_schemes("flexi cap fund 07"))
    # "07" can also appear inside other funds' scheme codes (multi-field
    # matching is intentional); the named fund must be among the matches.
    assert any(r.scheme_name == "Flexi Cap Fund 07 - Direct Growth" for r in results)
    assert all("flexi cap fund" in " ".join(filter(None, [r.scheme_name, r.amc, r.category, r.scheme_code])).lower() or "07" in r.scheme_code for r in results)


def test_search_matches_amc(fetcher):
    with _patch_universe(fetcher, _make_universe()):
        results = asyncio.run(fetcher.search_schemes("Alpha AMC flexi"))
    assert len(results) == 10
    assert all(r.amc == "Alpha AMC" for r in results)


def test_search_matches_category(fetcher):
    with _patch_universe(fetcher, _make_universe()):
        results = asyncio.run(fetcher.search_schemes("large cap"))
    assert len(results) == 1
    assert results[0].category == "Equity Scheme - Large Cap Fund"


def test_search_matches_scheme_code(fetcher):
    with _patch_universe(fetcher, _make_universe()):
        results = asyncio.run(fetcher.search_schemes("100003"))
    assert len(results) == 1
    assert results[0].scheme_code == "100003"


def test_search_zero_matches(fetcher):
    with _patch_universe(fetcher, _make_universe()):
        results = asyncio.run(fetcher.search_schemes("nonexistent-xyz"))
    assert results == []


def test_search_pagination(fetcher):
    universe = _make_universe()
    with _patch_universe(fetcher, universe):
        page1 = asyncio.run(fetcher.search_schemes("flexi", limit=8, offset=0))
        page2 = asyncio.run(fetcher.search_schemes("flexi", limit=8, offset=8))
        page3 = asyncio.run(fetcher.search_schemes("flexi", limit=8, offset=16))
    codes = [r.scheme_code for r in page1 + page2 + page3]
    assert len(codes) == 20 and len(set(codes)) == 20  # complete, no overlap


def test_route_response_shape_preserved(fetcher, client):
    """Response keeps {query, count, results} with the existing fields;
    `total` is additive for pagination."""
    with _patch_universe(fetcher, _make_universe()):
        resp = client.get("/api/mutual-funds/search", params={"q": "flexi"})
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) == {"query", "count", "results", "total"}
    assert data["query"] == "flexi"
    assert data["count"] == 20 and data["total"] == 20
    first = data["results"][0]
    assert set(first) == {"scheme_code", "scheme_name", "amc", "category", "sub_category",
                          "nav_date", "is_stale"}  # nav_date/is_stale: additive (2D.4)


def test_route_paginated_page_and_total(fetcher, client):
    with _patch_universe(fetcher, _make_universe()):
        resp = client.get("/api/mutual-funds/search", params={"q": "flexi", "limit": 5, "offset": 15})
    data = resp.json()
    assert data["count"] == 5
    assert data["total"] == 20
    assert len(data["results"]) == 5


def test_route_requires_query(client):
    # Missing 'q' is rejected by FastAPI request validation (422); an explicit
    # empty q="" still reaches the route and returns 400.
    assert client.get("/api/mutual-funds/search").status_code in (400, 422)
    assert client.get("/api/mutual-funds/search", params={"q": ""}).status_code == 400


def test_search_reuses_amfi_universe_not_mfapi(fetcher):
    """Search must go through get_all_schemes (cached AMFI universe) and must
    never call MFAPI search, NAV history, metrics or detail paths."""
    with (_patch_universe(fetcher, _make_universe()),
          patch.object(fetcher.mfapi, "search_schemes", new_callable=AsyncMock) as mfapi_search,
          patch.object(fetcher, "get_nav_history", new_callable=AsyncMock) as nav_hist,
          patch.object(fetcher, "get_metrics", new_callable=AsyncMock) as metrics,
          patch.object(fetcher, "get_scheme", new_callable=AsyncMock) as detail):
        asyncio.run(fetcher.search_schemes("flexi"))
        assert mfapi_search.await_count == 0
        assert nav_hist.await_count == 0
        assert metrics.await_count == 0
        assert detail.await_count == 0


def test_search_uses_cached_universe_once(fetcher):
    """Repeated searches reuse the cached universe (AMFI fetched once)."""
    universe = _make_universe()
    with (patch.object(fetcher, "_get_all_schemes_from_amfi", new_callable=AsyncMock, return_value=universe) as amfi_fetch,):
        asyncio.run(fetcher.search_schemes("flexi"))
        asyncio.run(fetcher.search_schemes("direct"))
        assert amfi_fetch.await_count == 1  # second search hits the in-memory cache
