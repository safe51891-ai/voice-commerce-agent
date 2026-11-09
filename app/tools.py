"""Tools the voice agent can call. All data is synthetic and loaded from data/.

Privacy rules are enforced here, not left to the model:
- Order details are returned only when both the order number and the email match.
- Leads are saved only when the caller has explicitly agreed.
"""
import re
from datetime import date

from .data import load

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

LEADS: list[dict] = []


def _public_product(product: dict) -> dict:
    return {
        "sku": product["sku"],
        "name": product["name"],
        "price": product["price"],
        "in_stock": product["stock"] > 0,
    }


def search_products(query: str, max_price: float | None = None) -> dict:
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2]
    matches = []
    for product in load("catalog.json"):
        haystack = " ".join([product["name"], product["category"], *product["tags"]]).lower()
        score = sum(1 for word in words if word in haystack)
        if words and score == 0:
            continue
        if max_price is not None and product["price"] > max_price:
            continue
        matches.append((score, product))
    matches.sort(key=lambda item: (-item[0], item[1]["price"]))
    return {"products": [_public_product(p) for _, p in matches[:5]]}


def recommend_products(category: str | None = None, max_price: float | None = None) -> dict:
    picks = []
    for product in load("catalog.json"):
        if product["stock"] <= 0:
            continue
        if category and product["category"] != category.lower():
            continue
        if max_price is not None and product["price"] > max_price:
            continue
        picks.append(product)
    picks.sort(key=lambda p: -p["rating"])
    return {"products": [_public_product(p) for p in picks[:3]]}


def get_order_status(order_id: str, email: str) -> dict:
    order = next((o for o in load("orders.json") if o["order_id"] == order_id.strip().upper()), None)
    if order is None or order["email"] != email.strip().lower():
        return {"verified": False, "message": "I could not verify that order number and email together."}
    return {
        "verified": True,
        "status": order["status"],
        "items": order["items"],
        "estimated_delivery": order["eta"],
    }


def get_promotions(today: str | None = None) -> dict:
    current = date.fromisoformat(today) if today else date.today()
    active = [
        {"code": p["code"], "description": p["description"], "valid_until": p["valid_until"]}
        for p in load("promotions.json")
        if date.fromisoformat(p["valid_until"]) >= current
    ]
    return {"promotions": active}


def save_lead(name: str, email: str, interest: str, consent: bool) -> dict:
    if not consent:
        return {"saved": False, "reason": "The caller has not agreed to be contacted."}
    if not EMAIL_RE.match(email.strip()):
        return {"saved": False, "reason": "That email address does not look valid."}
    LEADS.append({"name": name.strip(), "email": email.strip().lower(), "interest": interest.strip()})
    return {"saved": True}


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search the catalog by keywords. Returns name, price and whether it is in stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keywords from the customer's request"},
                    "max_price": {"type": "number", "description": "Optional maximum price in dollars"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_products",
            "description": "Suggest in-stock products, best rated first, optionally by category or budget.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["footwear", "outerwear", "bags", "accessories", "apparel"]},
                    "max_price": {"type": "number"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Look up an order. Requires BOTH the order number and the email used to place it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order number such as NW-1001"},
                    "email": {"type": "string"},
                },
                "required": ["order_id", "email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_promotions",
            "description": "List the current promotions. Only mention offers this returns.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_lead",
            "description": "Save a marketing lead. Set consent to true ONLY if the caller clearly agreed to be contacted.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "interest": {"type": "string", "description": "What the caller is interested in"},
                    "consent": {"type": "boolean"},
                },
                "required": ["name", "email", "interest", "consent"],
            },
        },
    },
]

DISPATCH = {
    "search_products": search_products,
    "recommend_products": recommend_products,
    "get_order_status": get_order_status,
    "get_promotions": get_promotions,
    "save_lead": save_lead,
}
