"""
Mutual Fund AI Insight Payload Builder.

Builds a structured context for AI insights from existing deterministic
Mutual Fund Analysis results, without performing any financial calculations.
"""
from __future__ import annotations

from typing import Optional, Dict, Any

from pydantic import BaseModel

from backend.models.mutual_fund import FundDetailResponse, CategoryAnalysisResponse


class MutualFundInsightContext(BaseModel):
    """
    Context for Mutual Fund AI Insights.

    Contains deterministic fund data, category-relative analysis, and
    optional user preferences. The AI service will interpret this context
    to generate insights.
    """
    fund_data: FundDetailResponse
    category_analysis: Optional[CategoryAnalysisResponse] = None
    user_preferences: Optional[Dict[str, Any]] = None


def build_mutual_fund_insight_context(
    fund_detail: FundDetailResponse,
    category_analysis: Optional[CategoryAnalysisResponse] = None,
    user_preferences: Optional[Dict[str, Any]] = None
) -> MutualFundInsightContext:
    """
    Build Mutual Fund AI insight context from existing analysis results.

    Args:
        fund_detail: Deterministic fund data from /detail endpoint
        category_analysis: Category-relative analysis from /category-analysis endpoint (optional)
        user_preferences: User preferences dict (optional, to be supplied by caller)

    Returns:
        MutualFundInsightContext: Structured context for AI insights
    """
    return MutualFundInsightContext(
        fund_data=fund_detail,
        category_analysis=category_analysis,
        user_preferences=user_preferences
    )