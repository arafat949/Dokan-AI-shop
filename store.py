"""Data layer for Dokan: products, shopping carts and orders.

Products and orders are saved as JSON files in the `data/` folder, so anything
added through the chat is still there after a restart. Carts live in memory,
one per browser session.
"""

import json
import os
import random
import tempfile
import threading
from datetime import datetime

from config import ORDERS_FILE, PRODUCTS_FILE

_lock = threading.RLock()

# Icons the frontend knows how to draw (see static/js/icons.js).
VALID_ICONS = [
    "laptop", "phone", "tablet", "buds", "headphones", "speaker", "mic", "watch",
    "keyboard", "mouse", "hub", "monitor", "power", "charger", "camera",
    "gamepad", "home", "router", "storage", "box",
]

# Default icon for a product added without an explicit icon.
CATEGORY_ICONS = {
    "laptop": "laptop", "smartphone": "phone", "tablet": "tablet", "audio": "headphones",
    "watch": "watch", "accessories": "mouse", "monitor": "monitor", "power": "power",
    "camera": "camera", "gaming": "gamepad", "smart home": "home",
    "networking": "router", "storage": "storage",
}


class StoreError(Exception):
    """A problem the customer (or the AI) can understand and fix."""


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------
def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json(path, data):
    """Write atomically so a crash can never leave a half-written file."""
    directory = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


_products = _read_json(PRODUCTS_FILE, [])
_orders = _read_json(ORDERS_FILE, [])
_carts = {}  # session_id -> {product_id: quantity}


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
def list_products():
    with _lock:
        return [dict(p) for p in _products]


def get_product(product_id):
    with _lock:
        for p in _products:
            if p["id"] == product_id:
                return dict(p)
    return None


def categories():
    with _lock:
        seen = []
        for p in _products:
            if p["category"] not in seen:
                seen.append(p["category"])
        return seen


def search_products(query=None, category=None, min_price=None, max_price=None, sort_by=None):
    """Filter the catalog. `query` matches words in the name, category and specs."""
    with _lock:
        results = [dict(p) for p in _products]

    if category:
        results = [p for p in results if p["category"].lower() == category.strip().lower()]
    if min_price is not None:
        results = [p for p in results if p["price"] >= min_price]
    if max_price is not None:
        results = [p for p in results if p["price"] <= max_price]

    if query:
        words = [w for w in query.lower().split() if w]
        scored = []
        for p in results:
            haystack = f'{p["name"]} {p["category"]} {" ".join(p["specs"])}'.lower()
            score = sum(1 for w in words if w in haystack)
            if score:
                scored.append((score, p))
        scored.sort(key=lambda pair: -pair[0])
        results = [p for _, p in scored]

    if sort_by == "price_asc":
        results.sort(key=lambda p: p["price"])
    elif sort_by == "price_desc":
        results.sort(key=lambda p: -p["price"])
    elif sort_by == "rating_desc":
        results.sort(key=lambda p: -(p["rating"] or 0))
    elif sort_by == "best_value":
        results.sort(key=lambda p: -((p["rating"] or 0) / p["price"]))
    return results


