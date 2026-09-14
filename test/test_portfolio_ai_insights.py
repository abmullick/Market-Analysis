"""Unit tests for the Portfolio Builder AI Insights endpoint.

Focuses on the additive, bounded AI endpoint only:
- the `portfolio_builder` context is used (portfolio, not individual fund),
- no financial calculation code is invoked (the deterministic context is
  forwarded straight to the AI service),
- the response mirrors the existing InsightResponse contract,
- the request model rejects malformed payloads.

Run:
    pytest test/test_portfolio_ai_insights.py -v
"""
from typing import Any

import pytest
from pydantic import ValidationError

from backend.routes.portfolio import (
    PortfolioInsightsRequest,
    generate_mutual_fund_portfolio_insights,
)
from backend.services.ai.groq import AIInsightService, InsightResponse

FUNDS_PAYLOAD = {
    "portfolio_input": {
        "fund_count": 2,
        "total_allocation": 100,
        "funds": [
            {
                "scheme_code": "122639",
                "scheme_name": "HDFC Flexi Cap Fund",
                "amc": "HDFC",
                "category": "Flexi Cap",
                "allocation": 60,
            },
            {
                "scheme_code": "119598",
                "scheme_name": "Mirae Asset Large Cap Fund",
                "amc": "Mirae",
                "category": "Large Cap",
                "allocation": 40,
            },
        ],
    },
    "portfolio_analysis": {
        "metrics": {
            "cagr": 0.148,
            "annualized_volatility": 0.112,
            "sharpe_ratio": 1.21,
            "maximum_drawdown": 0.182,
            "years": 6.2,
        },
        "health_score": {"score": 78.4, "confidence": {"tier": "B", "label": "Good"}},
        "benchmark": {
            "available": True,
            "portfolio_cagr": 0.148,
            "nifty50_tri_cagr": 0.135,
            "nifty50_outperformance": 0.013,
        },
        "warnings": ["Sample warning."],
    },
}


class FakeAIInsightService:
    """In-memory stand-in that records what the endpoint asked for."""

    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], str, str | None]] = []

    async def generate_insights(
        self, data: dict[str, Any], context: str = "fund_analysis", focus: str | None = None
    ) -> InsightResponse:
        self.calls.append((data, context, focus))
        return InsightResponse(
            summary="Balanced portfolio with a strong risk-adjusted profile.",
            key_points=["Broad category spread across two funds."],
            risks=["Top allocation exceeds 50%."],
            opportunities=["Sharpe ratio above 1.0."],
            recommendation="Review the concentration in the largest holding.",
        )


@pytest.mark.asyncio
async def test_portfolio_insights_uses_portfolio_builder_context(monkeypatch):
    fake = FakeAIInsightService()
    monkeypatch.setattr(AIInsightService, "generate_insights", fake.generate_insights)

    payload = PortfolioInsightsRequest(
        portfolio_input=FUNDS_PAYLOAD["portfolio_input"],
        portfolio_analysis=FUNDS_PAYLOAD["portfolio_analysis"],
    )
    response = await generate_mutual_fund_portfolio_insights(payload)

    assert isinstance(response, InsightResponse)
    assert response.summary
    assert len(fake.calls) == 1
    data, context, focus = fake.calls[0]
    assert context == "portfolio_builder"
    assert focus is not None
    # The deterministic context is forwarded untouched; nothing recomputed.
    assert data["portfolio_input"]["funds"][0]["scheme_code"] == "122639"
    assert data["portfolio_analysis"]["metrics"]["cagr"] == 0.148


@pytest.mark.asyncio
async def test_portfolio_insights_does_not_recalculate(monkeypatch):
    """The endpoint must never call the portfolio calculation engine."""
    import backend.routes.portfolio as portfolio_route

    fake = FakeAIInsightService()
    monkeypatch.setattr(AIInsightService, "generate_insights", fake.generate_insights)
    monkeypatch.setattr(
        portfolio_route, "calculate_portfolio_analysis", lambda *_: (_ for _ in ()).throw(AssertionError())
    )

    payload = PortfolioInsightsRequest(
        portfolio_input=FUNDS_PAYLOAD["portfolio_input"],
        portfolio_analysis=FUNDS_PAYLOAD["portfolio_analysis"],
    )
    response = await generate_mutual_fund_portfolio_insights(payload)
    assert response.summary  # calculation engine never touched


@pytest.mark.asyncio
async def test_portfolio_insights_maps_ai_failure_to_503(monkeypatch):
    async def boom(*_, **__):
        raise RuntimeError("AI service down")

    monkeypatch.setattr(AIInsightService, "generate_insights", boom)

    payload = PortfolioInsightsRequest(
        portfolio_input=FUNDS_PAYLOAD["portfolio_input"],
        portfolio_analysis=FUNDS_PAYLOAD["portfolio_analysis"],
    )
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        await generate_mutual_fund_portfolio_insights(payload)
    assert excinfo.value.status_code == 503


def test_portfolio_insights_request_rejects_missing_sections():
    with pytest.raises(ValidationError):
        PortfolioInsightsRequest(portfolio_input={"funds": []})
    with pytest.raises(ValidationError):
        PortfolioInsightsRequest(portfolio_analysis={"metrics": {}})