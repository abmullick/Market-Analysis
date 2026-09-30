from pydantic import BaseModel, Field
from typing import Optional


class Fundamentals(BaseModel):
    symbol: str
    name: Optional[str] = None
    exchange: Optional[str] = None
    currency: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None

    market_cap: Optional[float] = None
    enterprise_value: Optional[float] = None
    shares_outstanding: Optional[float] = None
    price: Optional[float] = None
    beta: Optional[float] = None

    pe: Optional[float] = None
    forward_pe: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    peg: Optional[float] = None
    ev_ebitda: Optional[float] = None
    ev_revenue: Optional[float] = None

    roe: Optional[float] = None
    roce: Optional[float] = None
    roa: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    profit_margin: Optional[float] = None

    debt_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    cash: Optional[float] = None
    total_debt: Optional[float] = None

    revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_profit: Optional[float] = None
    ebitda: Optional[float] = None
    net_profit: Optional[float] = None
    eps: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    capital_expenditure: Optional[float] = None
    free_cash_flow: Optional[float] = None

    revenue_growth: Optional[float] = None
    profit_growth: Optional[float] = None
    eps_growth: Optional[float] = None
    revenue_cagr_3y: Optional[float] = None
    revenue_cagr_5y: Optional[float] = None
    profit_cagr_3y: Optional[float] = None
    profit_cagr_5y: Optional[float] = None
    eps_cagr_3y: Optional[float] = None
    eps_cagr_5y: Optional[float] = None
    fcf_cagr_3y: Optional[float] = None
    fcf_cagr_5y: Optional[float] = None
    operating_margin_change: Optional[float] = None

    dividend_yield: Optional[float] = None
    payout_ratio: Optional[float] = None
    promoter_holding: Optional[float] = None
    fii_holding: Optional[float] = None
    dii_holding: Optional[float] = None

    data_as_of: Optional[str] = None
    source: str = "Yahoo Finance"


class FinancialPeriod(BaseModel):
    period: str
    values: dict[str, Optional[float]]


class StockAnalysis(BaseModel):
    fundamentals: Fundamentals
    income_statement: list[FinancialPeriod] = Field(default_factory=list)
    balance_sheet: list[FinancialPeriod] = Field(default_factory=list)
    cash_flow: list[FinancialPeriod] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
