from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routes.mutual_funds import router
from backend.services.ai.groq import InsightResponse


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix="/api/mutual-funds")
    return TestClient(app)


@pytest.fixture
def payload():
    return {
        "ranking_configuration": {
            "categories": ["Equity - Large Cap"],
            "screening_filters": [],
            "criteria": [{"name": "3Y_cagr", "weight": 100}],
            "auto_renormalize": True,
        },
        "ranking_summary": {
            "total_funds": 20,
            "displayed_funds": 20,
            "eligible_funds": 20,
            "categories": ["Equity - Large Cap"],
        },
        "top_funds": [{
            "rank": 1,
            "scheme_name": "Top Fund",
            "overall_score": 95.5,
            "metric_scores": [{"criterion": "3Y_cagr", "weight": 100, "score": 95}],
        }],
        "bottom_funds": [{"rank": 20, "scheme_name": "Lower Fund", "overall_score": 22.5}],
    }


@pytest.fixture
def response():
    return InsightResponse(
        summary="The ranking emphasizes three-year performance.",
        key_points=["Top funds score strongly on the selected criterion."],
        risks=["The ranking is concentrated in the selected weighting."],
        opportunities=["Investigate consistency beyond the primary criterion."],
        recommendation="Review the top funds against the intended objective.",
    )


def test_ranking_insights_uses_exact_compact_payload(client, payload, response):
    with patch("backend.routes.mutual_funds.AIInsightService.generate_insights", new_callable=AsyncMock) as ai_mock:
        ai_mock.return_value = response
        result = client.post("/api/mutual-funds/ranking-insights", json=payload)

    assert result.status_code == 200
    assert result.json() == response.model_dump()
    ai_mock.assert_awaited_once_with(
        data=payload,
        context="ranking_summary",
        focus="holistic interpretation of the supplied ranking drivers, trade-offs, risks, and opportunities",
    )
    assert ai_mock.await_args.kwargs["data"]["ranking_configuration"] == payload["ranking_configuration"]
    assert "currentRankings" not in ai_mock.await_args.kwargs["data"]


def test_invalid_ranking_request_returns_422(client):
    result = client.post("/api/mutual-funds/ranking-insights", json={})
    assert result.status_code == 422


def test_provider_failure_returns_generic_503(client, payload):
    with patch("backend.routes.mutual_funds.AIInsightService.generate_insights", new_callable=AsyncMock) as ai_mock:
        ai_mock.side_effect = RuntimeError("provider internals must not leak")
        result = client.post("/api/mutual-funds/ranking-insights", json=payload)

    assert result.status_code == 503
    assert result.json()["detail"] == "The AI service is temporarily unavailable"
    assert "provider internals" not in result.text


def test_router_has_separate_ranking_route():
    assert any(route.path == "/ranking-insights" for route in router.routes)
