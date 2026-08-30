from pydantic import BaseModel
from typing import Optional


class Holding(BaseModel):
    symbol: str
    name: Optional[str] = None
    quantity: Optional[float] = None
    average_price: Optional[float] = None
    current_price: Optional[float] = None
    invested_value: Optional[float] = None
    current_value: Optional[float] = None
    portfolio_weight: Optional[float] = None
