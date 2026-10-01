import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.database.session import SessionLocal
from app.models.product import Product, PriceHistory, TrackedProduct
from app.scrapers.factory import ScraperFactory
from app.scrapers.exceptions import ScraperException
from app.services.alert_service import AlertService
logger = logging.getLogger("price_tracker.tracker")


class TrackerService:
    @staticmethod
    def check_all_tracked_products():
        """Periodically scans tracked products, updates prices, and evaluates alerts."""
        logger.info("Scheduler triggered: Starting price check cycle...")
        db: Session = SessionLocal()

        try:
            products = (
                db.query(Product)
                .join(TrackedProduct, Product.id == TrackedProduct.product_id)
                .distinct()
                .all()
            )

            if not products:
                logger.info("No tracked products found. Cycle skipped.")
                return

            for product in products:
                TrackerService._update_single_product(db, product)

            db.commit()
            logger.info("Scheduler completed: Price check cycle finished.")
        except Exception as exc:
            db.rollback()
            logger.error(f"Error during scheduled price check cycle: {exc}", exc_info=True)
        finally:
            db.close()

    @staticmethod
    def _update_single_product(db: Session, product: Product):
        try:
            logger.info(f"Scanning latest price for: {product.name} (ID: {product.id})")
            scraper = ScraperFactory.get_scraper(product.url)
            scraped = scraper.scrape(product.url)

            old_price = product.current_price
            new_price = scraped.price

            # Record history
            history_record = PriceHistory(
                product_id=product.id,
                price=new_price,
                recorded_at=datetime.now(timezone.utc),
            )
            db.add(history_record)

            # Update product attributes
            product.current_price = new_price
            product.availability = scraped.availability == "In Stock"
            product.updated_at = datetime.now(timezone.utc)

            if new_price != old_price:
                logger.info(
                    f"Price changed for '{product.name}': {old_price} -> {new_price} {product.currency}"
                )
            else:
                logger.info(f"Price unchanged for '{product.name}' ({new_price} {product.currency})")

            # Check and trigger alerts
            AlertService.evaluate_product_alerts(db, product)

        except ScraperException as scrape_err:
            logger.warning(f"Failed to scrape product ID {product.id}: {scrape_err}")
        except Exception as e:
            logger.error(f"Unexpected error checking product ID {product.id}: {e}")
