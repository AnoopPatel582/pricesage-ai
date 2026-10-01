from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.product import Product, TrackedProduct
from app.models.user import User
from app.schemas.history import PriceHistoryStats
from app.schemas.product_api import (
    ProductCreateRequest,
    ProductResponse,
    TrackedProductResponse,
)
from app.schemas.alert import AlertResponse
from app.scrapers.exceptions import ScraperException
from app.services.product_service import ProductService
from app.services.alert_service import AlertService
from app.services.history_service import HistoryService
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("/{product_id}/history", response_model=PriceHistoryStats)
def get_product_price_history(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    track = db.query(TrackedProduct).filter_by(user_id=current_user.id, product_id=product_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Tracked product not found")
    return HistoryService.get_product_price_history(db, product_id)


@router.post("/", response_model=TrackedProductResponse, status_code=status.HTTP_201_CREATED)
def add_and_track_product(
    payload: ProductCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Scrapes a URL and tracks it specifically for the authenticated user with scraper error handling."""
    try:
        return ProductService.track_product(
            db=db,
            user_id=current_user.id,
            url=payload.url,
            target_price=payload.target_price,
        )
    except ScraperException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during scraping: {exc}"
        )



@router.get("/", response_model=List[TrackedProductResponse])
def list_tracked_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns products tracked exclusively by the authenticated user."""
    return (
        db.query(TrackedProduct)
        .filter(TrackedProduct.user_id == current_user.id)
        .all()
    )


@router.get("/alerts", response_model=List[AlertResponse], tags=["Alerts"])
def list_active_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch active alerts triggered for the authenticated user."""
    return AlertService.get_user_alerts(db=db, user_id=current_user.id)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch product details by ID."""
    product = (
        db.query(Product)
        .join(TrackedProduct, TrackedProduct.product_id == Product.id)
        .filter(Product.id == product_id, TrackedProduct.user_id == current_user.id)
        .first()
    )
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found",
        )
    return product


@router.delete("/{product_id}/track", status_code=status.HTTP_204_NO_CONTENT)
def untrack_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a product from the authenticated user's tracking list."""
    track = (
        db.query(TrackedProduct)
        .filter(
            TrackedProduct.user_id == current_user.id,
            TrackedProduct.product_id == product_id,
        )
        .first()
    )
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracked product record not found for this user",
        )
    db.delete(track)
    db.commit()
    return None