def add_product(name, category, price, stock, rating=None, specs=None, icon=None):
    """Add a new product to the catalog and save it. Returns the new product."""
    name = (name or "").strip()
    category = (category or "").strip()
    if not name:
        raise StoreError("Product name is required.")
    if len(name) > 80:
        raise StoreError("Product name must be 80 characters or fewer.")
    if not category:
        raise StoreError("Category is required.")

    try:
        price = int(round(float(price)))
        stock = int(stock)
    except (TypeError, ValueError):
        raise StoreError("Price and stock must be numbers.")
    if price <= 0:
        raise StoreError("Price must be greater than zero.")
    if stock < 0:
        raise StoreError("Stock cannot be negative.")

    if rating is not None:
        try:
            rating = round(min(5.0, max(0.0, float(rating))), 1)
        except (TypeError, ValueError):
            rating = None

    specs = [str(s).strip() for s in (specs or []) if str(s).strip()][:6]

    with _lock:
        if any(p["name"].lower() == name.lower() for p in _products):
            raise StoreError(f'A product named "{name}" already exists.')

        # Reuse the spelling of an existing category if there is one.
        for p in _products:
            if p["category"].lower() == category.lower():
                category = p["category"]
                break
        else:
            category = category.title()

        if icon not in VALID_ICONS:
            icon = CATEGORY_ICONS.get(category.lower(), "box")

        product = {
            "id": max((p["id"] for p in _products), default=0) + 1,
            "name": name,
            "category": category,
            "price": price,
            "rating": rating,
            "stock": stock,
            "icon": icon,
            "specs": specs,
        }
        _products.append(product)
        _write_json(PRODUCTS_FILE, _products)
        return dict(product)


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------
def get_cart(session_id):
    """Return the cart with full product details and totals."""
    with _lock:
        cart = _carts.get(session_id, {})
        items, total, count = [], 0, 0
        for pid, qty in cart.items():
            p = next((x for x in _products if x["id"] == pid), None)
            if not p:
                continue
            line_total = p["price"] * qty
            items.append({
                "id": p["id"], "name": p["name"], "category": p["category"],
                "icon": p["icon"], "image": p.get("image"), "price": p["price"], "qty": qty,
                "line_total": line_total, "stock": p["stock"],
            })
            total += line_total
            count += qty
        return {"items": items, "total": total, "count": count}


def add_to_cart(session_id, product_id, quantity=1):
    quantity = int(quantity or 1)
    if quantity < 1:
        raise StoreError("Quantity must be at least 1.")
    with _lock:
        product = get_product(product_id)
        if not product:
            raise StoreError("Product not found.")
        cart = _carts.setdefault(session_id, {})
        new_qty = cart.get(product_id, 0) + quantity
        if new_qty > product["stock"]:
            left = product["stock"] - cart.get(product_id, 0)
            raise StoreError(
                f'Not enough stock for {product["name"]}. Only {max(left, 0)} more available.'
            )
        cart[product_id] = new_qty
        return product


def set_cart_quantity(session_id, product_id, quantity):
    quantity = int(quantity)
    with _lock:
        product = get_product(product_id)
        if not product:
            raise StoreError("Product not found.")
        cart = _carts.setdefault(session_id, {})
        if quantity <= 0:
            cart.pop(product_id, None)
        else:
            cart[product_id] = min(quantity, product["stock"])


def remove_from_cart(session_id, product_id):
    with _lock:
        cart = _carts.get(session_id, {})
        if product_id not in cart:
            raise StoreError("That product is not in the cart.")
        del cart[product_id]


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
def place_order(session_id, method, account_hint, transaction_id):
    """Turn the cart into a paid order: reduce stock, clear the cart, save it."""
    with _lock:
        cart = get_cart(session_id)
        if not cart["items"]:
            raise StoreError("Your cart is empty.")

        # Check stock again right before taking it.
        for item in cart["items"]:
            product = next(p for p in _products if p["id"] == item["id"])
            if product["stock"] < item["qty"]:
                raise StoreError(
                    f'Sorry, {product["name"]} just went low on stock '
                    f'({product["stock"]} left). Please update your cart.'
                )

        for item in cart["items"]:
            product = next(p for p in _products if p["id"] == item["id"])
            product["stock"] -= item["qty"]

        existing_ids = {o["order_id"] for o in _orders}
        order_id = f"DK{random.randint(10000, 99999)}"
        while order_id in existing_ids:
            order_id = f"DK{random.randint(10000, 99999)}"

        order = {
            "order_id": order_id,
            "transaction_id": transaction_id,
            "payment_method": method,
            "account": account_hint,  # masked, never the full number
            "items": [
                {"id": i["id"], "name": i["name"], "qty": i["qty"], "price": i["price"]}
                for i in cart["items"]
            ],
            "total": cart["total"],
            "status": "Confirmed",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        _orders.append(order)
        _carts[session_id] = {}
        _write_json(PRODUCTS_FILE, _products)
        _write_json(ORDERS_FILE, _orders)
        return order
