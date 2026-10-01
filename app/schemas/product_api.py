from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ProductCreateRequest(BaseModel):
    url: str = Field(..., description="Full URL of the product to track")
    target_price: float = Field(..., gt=0, description="Desired alert threshold price")


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    url: str
    image_url: Optional[str] = None
    current_price: float
    currency: str
    availability: bool
    created_at: datetime
    updated_at: datetime



class TrackedProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    product_id: int
    target_price: float
    is_alert_active: bool
    created_at: datetime
    product: ProductResponse
