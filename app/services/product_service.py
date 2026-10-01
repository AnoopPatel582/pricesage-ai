from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.product import Product, PriceHistory, TrackedProduct
from app.models.user import User
from app.scrapers.factory import ScraperFactory


class ProductService:
    @staticmethod
    def get_or_create_product(db: Session, url: str) -> Product:
        """Find an existing product by URL or scrape and create it."""
        product = db.query(Product).filter(Product.url == url).first()
        if product:
            return product

        # Dispatch domain-appropriate scraper
        scraper = ScraperFactory.get_scraper(url)
        scraped_data = scraper.scrape(url)

        # Instantiate Product directly instead of calling get_or_create recursively
        product = Product(
            name=scraped_data.name,
            current_price=scraped_data.price,
            currency=scraped_data.currency,
            availability=True if scraped_data.availability == "In Stock" else False,
            image_url=scraped_data.image_url,
            url=url,
        )
        db.add(product)
        db.commit()
        db.refresh(product)

        # Seed initial price history
        history_entry = PriceHistory(product_id=product.id, price=scraped_data.price)
        db.add(history_entry)
        db.commit()

        return product

    @staticmethod
    def track_product(db: Session, user_id: int, url: str, target_price: float) -> TrackedProduct:
        product = ProductService.get_or_create_product(db, url)

        # Check if user already tracks this product
        existing_track = (
            db.query(TrackedProduct)
            .filter(TrackedProduct.user_id == user_id, TrackedProduct.product_id == product.id)
            .first()
        )
        if existing_track:
            existing_track.target_price = target_price
            existing_track.is_alert_active = True
            db.commit()
            db.refresh(existing_track)
            return existing_track

        tracked = TrackedProduct(
            user_id=user_id,
            product_id=product.id,
            target_price=target_price,
            is_alert_active=True,
        )
        db.add(tracked)
        db.commit()
        db.refresh(tracked)
        return tracked
