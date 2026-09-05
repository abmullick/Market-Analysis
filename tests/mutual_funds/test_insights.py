from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.models.mutual_fund import CategoryAnalysisResponse, CategoryMetricPercentile, FundDetailResponse
from backend.routes.mutual_funds import router
from backend.services.ai.groq import InsightResponse


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix="/api/mutual-funds")
    return TestClient(app)


@pytest.fixture
def fund_detail():
    return FundDetailResponse(
        scheme_code="123456",
        scheme_name="Test Fund",
        amc="Test AMC",
        category="Test Category",
        nav=100.0,
        three_year_cagr=0.12,
        sharpe_ratio=0.8,
    )


@pytest.fixture
def category_analysis():
    return CategoryAnalysisResponse(
        scheme_code="123456",
        scheme_name="Test Fund",
        category="Test Category",
        metrics=[CategoryMetricPercentile(
            metric="three_year_cagr",
            label="3Y CAGR",
            fund_value=0.12,
            percentile=75.0,
            category_count=50,
            higher_is_better=True,
            rank=13,
        )],
    )


@pytest.fixture
def compact_payload():
    return {
        "selected_fund": {
            "scheme_name": "Test Fund",
            "category": "Test Category",
            "performance": {"three_year_cagr": 0.12},
        },
        "ranking": {
            "rank": 4,
            "total_funds": 50,
            "percentile": 92,
            "metric_scores": [{"criterion": "3Y_cagr", "score": 88}],
        },
        "category_analysis": {
            "metrics": [{"metric": "3Y_cagr", "percentile": 75}],
        },
        "peers": [{"rank": 3, "name": "Peer Fund", "score": 89}],
        "user_preferences": {
            "categories": ["Test Category"],
            "screening_filters": [{"field": "amc", "operator": "contains", "values": ["Test"]}],
            "criteria": [{"name": "3Y_cagr", "weight": 100}],
            "auto_renormalize": True,
        },
    }


@pytest.fixture
def insight_response():
    return InsightResponse(
        summary="Test summary",
        key_points=["Point"],
        risks=["Risk"],
        opportunities=["Opportunity"],
        recommendation="Recommendation",
    )


def test_endpoint_uses_compact_context_and_exact_preferences(
    client, fund_detail, category_analysis, compact_payload, insight_response
):
    with patch("backend.routes.mutual_funds.get_fund_detail", new_callable=AsyncMock) as detail_mock, \
         patch("backend.routes.mutual_funds.get_category_analysis", new_callable=AsyncMock) as category_mock, \
         patch("backend.routes.mutual_funds.build_mutual_fund_insight_context") as builder_mock, \
         patch("backend.routes.mutual_funds.AIInsightService.generate_insights", new_callable=AsyncMock) as ai_mock:
        detail_mock.return_value = fund_detail
        category_mock.return_value = category_analysis
        builder_mock.return_value = object()
        ai_mock.return_value = insight_response

        response = client.post("/api/mutual-funds/123456/insights", json=compact_payload)

    assert response.status_code == 200
    assert response.json() == insight_response.model_dump()
    builder_mock.assert_called_once_with(
        fund_detail=fund_detail,
        category_analysis=category_analysis,
        user_preferences=compact_payload["user_preferences"],
    )
    ai_mock.assert_awaited_once_with(
        data=compact_payload,
        context="fund_analysis",
    )
    assert ai_mock.await_args.kwargs["data"]["user_preferences"] == compact_payload["user_preferences"]
    assert "currentRankings" not in ai_mock.await_args.kwargs["data"]


def test_endpoint_handles_missing_category_analysis(
    client, fund_detail, compact_payload, insight_response
):
    with patch("backend.routes.mutual_funds.get_fund_detail", new_callable=AsyncMock) as detail_mock, \
         patch("backend.routes.mutual_funds.get_category_analysis", new_callable=AsyncMock) as category_mock, \
         patch("backend.routes.mutual_funds.build_mutual_fund_insight_context") as builder_mock, \
         patch("backend.routes.mutual_funds.AIInsightService.generate_insights", new_callable=AsyncMock) as ai_mock:
        detail_mock.return_value = fund_detail
        category_mock.side_effect = HTTPException(status_code=404, detail="Unavailable")
        builder_mock.return_value = object()
        ai_mock.return_value = insight_response

        response = client.post("/api/mutual-funds/123456/insights", json=compact_payload)

    assert response.status_code == 200
    builder_mock.assert_called_once_with(
        fund_detail=fund_detail,
        category_analysis=None,
        user_preferences=compact_payload["user_preferences"],
    )


def test_invalid_scheme_code_returns_404(client, compact_payload):
    response = client.post("/api/mutual-funds/not-a-scheme/insights", json=compact_payload)
    assert response.status_code == 404


def test_missing_fund_data_preserves_existing_http_error(client, compact_payload):
    with patch("backend.routes.mutual_funds.get_fund_detail", new_callable=AsyncMock) as detail_mock:
        detail_mock.side_effect = HTTPException(status_code=404, detail="Fund not found")
        response = client.post("/api/mutual-funds/999999/insights", json=compact_payload)

    assert response.status_code == 404


def test_ai_provider_failure_returns_503(client, fund_detail, compact_payload):
    with patch("backend.routes.mutual_funds.get_fund_detail", new_callable=AsyncMock) as detail_mock, \
         patch("backend.routes.mutual_funds.get_category_analysis", new_callable=AsyncMock) as category_mock, \
         patch("backend.routes.mutual_funds.build_mutual_fund_insight_context") as builder_mock, \
         patch("backend.routes.mutual_funds.AIInsightService.generate_insights", new_callable=AsyncMock) as ai_mock:
        detail_mock.return_value = fund_detail
        category_mock.return_value = None
        builder_mock.return_value = object()
        ai_mock.side_effect = RuntimeError("provider unavailable")

        response = client.post("/api/mutual-funds/123456/insights", json=compact_payload)

    assert response.status_code == 503
    assert response.json()["detail"] == "The AI service is temporarily unavailable"


def test_invalid_request_returns_422(client):
    response = client.post("/api/mutual-funds/123456/insights", json={})
    assert response.status_code == 422


def test_router_keeps_existing_mutual_fund_routes():
    paths = {route.path for route in router.routes}
    assert "/{scheme_code}/detail" in paths
    assert "/{scheme_code}/category-analysis" in paths
    assert "/{scheme_code}/insights" in paths
