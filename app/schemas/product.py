from pydantic import BaseModel, HttpUrl
from typing import Optional


class ScrapedProduct(BaseModel):
    title: str
    price: float
    currency: str
    image_url: Optional[str] = None
    availability: bool
    source_url: str
