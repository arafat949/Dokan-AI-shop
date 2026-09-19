"""Dokan web server.

Run with:  python app.py   then open http://127.0.0.1:5000
"""

import re

from flask import Flask, jsonify, request, send_from_directory

import ai_agent
import config
import payments
import store
from payments import PaymentError
from store import StoreError

app = Flask(__name__, static_folder="static", static_url_path="/static")


def session_id():
    """Each browser sends a random ID so every visitor gets their own cart and chat."""
    raw = request.headers.get("X-Session-Id", "")
    return re.sub(r"[^A-Za-z0-9_-]", "", raw)[:64] or "anonymous"


def error(message, status=400, **extra):
    return jsonify({"error": message, **extra}), status


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ---------------------------------------------------------------------------
# Catalog + config
# ---------------------------------------------------------------------------
@app.get("/api/config")
def get_config():
    return jsonify({
        "ai_enabled": ai_agent.ai_enabled(),
        "model": config.ANTHROPIC_MODEL if ai_agent.ai_enabled() else None,
        "payment_methods": payments.METHODS,
    })


@app.get("/api/products")
def get_products():
    return jsonify({"products": store.list_products(), "categories": store.categories()})


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------
@app.get("/api/cart")
def get_cart():
    return jsonify(store.get_cart(session_id()))


@app.post("/api/cart/items")
def cart_add():
    data = request.get_json(silent=True) or {}
    try:
        product = store.add_to_cart(session_id(), int(data.get("product_id", 0)), data.get("quantity", 1))
    except (StoreError, ValueError) as e:
        return error(str(e) or "Invalid request.", 409)
    return jsonify({"added": product["name"], "cart": store.get_cart(session_id())})


@app.patch("/api/cart/items/<int:product_id>")
def cart_update(product_id):
    data = request.get_json(silent=True) or {}
    try:
        store.set_cart_quantity(session_id(), product_id, data.get("quantity", 1))
    except (StoreError, ValueError) as e:
        return error(str(e) or "Invalid request.", 409)
    return jsonify(store.get_cart(session_id()))


@app.delete("/api/cart/items/<int:product_id>")
def cart_remove(product_id):
    try:
        store.remove_from_cart(session_id(), product_id)
    except StoreError as e:
        return error(str(e), 404)
    return jsonify(store.get_cart(session_id()))


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return error("Please type a message.")
    if len(message) > 1000:
        return error("That message is too long. Please keep it under 1000 characters.")

    sid = session_id()
    result = ai_agent.chat(sid, message)
    result["cart"] = store.get_cart(sid)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Payment (demo)
# ---------------------------------------------------------------------------
@app.post("/api/pay")
def pay():
    sid = session_id()
    payload = request.get_json(silent=True) or {}

    if not store.get_cart(sid)["items"]:
        return error("Your cart is empty.", 409)

    try:
        method, account_hint = payments.validate(payload)
    except PaymentError as e:
        return error(str(e), 400, field=e.field)

    try:
        order = store.place_order(sid, method, account_hint, payments.new_transaction_id())
    except StoreError as e:
        return error(str(e), 409)

    items = ", ".join(f'{i["qty"]} x {i["name"]}' for i in order["items"])
    ai_agent.record_event(
        sid,
        f'Payment completed via {payments.METHODS[method]}. Order {order["order_id"]} is confirmed: '
        f'{items}. Total {order["total"]} BDT. The cart is now empty.',
    )
    return jsonify({
        "order": order,
        "method_label": payments.METHODS[method],
        "cart": store.get_cart(sid),
    })


@app.errorhandler(404)
def not_found(_):
    if request.path.startswith("/api/"):
        return error("Not found.", 404)
    return "Page not found", 404


if __name__ == "__main__":
    mode = f"Claude AI ({config.ANTHROPIC_MODEL})" if ai_agent.ai_enabled() else "basic mode (no ANTHROPIC_API_KEY set)"
    print(f"\n  Dokan is running in {mode}")
    print(f"  Open http://{config.HOST}:{config.PORT}\n")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
