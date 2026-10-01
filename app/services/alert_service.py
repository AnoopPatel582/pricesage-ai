import logging
from datetime import datetime, timezone
from typing import List
from sqlalchemy.orm import Session
from app.models.product import Product, TrackedProduct
from app.schemas.alert import AlertResponse
from app.notifications.email_service import EmailService

logger = logging.getLogger("price_tracker.alerts")


class AlertService:
    @staticmethod
    def evaluate_product_alerts(db: Session, product: Product) -> List[dict]:
        """Check all users tracking this product and dispatch alerts."""
        triggered_alerts = []

        tracks = (
            db.query(TrackedProduct)
            .filter(
                TrackedProduct.product_id == product.id,
            )
            .all()
        )

        for track in tracks:
            if product.current_price <= track.target_price:
                savings = round(track.target_price - product.current_price, 2)
                logger.info(
                    f"ALERT TRIGGERED: '{product.name}' is {product.current_price} {product.currency} "
                    f"(Target: {track.target_price})"
                )

                # Send email notification
                user = track.user
                if user and user.email:
                    sent = EmailService.send_price_drop_alert(
                        to_email=user.email,
                        user_name=user.name,
                        product_name=product.name,
                        current_price=product.current_price,
                        target_price=track.target_price,
                        currency=product.currency,
                        product_url=product.url,
                    )

                # Deactivate alert to avoid duplicate messages on future scheduler cycles
                if not user or not user.email or sent:
                    track.is_alert_active = False

                triggered_alerts.append({
                    "user": user,
                    "product": product,
                    "target_price": track.target_price,
                    "current_price": product.current_price,
                    "savings": savings,
                })

            elif product.current_price > track.target_price and not track.is_alert_active:
                # Reset alert eligibility if the price climbs back up
                track.is_alert_active = True
                logger.info(f"Alert reset for '{product.name}' (price rebounded)")

        return triggered_alerts

    @staticmethod
    def get_user_alerts(db: Session, user_id: int) -> List[AlertResponse]:
        """List active deals where current price is at or below target."""
        triggered_tracks = (
            db.query(TrackedProduct)
            .join(Product, TrackedProduct.product_id == Product.id)
            .filter(
                TrackedProduct.user_id == user_id,
                Product.current_price <= TrackedProduct.target_price,
            )
            .all()
        )

        results = []
        for track in triggered_tracks:
            p = track.product
            results.append(
                AlertResponse(
                    product_id=p.id,
                    product_name=p.name,
                    product_url=p.url,
                    image_url=p.image_url,
                    currency=p.currency,
                    current_price=p.current_price,
                    target_price=track.target_price,
                    savings=round(track.target_price - p.current_price, 2),
                    triggered_at=p.updated_at or datetime.now(timezone.utc),
                )
            )
        return results
