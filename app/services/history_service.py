from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.product import Product, PriceHistory
from app.schemas.history import PriceHistoryStats, PricePoint


class HistoryService:
    @staticmethod
    def get_product_price_history(db: Session, product_id: int) -> PriceHistoryStats:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {product_id} not found."
            )

        # Retrieve chronological points (earliest to latest for clean chart rendering)
        records = (
            db.query(PriceHistory)
            .filter(PriceHistory.product_id == product_id)
            .order_by(PriceHistory.recorded_at.asc())
            .all()
        )

        if not records:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No price history recorded for this product."
            )

        prices = [r.price for r in records]
        current_price = product.current_price
        lowest_price = min(prices)
        highest_price = max(prices)

        # Determine previous price
        if len(records) > 1:
            previous_price = records[-2].price
            percentage_change = round(((current_price - previous_price) / previous_price) * 100, 2)
        else:
            previous_price = current_price
            percentage_change = 0.0

        history_points = [
            PricePoint(price=r.price, recorded_at=r.recorded_at) for r in records
        ]

        return PriceHistoryStats(
            product_id=product.id,
            product_name=product.name,
            currency=product.currency,
            current_price=current_price,
            previous_price=previous_price,
            lowest_price=lowest_price,
            highest_price=highest_price,
            percentage_change=percentage_change,
            history=history_points,
        )
