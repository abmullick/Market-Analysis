from pydantic import BaseModel
from typing import Optional


class Stock(BaseModel):
    symbol: str
    name: str
    exchange: str
    isin: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
