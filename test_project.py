import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.agent.custom_agent import get_price_history_tool, search_products_tool
from app.api import agent as agent_api
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


def test_agent_returns_a_final_answer_after_multiple_tools(db, monkeypatch):
    user = User(name="A", email="a@example.com", password_hash="unused")
    product = Product(
        name="Sample Book",
        url="https://books.toscrape.com/sample",
        current_price=12.5,
        currency="GBP",
        availability=True,
    )
    db.add_all([user, product])
    db.flush()
    db.add_all([
        TrackedProduct(user_id=user.id, product_id=product.id, target_price=10.0),
        PriceHistory(product_id=product.id, price=12.5),
    ])
    db.commit()

    def tool_call(call_id, name, arguments):
        return SimpleNamespace(
            id=call_id,
            function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
        )

    replies = iter([
        SimpleNamespace(content=None, tool_calls=[
            tool_call("call-1", "get_tracked_products", {}),
            tool_call("call-2", "get_price_history", {"product_id": product.id}),
        ]),
        SimpleNamespace(content="Sample Book is £12.50; its recorded low is £12.50.", tool_calls=None),
    ])
    requests = []

    def create(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=next(replies))])

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(agent_api, "Groq", lambda api_key: fake_client)
    monkeypatch.setattr(agent_api.settings, "GROQ_API_KEY", "test-key")

    result = agent_api.chat_with_agent(
        agent_api.ChatRequest(message="What is my book's price history?"), db, user
    )

    assert result["response"] == "Sample Book is £12.50; its recorded low is £12.50."
    assert result["tools_used"] == ["get_tracked_products", "get_price_history"]
    assert result["data"] is None
    assert len(result["tool_results"]) == 2
    tool_messages = [message for message in requests[1]["messages"] if message["role"] == "tool"]
    assert [message["tool_call_id"] for message in tool_messages] == ["call-1", "call-2"]
    assert "12.5" in tool_messages[1]["content"]
    assert [message.role for message in db.query(Message).order_by(Message.id)] == ["user", "assistant"]


def test_agent_continuation_is_scoped_to_conversation_owner(db, monkeypatch):
    owner = User(name="A", email="a@example.com", password_hash="unused")
    other = User(name="B", email="b@example.com", password_hash="unused")
    db.add_all([owner, other])
    db.commit()
    requests = []

    def create(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content="Answer", tool_calls=None
        ))])

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(agent_api, "Groq", lambda api_key: fake_client)
    monkeypatch.setattr(agent_api.settings, "GROQ_API_KEY", "test-key")

    first = agent_api.chat_with_agent(agent_api.ChatRequest(message="First question"), db, owner)
    agent_api.chat_with_agent(
        agent_api.ChatRequest(message="Follow up", conversation_id=first["conversation_id"]),
        db,
        owner,
    )
    history = requests[1]["messages"]
    assert [entry["content"] for entry in history[-3:]] == [
        "First question", "Answer", "Follow up"
    ]

    with pytest.raises(HTTPException) as error:
        agent_api.chat_with_agent(
            agent_api.ChatRequest(message="Read someone else's chat", conversation_id=first["conversation_id"]),
            db,
            other,
        )
    assert error.value.status_code == 404
    assert len(requests) == 2
