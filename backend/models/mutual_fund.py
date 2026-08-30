from pydantic import BaseModel
from typing import Any, Optional


class MutualFund(BaseModel):
    scheme_code: str
    scheme_name: str
    amc: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    nav: Optional[float] = None
    nav_date: Optional[str] = None
    one_year_return: Optional[float] = None
    three_year_return: Optional[float] = None
    five_year_return: Optional[float] = None
    expense_ratio: Optional[float] = None
    minimum_investment: Optional[float] = None
    fund_manager: Optional[str] = None
    asset_allocation: Optional[dict[str, float]] = None
    top_holdings: Optional[list[dict[str, Any]]] = None


class NAVRecord(BaseModel):
    date: str
    nav: float


class SchemeSearchResult(BaseModel):
    scheme_code: str
    scheme_name: str
    amc: str
    category: str
    sub_category: Optional[str] = None


class FundMetrics(BaseModel):
    scheme_code: str
    scheme_name: Optional[str] = None
    category: Optional[str] = None
    calculated_at: Optional[str] = None
    data_start_date: Optional[str] = None
    data_end_date: Optional[str] = None
    data_points: int = 0
    years_available: Optional[float] = None

    one_year_return: Optional[float] = None
    three_year_cagr: Optional[float] = None
    five_year_cagr: Optional[float] = None
    ten_year_cagr: Optional[float] = None

    annualized_volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    maximum_drawdown: Optional[float] = None
    downside_deviation: Optional[float] = None

    rolling_return_consistency: Optional[dict[str, Any]] = None


class CriterionConfig(BaseModel):
    name: str
    weight: float


class RankingRequest(BaseModel):
    category: str
    criteria: list[CriterionConfig]
    auto_renormalize: bool = True


class CriterionScore(BaseModel):
    criterion: str
    weight: float
    score: Optional[float] = None
    raw_value: Optional[Any] = None


class FundRank(BaseModel):
    scheme_code: str
    scheme_name: str
    category: Optional[str] = None
    rank: Optional[int] = None
    overall_score: Optional[float] = None
    criteria_scores: list[CriterionScore] = []


class RankingResponse(BaseModel):
    category: str
    rankings: list[FundRank]
