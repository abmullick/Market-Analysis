from pydantic import BaseModel, model_validator
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
    one_year_volatility: Optional[float] = None
    three_year_volatility: Optional[float] = None
    five_year_volatility: Optional[float] = None
    ten_year_volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    maximum_drawdown: Optional[float] = None
    downside_deviation: Optional[float] = None

    rolling_return_consistency: Optional[dict[str, Any]] = None


class CriterionConfig(BaseModel):
    name: str
    weight: float


class ScreeningFilter(BaseModel):
    field: str
    operator: str
    value: Optional[Any] = None
    value_min: Optional[Any] = None
    value_max: Optional[Any] = None
    values: Optional[list[str]] = None

    @model_validator(mode="after")
    def validate_filter_value(self):
        """Validate that filter values match the expected type for the field."""
        numeric_fields = {
            "aum_cr",
            "one_year_return", "three_year_cagr", "five_year_cagr", "ten_year_cagr",
            "sharpe_ratio", "sortino_ratio", "annualized_volatility",
            "maximum_drawdown", "downside_deviation", "consistency"
        }
        date_fields = {"first_nav_date"}
        categorical_fields = {"amc", "plan", "option", "scheme_code", "scheme_name"}

        if self.field in numeric_fields:
            # Numeric filters require numeric value
            if self.value is not None and not isinstance(self.value, (int, float)):
                raise ValueError(f"Field '{self.field}' requires a numeric value, got {type(self.value).__name__}")
            if self.value_min is not None and not isinstance(self.value_min, (int, float)):
                raise ValueError(f"Field '{self.field}' requires numeric value_min")
            if self.value_max is not None and not isinstance(self.value_max, (int, float)):
                raise ValueError(f"Field '{self.field}' requires numeric value_max")
        elif self.field in date_fields:
            # Date filters require string value in YYYY-MM-DD format
            if self.value is not None and not isinstance(self.value, str):
                raise ValueError(f"Field '{self.field}' requires a date string (YYYY-MM-DD), got {type(self.value).__name__}")
            if self.value == "":
                raise ValueError(f"Field '{self.field}' cannot have empty value")
            if self.value_min is not None and not isinstance(self.value_min, str):
                raise ValueError(f"Field '{self.field}' requires date string value_min")
            if self.value_max is not None and not isinstance(self.value_max, str):
                raise ValueError(f"Field '{self.field}' requires date string value_max")
        elif self.field in categorical_fields:
            # Categorical filters require string value
            if self.value is not None and not isinstance(self.value, str):
                raise ValueError(f"Field '{self.field}' requires a string value, got {type(self.value).__name__}")
            if self.value == "":
                raise ValueError(f"Field '{self.field}' cannot have empty value")
        # For unknown fields, allow any type (backward compatibility)

        return self


class RankingRequest(BaseModel):
    category: Any = None  # Can be str (single) or list[str] (multiple)
    criteria: list[CriterionConfig]
    auto_renormalize: bool = True
    screening_filters: list[ScreeningFilter] = []

    @model_validator(mode="after")
    def validate_category(self):
        """Normalize category to list format."""
        if self.category is None:
            self.category = []
        elif isinstance(self.category, str):
            self.category = [self.category]
        elif isinstance(self.category, list):
            # Remove duplicates while preserving order
            seen = set()
            unique = []
            for c in self.category:
                if c and c not in seen:
                    seen.add(c)
                    unique.append(c)
            self.category = unique
        else:
            raise ValueError("Category must be a string or list of strings")
        return self


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
    nav: Optional[float] = None
    nav_date: Optional[str] = None
    data_points: Optional[int] = None
    aum_cr: Optional[float] = None
    aum_quarter: Optional[str] = None
    aum_quarter_end: Optional[str] = None
    total_aum_cr: Optional[float] = None
    total_aum_quarter: Optional[str] = None
    total_aum_quarter_end: Optional[str] = None
    first_nav_date: Optional[str] = None


class RankingResponse(BaseModel):
    category: str
    rankings: list[FundRank]


class FundDetailResponse(BaseModel):
    scheme_code: str
    scheme_name: str
    amc: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    plan: Optional[str] = None
    option: Optional[str] = None
    nav: Optional[float] = None
    nav_date: Optional[str] = None
    aum_cr: Optional[float] = None
    aum_quarter: Optional[str] = None
    aum_quarter_end: Optional[str] = None
    total_aum_cr: Optional[float] = None
    total_aum_quarter: Optional[str] = None
    total_aum_quarter_end: Optional[str] = None
    first_nav_date: Optional[str] = None
    fund_age_years: Optional[float] = None
    expense_ratio: Optional[float] = None
    minimum_investment: Optional[float] = None
    fund_manager: Optional[str] = None
    asset_allocation: Optional[dict[str, float]] = None
    top_holdings: Optional[list[dict[str, Any]]] = None

    one_year_return: Optional[float] = None
    three_year_cagr: Optional[float] = None
    five_year_cagr: Optional[float] = None
    ten_year_cagr: Optional[float] = None
    annualized_volatility: Optional[float] = None
    one_year_volatility: Optional[float] = None
    three_year_volatility: Optional[float] = None
    five_year_volatility: Optional[float] = None
    ten_year_volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    maximum_drawdown: Optional[float] = None
    downside_deviation: Optional[float] = None
    rolling_return_consistency: Optional[dict[str, Any]] = None

    data_points: int = 0
    data_start_date: Optional[str] = None
    data_end_date: Optional[str] = None


class CategoryMetricPercentile(BaseModel):
    metric: str
    label: str
    fund_value: Optional[float] = None
    percentile: Optional[float] = None
    category_count: int = 0
    higher_is_better: bool = True
    rank: Optional[int] = None


class CategoryAnalysisResponse(BaseModel):
    scheme_code: str
    scheme_name: str
    category: str
    metrics: list[CategoryMetricPercentile] = []


class NAVHistoryResponse(BaseModel):
    scheme_code: str
    scheme_name: str
    dates: list[str]
    navs: list[float]


class RollingReturnResponse(BaseModel):
    scheme_code: str
    scheme_name: str
    period_years: int
    dates: list[str]
    returns: list[float]
    summary: Optional[dict[str, Any]] = None
    insufficient_history: bool = False
