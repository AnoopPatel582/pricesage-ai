from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class PricePoint(BaseModel):
    price: float
    recorded_at: datetime

    class Config:
        from_attributes = True


class PriceHistoryStats(BaseModel):
    product_id: int
    product_name: str
    currency: str
    current_price: float
    previous_price: Optional[float] = None
    lowest_price: float
    highest_price: float
    percentage_change: float
    history: List[PricePoint]
