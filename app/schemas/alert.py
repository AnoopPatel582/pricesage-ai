from datetime import datetime
from pydantic import BaseModel


class AlertResponse(BaseModel):
    product_id: int
    product_name: str
    product_url: str
    image_url: str | None = None
    currency: str
    current_price: float
    target_price: float
    savings: float
    triggered_at: datetime
