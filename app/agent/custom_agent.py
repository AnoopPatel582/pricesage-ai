import json
import logging
from typing import Callable, Dict, Any
from sqlalchemy.orm import Session
from app.models.product import Product, PriceHistory, TrackedProduct

from app.services.product_service import ProductService

logger = logging.getLogger("price_tracker.agent")

class CustomAgentRegistry:
    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.openai_tools = []

    def register(self, name: str, func: Callable, description: str, parameters: dict):
        self.tools[name] = {"function": func, "description": description}
        self.openai_tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters
            }
        })

agent_registry = CustomAgentRegistry()

# --- Tool Definitions ---

def search_products_tool(db: Session, user_id: int, query: str = "") -> str:
    db_query = db.query(Product).join(TrackedProduct).filter(TrackedProduct.user_id == user_id)
    if query:
        db_query = db_query.filter(Product.name.ilike(f"%{query}%"))
    products = db_query.all()
    results = [{"id": p.id, "name": p.name, "price": p.current_price, "currency": p.currency, "url": p.url} for p in products]
    return json.dumps(results, indent=2)

agent_registry.register(
    name="search_products",
    func=search_products_tool,
    description="Search real products in the database by query string.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "The search keyword like laptop, phone, mouse"}},
        "required": ["query"]
    }
)

def get_tracked_products_tool(db: Session, user_id: int) -> str:
    tracked_items = db.query(TrackedProduct).filter(TrackedProduct.user_id == user_id).all()
    if not tracked_items:
        return json.dumps({"message": "You are not tracking any products currently."})
    results = []
    for item in tracked_items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        results.append({
            "product_name": product.name if product else "Unknown",
            "current_price": product.current_price if product else None,
            "target_price": item.target_price
        })
    return json.dumps(results, indent=2)

agent_registry.register(
    name="get_tracked_products",
    func=get_tracked_products_tool,
    description="Retrieve all products tracked by the current user.",
    parameters={"type": "object", "properties": {}}
)

def track_product_tool(db: Session, user_id: int, url: str, target_price: float = 500.0) -> str:
    try:
        tracked = ProductService.track_product(db=db, user_id=user_id, url=url, target_price=target_price)
        return json.dumps({"success": True, "message": f"Successfully tracking product ID {tracked.product_id} with target ₹{target_price}"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

agent_registry.register(
    name="track_product",
    func=track_product_tool,
    description="Track an e-commerce URL with a specified target price.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The product URL to track"},
            "target_price": {"type": "number", "description": "The target price threshold"}
        },
        "required": ["url"]
    }
)

def get_price_history_tool(db: Session, user_id: int, product_id: int) -> str:
    tracked = db.query(TrackedProduct).filter_by(user_id=user_id, product_id=product_id).first()
    if not tracked:
        return json.dumps({"error": "Product is not in your tracking list."})
    history = db.query(PriceHistory).filter(PriceHistory.product_id == product_id).all()
    if not history:
        return json.dumps({"message": "No price history found."})
    prices = [h.price for h in history]
    return json.dumps({
        "product_id": product_id,
        "lowest": min(prices),
        "highest": max(prices),
        "average": round(sum(prices) / len(prices), 2),
        "history": [{"price": h.price, "timestamp": str(h.recorded_at)} for h in history]
    }, indent=2)

agent_registry.register(
    name="get_price_history",
    func=get_price_history_tool,
    description="Retrieve price history and statistical trends for a product ID.",
    parameters={
        "type": "object",
        "properties": {"product_id": {"type": "integer", "description": "The product ID"}},
        "required": ["product_id"]
    }
)
