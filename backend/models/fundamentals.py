from pydantic import BaseModel
from typing import Optional


class Fundamentals(BaseModel):
    symbol: str
    market_cap: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    peg: Optional[float] = None
    roe: Optional[float] = None
    roce: Optional[float] = None
    roa: Optional[float] = None
    ev_ebitda: Optional[float] = None
    debt_equity: Optional[float] = None
    revenue: Optional[float] = None
    operating_profit: Optional[float] = None
    net_profit: Optional[float] = None
    eps: Optional[float] = None
    free_cash_flow: Optional[float] = None
    revenue_growth: Optional[float] = None
    profit_growth: Optional[float] = None
    eps_growth: Optional[float] = None
    promoter_holding: Optional[float] = None
    fii_holding: Optional[float] = None
    dii_holding: Optional[float] = None
