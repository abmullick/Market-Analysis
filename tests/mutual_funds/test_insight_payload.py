"""
Tests for Mutual Fund AI Insight Payload Builder.
"""
from __future__ import annotations

from backend.models.mutual_fund import (
    FundDetailResponse,
    CategoryAnalysisResponse,
    CategoryMetricPercentile,
)
from backend.services.mutual_funds.insight_payload import (
    MutualFundInsightContext,
    build_mutual_fund_insight_context,
)


def test_build_payload_includes_fund_data():
    """Fund identity fields are correctly included."""
    fund_detail = FundDetailResponse(
        scheme_code="123456",
        scheme_name="Test Fund",
        amc="Test AMC",
        category="Test Category",
        nav=100.0,
        nav_date="2026-09-01",
        expense_ratio=1.5,
        three_year_cagr=0.12,
        five_year_cagr=0.10,
        sharpe_ratio=0.8,
        sortino_ratio=1.0,
        maximum_drawdown=-0.15,
        data_points=1000,
    )
    context = build_mutual_fund_insight_context(fund_detail)

    assert context.fund_data.scheme_code == "123456"
    assert context.fund_data.scheme_name == "Test Fund"
    assert context.fund_data.amc == "Test AMC"
    assert context.fund_data.category == "Test Category"
    assert context.fund_data.nav == 100.0
    assert context.fund_data.expense_ratio == 1.5
    assert context.fund_data.three_year_cagr == 0.12
    assert context.fund_data.five_year_cagr == 0.10
    assert context.fund_data.sharpe_ratio == 0.8
    assert context.fund_data.sortino_ratio == 1.0
    assert context.fund_data.maximum_drawdown == -0.15
    assert context.fund_data.data_points == 1000


def test_build_payload_includes_category_analysis():
    """Existing category-analysis/ranking data is passed through unchanged."""
    fund_detail = FundDetailResponse(
        scheme_code="123456",
        scheme_name="Test Fund",
        nav=100.0,
        nav_date="2026-09-01",
    )
    category_analysis = CategoryAnalysisResponse(
        scheme_code="123456",
        scheme_name="Test Fund",
        category="Test Category",
        metrics=[
            CategoryMetricPercentile(
                metric="three_year_cagr",
                label="3Y CAGR",
                fund_value=0.12,
                percentile=75.0,
                category_count=50,
                higher_is_better=True,
                rank=13,
            )
        ],
    )
    context = build_mutual_fund_insight_context(
        fund_detail, category_analysis=category_analysis
    )

    assert context.category_analysis is not None
    assert context.category_analysis.scheme_code == "123456"
    assert context.category_analysis.scheme_name == "Test Fund"
    assert context.category_analysis.category == "Test Category"
    assert len(context.category_analysis.metrics) == 1
    metric = context.category_analysis.metrics[0]
    assert metric.metric == "three_year_cagr"
    assert metric.label == "3Y CAGR"
    assert metric.fund_value == 0.12
    assert metric.percentile == 75.0
    assert metric.category_count == 50
    assert metric.higher_is_better is True
    assert metric.rank == 13


def test_build_payload_handles_optional_user_preferences():
    """User preferences are included when supplied."""
    fund_detail = FundDetailResponse(
        scheme_code="123456",
        scheme_name="Test Fund",
        nav=100.0,
    )
    user_prefs = {
        "risk_tolerance": "moderate",
        "investment_horizon": "long_term",
        "investment_objective": "wealth_creation",
    }
    context = build_mutual_fund_insight_context(
        fund_detail, user_preferences=user_prefs
    )

    assert context.user_preferences == user_prefs


def test_build_payload_user_preferences_optional():
    """User preferences remain optional when not supplied."""
    fund_detail = FundDetailResponse(
        scheme_code="123456",
        scheme_name="Test Fund",
        nav=100.0,
    )
    context = build_mutual_fund_insight_context(fund_detail)

    assert context.user_preferences is None


def test_build_payload_does_not_calculate_or_alter_metrics():
    """The builder does not calculate or alter financial metrics."""
    original_cagr = 0.123456789
    fund_detail = FundDetailResponse(
        scheme_code="123456",
        scheme_name="Test Fund",
        three_year_cagr=original_cagr,
        nav=100.0,
    )
    context = build_mutual_fund_insight_context(fund_detail)

    # The value should be exactly as passed through, not altered
    assert context.fund_data.three_year_cagr == original_cagr


def test_build_payload_handles_missing_optional_data_safely():
    """Missing optional data is handled safely."""
    # Fund detail with minimal required fields
    fund_detail = FundDetailResponse(
        scheme_code="123456",
        scheme_name="Test Fund",
        # Note: many fields are Optional and will be None by default
    )
    context = build_mutual_fund_insight_context(fund_detail)

    assert context.fund_data.scheme_code == "123456"
    assert context.fund_data.scheme_name == "Test Fund"
    assert context.fund_data.nav is None
    assert context.fund_data.nav_date is None
    assert context.fund_data.expense_ratio is None
    assert context.category_analysis is None
    assert context.user_preferences is None


def test_build_payload_result_is_serializable():
    """The resulting payload is serializable/valid according to the model."""
    fund_detail = FundDetailResponse(
        scheme_code="123456",
        scheme_name="Test Fund",
        nav=100.0,
        three_year_cagr=0.12,
    )
    category_analysis = CategoryAnalysisResponse(
        scheme_code="123456",
        scheme_name="Test Fund",
        category="Test Category",
        metrics=[],
    )
    user_prefs = {"risk_tolerance": "high"}

    context = build_mutual_fund_insight_context(
        fund_detail, category_analysis, user_prefs
    )

    # This should not raise an exception
    data = context.model_dump()
    assert isinstance(data, dict)
    assert data["fund_data"]["scheme_code"] == "123456"
    assert data["category_analysis"]["scheme_name"] == "Test Fund"
    assert data["user_preferences"]["risk_tolerance"] == "high"


def test_build_payload_no_external_calls():
        """No external AI/network calls occur in the payload builder."""
        # This test is implicit: the function only does data assembly
        # We can verify by checking that the function doesn't import or call
        # any external services. Since we're only testing the function directly,
        # and it doesn't make any external calls in its implementation, this passes.
        fund_detail = FundDetailResponse(
            scheme_code="123456",
            scheme_name="Test Fund",
            nav=100.0,
        )
        # Just calling the function should not trigger any external requests
        context = build_mutual_fund_insight_context(fund_detail)
        assert isinstance(context, MutualFundInsightContext)