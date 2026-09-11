from pydantic import BaseModel, Field
from typing import Any, Optional


class Holding(BaseModel):
    symbol: str
    name: Optional[str] = None
    quantity: Optional[float] = None
    average_price: Optional[float] = None
    current_price: Optional[float] = None
    invested_value: Optional[float] = None
    current_value: Optional[float] = None
    portfolio_weight: Optional[float] = None


# ---------------------------------------------------------------------------
# Mutual-fund portfolio analysis (allocation-based, client-side portfolio)
# ---------------------------------------------------------------------------


class PortfolioFundInput(BaseModel):
    scheme_code: str
    allocation: float = Field(ge=0, le=100, description="Target allocation in percent")


class PortfolioAnalysisRequest(BaseModel):
    funds: list[PortfolioFundInput]
    lookback_years: int | None = Field(
        default=None,
        ge=1,
        le=15,
        description=(
            "Optional lookback window in years. None (default) uses the COMPLETE "
            "available NAV history so the portfolio common period is derived "
            "dynamically from fund inception dates."
        ),
    )


class PortfolioSeriesPoint(BaseModel):
    date: str
    value: float


class PortfolioFundResult(BaseModel):
    scheme_code: str
    allocation: float
    effective_weight: float
    observations: int
    first_date: Optional[str] = None
    last_date: Optional[str] = None
    contributes: bool
    # Additive fund metadata (AMFI universe) used by the Health Score Fund Mix
    # component; None when unavailable.
    amc: Optional[str] = None
    category: Optional[str] = None
    is_stale: bool = False


class PortfolioMetricsData(BaseModel):
    cagr: Optional[float] = None
    annualized_volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    downside_deviation: Optional[float] = None
    maximum_drawdown: Optional[float] = None
    total_return: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    observations: int = 0
    years: Optional[float] = None


class FundReturnContribution(BaseModel):
    """Single fund's contribution to the portfolio's total return.

    ``contribution`` is a decimal expressed in portfolio-return percentage
    points (e.g. ``0.0524`` = +5.24 pp). It is derived from the existing
    constant-target-weight, daily-rebalanced portfolio methodology:

        contribution_i = sum_t w_i * r_i(t) * V(t-1)

    where ``V(t-1)`` is the portfolio's cumulative growth factor just before
    day ``t``. Contributions are therefore additive and reconcile exactly to
    the portfolio's total return over the common analysis period. They are
    intentionally NOT ``allocation x fund total return`` (which ignores
    compounding and daily rebalancing).

    ``contribution_percentage`` is the fund's share of the total positive
    contribution (for positive contributors) or of the total negative
    contribution (for negative contributors). It is ``None`` when that
    denominator is zero or undefined — never fabricated.
    """

    scheme_code: str
    scheme_name: Optional[str] = None
    allocation: float
    fund_return: float
    contribution: float
    contribution_percentage: Optional[float] = None


class ReturnContributionData(BaseModel):
    """Additive Return Contribution (performance attribution) section.

    Computed inside the existing portfolio daily-return pipeline using only
    data already available there (common dates, target weights, fund daily
    returns, cumulative growth factor). ``total_contribution`` equals the
    portfolio's total return up to float rounding; the residual is reported
    in ``reconciliation_difference``.
    """

    contributions: list[FundReturnContribution] = []
    total_contribution: float = 0.0
    portfolio_return: Optional[float] = None
    reconciliation_difference: float = 0.0


class PortfolioAnalysisResult(BaseModel):
    funds: list[PortfolioFundResult]
    metrics: PortfolioMetricsData
    series: list[PortfolioSeriesPoint]
    warnings: list[str] = []
    # Additive Phase 3A rolling-consistency windows (1Y/3Y/5Y) computed on the
    # portfolio growth series; None when history is too short for any window.
    rolling_consistency: Optional[dict[str, Any]] = None
    # Additive Phase 3A Health Score (None → not computed).
    health_score: Optional["HealthScoreData"] = None
    # Additive Phase 2E Portfolio-vs-Benchmark comparison (None → not computed).
    benchmark_data: Optional["BenchmarkData"] = None
    # Additive Return Contribution (performance attribution); always populated
    # on a successful analysis. Purely derived from the existing pipeline.
    return_contribution: Optional[ReturnContributionData] = None


# ---------------------------------------------------------------------------
# Portfolio vs Benchmark comparison (Phase 2E) — additive response metadata
# ---------------------------------------------------------------------------


class BenchmarkData(BaseModel):
    """Benchmark comparison for the portfolio growth chart.

    All available series are rebased to 100 at ``common_start``. ``dates`` is
    the sorted set of valid published dates common to the portfolio and each
    available benchmark; the parallel value arrays (``portfolio``,
    ``nifty50_tri``, ``sp500_total_return_inr``) are aligned to ``dates``.

    CAGRs are computed over the same common comparison period the chart shows.
    Outperformance = portfolio CAGR − benchmark CAGR. ``sp500_total_return_inr``
    is the S&P 500 Total Return series converted into INR using the ECB/Frankfurter
    USD/INR reference rate (no price-only or synthetic series are ever used).
    """

    available: bool = False
    nifty50_tri_available: bool = False
    sp500_available: bool = False
    common_start: Optional[str] = None
    common_end: Optional[str] = None
    observations: int = 0
    dates: list[str] = []
    portfolio: list[float] = []
    nifty50_tri: list[float] = []
    sp500_total_return_inr: list[float] = []
    portfolio_cagr: Optional[float] = None
    nifty50_tri_cagr: Optional[float] = None
    sp500_total_return_cagr: Optional[float] = None
    nifty50_outperformance: Optional[float] = None
    sp500_outperformance: Optional[float] = None
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# Portfolio Health Score (Phase 3A) — additive response metadata
# ---------------------------------------------------------------------------


class HealthConfidence(BaseModel):
    tier: str  # "A" | "B" | "C" | "D"
    label: str


class HealthScoreComponents(BaseModel):
    return_quality: Optional[float] = None
    downside_risk: Optional[float] = None
    risk_adjusted_return: Optional[float] = None
    concentration: Optional[float] = None
    fund_mix: Optional[float] = None


class ComponentExplanation(BaseModel):
    """Structured explanation data for a single health score component."""

    component_name: str
    component_score: Optional[float] = None
    component_weight: Optional[float] = None
    inputs: dict[str, Any] = {}
    intermediate_scores: dict[str, Any] = {}
    calculation_details: list[str] = []
    summary_text: Optional[str] = None


class HealthScoreExplanation(BaseModel):
    """Complete explanation data for the Portfolio Health Score."""

    overall_score: Optional[float] = None
    overall_weight_details: list[str] = []
    total_weighted_contribution: float = 0.0
    components: dict[str, ComponentExplanation] = {}
    confidence_explanation: dict[str, Any] = {}
    raw_metrics_available: dict[str, bool] = {}


class HealthScoreData(BaseModel):
    score: Optional[float] = None
    confidence: HealthConfidence
    components: HealthScoreComponents
    component_weights: dict[str, float]
    available_components: list[str] = []
    single_fund_portfolio: bool = False
    has_legacy_scheme: bool = False
    score_withheld: bool = False
    withholding_reason: Optional[str] = None
    # Phase 3B: Structured explanation data for UI explainability
    explanation: Optional[HealthScoreExplanation] = None


# Resolve the forward reference from PortfolioAnalysisResult.health_score.
PortfolioAnalysisResult.model_rebuild()
