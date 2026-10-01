import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.agent.custom_agent import get_price_history_tool, search_products_tool
from app.main import app
from app.database.session import Base
from app.models import PriceHistory, Product, TrackedProduct, User
from app.models.conversation import Conversation, Message  # noqa: F401
from app.scrapers.base import ScrapedProduct
from app.scrapers.book_scraper import BookToScrapeScraper
from app.scrapers.factory import ScraperFactory
from app.services.product_service import ProductService


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_book_scraper_parses_product():
    html = """
    <div class="product_main"><h1>Sample Book</h1>
      <p class="price_color">£12.50</p>
      <p class="availability">In stock</p></div>
    <div id="product_gallery"><img src="../../media/cover.jpg"></div>
    """
    item = BookToScrapeScraper().parse(
        html, "https://books.toscrape.com/catalogue/sample/index.html"
    )
    assert item.name == "Sample Book"
    assert item.price == 12.5
    assert item.currency == "GBP"
    assert item.availability == "In Stock"
    assert item.image_url == "https://books.toscrape.com/media/cover.jpg"


def test_dashboard_and_health_routes():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "healthy"}
    assert "PriceSage AI" in client.get("/").text


def test_tracking_reuses_product_and_scopes_agent_data(db, monkeypatch):
    users = [
        User(name="A", email="a@example.com", password_hash="unused"),
        User(name="B", email="b@example.com", password_hash="unused"),
    ]
    db.add_all(users)
    db.commit()

    scrape_calls = []

    def scrape(url):
        scrape_calls.append(url)
        return ScrapedProduct(name="Sample Book", price=12.5, currency="GBP")

    monkeypatch.setattr(
        ScraperFactory, "get_scraper", lambda url: SimpleNamespace(scrape=scrape)
    )
    url = "https://books.toscrape.com/catalogue/sample/index.html"
    first = ProductService.track_product(db, users[0].id, url, 10.0)
    second = ProductService.track_product(db, users[1].id, url, 11.0)

    assert first.product_id == second.product_id
    assert scrape_calls == [url]
    assert db.query(Product).count() == 1
    assert db.query(PriceHistory).count() == 1
    assert db.query(TrackedProduct).count() == 2

    assert "Sample Book" in search_products_tool(db, users[0].id, "Sample")
    history = json.loads(get_price_history_tool(db, users[1].id, first.product_id))
    assert history["lowest"] == 12.5
    assert len(history["history"]) == 1

    db.delete(second)
    db.commit()
    assert "not in your tracking list" in get_price_history_tool(db, users[1].id, first.product_id)
