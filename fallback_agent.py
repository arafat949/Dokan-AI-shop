"""Basic-mode assistant: understands a set of simple commands with plain rules.

It is used when no ANTHROPIC_API_KEY is set (or the AI service is down), so the
shop always works. It calls the same tools as the Claude assistant.
"""

import re

import store
from tools import execute_tool

STOP_WORDS = {
    "add", "to", "the", "a", "an", "my", "cart", "basket", "please", "buy", "order", "i", "want",
    "need", "get", "me", "and", "of", "for", "in", "it", "one", "two", "three", "pcs", "piece",
    "pieces", "x", "from", "remove", "delete", "take", "purchase", "now", "some", "can", "you",
    "could", "would", "like", "put", "into", "with", "under", "below", "above", "over", "than",
    "less", "more", "best", "good", "show", "find", "give", "is", "are", "what", "which", "how",
    "much", "do", "have", "any", "tk", "taka", "bdt", "on", "at", "up", "also", "this", "that",
}

# Broad words that map to a whole category.
CATEGORY_WORDS = {
    "laptop": "Laptop", "laptops": "Laptop", "notebook": "Laptop",
    "phone": "Smartphone", "phones": "Smartphone", "smartphone": "Smartphone",
    "smartphones": "Smartphone", "mobile": "Smartphone", "mobiles": "Smartphone",
    "tablet": "Tablet", "tablets": "Tablet",
    "audio": "Audio", "watch": "Watch", "watches": "Watch", "smartwatch": "Watch",
    "accessories": "Accessories",
    "monitor": "Monitor", "monitors": "Monitor", "camera": "Camera", "cameras": "Camera",
    "gaming": "Gaming", "networking": "Networking", "storage": "Storage",
}

# Specific words that map to a keyword search.
KEYWORD_ALIASES = {
    "earbuds": "buds", "earbud": "buds", "earphones": "buds", "buds": "buds",
    "headphones": "headphones", "headphone": "headphones", "headset": "headset",
    "speaker": "speaker", "speakers": "speaker", "mic": "mic", "microphone": "mic",
    "keyboard": "keyboard", "keyboards": "keyboard", "mouse": "mouse",
    "charger": "charger", "chargers": "charger", "powerbank": "voltpack",
    "ssd": "ssd", "pendrive": "flash", "router": "router", "wifi": "router",
    "controller": "controller", "gamepad": "controller", "bulb": "bulb", "security": "security",
    "hub": "hub", "stand": "stand",
}

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}

HELP = (
    "I'm running in basic mode (no AI key set), so I understand simple commands:\n"
    "- \"best phone under 40000\" or \"show laptops\"\n"
    "- \"add PulseBuds Pro to cart\" (add \"2x\" for more than one)\n"
    "- \"show my cart\" and \"remove PulseBuds Pro\"\n"
    "- \"checkout\" to open the payment window\n"
    "- \"add product: Name, Category, Price, Stock\" to add a product to the store"
)


def _tokens(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _money(n):
    return f"৳{int(n):,}"


def _rating(p):
    return f"★ {p['rating']}" if p.get("rating") else "New"


def _match_products(text, pool):
    """Find the product(s) in `pool` that the message is most likely talking about.

    Returns every product tied for the most matching name words, so a message like
    "add apple" (an iPhone and a MacBook) comes back with two products and we can ask which one.
    """
    # Words like "phone" or "watch" describe a category, not one product, so they never pick a product.
    words = set(_tokens(text)) - STOP_WORDS - set(CATEGORY_WORDS)
    best, best_overlap = [], 0
    for p in pool:
        overlap = len(words & set(_tokens(p["name"])))
        if not overlap:
            continue
        if overlap > best_overlap:
            best, best_overlap = [p], overlap
        elif overlap == best_overlap:
            best.append(p)
    return best


def _parse_quantity(low):
    m = re.search(r"\b(\d{1,2})\s*(?:x|pcs|pieces|units)\b", low) or re.search(r"\bx\s*(\d{1,2})\b", low)
    if m:
        return max(1, int(m.group(1)))
    for word, value in NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", low):
            return value
    return 1


def _parse_amount(number, suffix):
    value = float(number.replace(",", ""))
    if suffix and suffix.lower() == "k":
        value *= 1000
    return value


def _parse_budget(low):
    """Returns (min_price, max_price) found in the message."""
    num = r"([\d,]+(?:\.\d+)?)\s*(k)?"
    cur = r"\s*(?:৳|tk\.?|bdt|taka)?\s*"
    max_price = min_price = None
    m = re.search(rf"(?:under|below|within|less than|upto|up to|max(?:imum)?|budget(?: of| is)?|around|about){cur}{num}", low)
    if m:
        max_price = _parse_amount(m.group(1), m.group(2))
    m = re.search(rf"(?:above|over|more than|at least|minimum){cur}{num}", low)
    if m:
        min_price = _parse_amount(m.group(1), m.group(2))
    m = re.search(rf"between{cur}{num}\s*(?:and|to|-){cur}{num}", low)
    if m:
        min_price = _parse_amount(m.group(1), m.group(2))
        max_price = _parse_amount(m.group(3), m.group(4))
    return min_price, max_price


# ---------------------------------------------------------------------------
# Intents
# ---------------------------------------------------------------------------
def _add_product(ctx, text):
    body = text.split(":", 1)[1] if ":" in text else re.sub(
        r"^\s*(?:add|new)\s+(?:a\s+|new\s+)*product\s*", "", text, flags=re.I
    )
    parts = [p.strip() for p in body.split(",") if p.strip()]
    if len(parts) < 4:
        return (
            "To add a product, send it in this format:\n"
            "add product: Name, Category, Price, Stock\n\n"
            "Example:\nadd product: PulseBuds Max, Audio, 6500, 25"
        )
    name, category = parts[0], parts[1]
    price = re.sub(r"[^\d.]", "", parts[2])
    stock = re.sub(r"\D", "", parts[3])
    rating = re.sub(r"[^\d.]", "", parts[4]) if len(parts) > 4 else None
    result = execute_tool(ctx, "add_product", {
        "name": name, "category": category, "price": price or 0,
        "stock": stock or 0, "rating": rating or None,
    })
    if "error" in result:
        return f"I couldn't add that product: {result['error']}"
    p = result["product"]
    return (
        f"Done! {p['name']} is now in the catalog under {p['category']} "
        f"at {_money(p['price_bdt'])} with {p['stock']} in stock."
    )


def _checkout(ctx):
    result = execute_tool(ctx, "checkout", {})
    if "error" in result:
        return "Your cart is empty, so there's nothing to pay for yet. Tell me what you'd like to buy!"
    return f"Opening the payment window for {_money(result['total_bdt'])}. Choose bKash, Nagad or Card to finish your order."


def _show_cart(ctx):
    cart = execute_tool(ctx, "get_cart", {})
    if not cart["items"]:
        return "Your cart is empty. Try \"show laptops\" or \"best phone under 40000\"."
    lines = [f"- {i['name']} x{i['qty']} = {_money(i['line_total_bdt'])}" for i in cart["items"]]
    return "Here's your cart:\n" + "\n".join(lines) + f"\nTotal: {_money(cart['total_bdt'])}\n\nSay \"checkout\" when you're ready to pay."


def _remove(ctx, text):
    in_cart = [p for p in (store.get_product(i["id"]) for i in store.get_cart(ctx.session_id)["items"]) if p]
    matches = _match_products(text, in_cart)
    if len(matches) != 1:
        return "Which item should I remove? Say for example \"remove PulseBuds Pro\"."
    result = execute_tool(ctx, "remove_from_cart", {"product_id": matches[0]["id"]})
    if "error" in result:
        return result["error"]
    return f"Removed {matches[0]['name']} from your cart."


def _add_to_cart(ctx, text, low, matches):
    if len(matches) > 1:
        ctx.card_ids = [p["id"] for p in matches[:3]]
        names = "\n".join(f"- {p['name']} ({_money(p['price'])})" for p in matches[:5])
        return f"Which one do you mean?\n{names}"
    product = matches[0]
    result = execute_tool(ctx, "add_to_cart", {"product_id": product["id"], "quantity": _parse_quantity(low)})
    if "error" in result:
        return result["error"]
    return (
        f"Added {product['name']} to your cart. Your total is now {_money(result['cart']['total_bdt'])}.\n"
        "Say \"checkout\" to pay, or keep shopping!"
    )


def _search(ctx, low):
    words = _tokens(low)
    category = next((CATEGORY_WORDS[w] for w in words if w in CATEGORY_WORDS), None)
    keyword = next((KEYWORD_ALIASES[w] for w in words if w in KEYWORD_ALIASES), None)
    min_price, max_price = _parse_budget(low)

    # Brand names ("samsung", "rolex") are the first word of each product name.
    brands = {p["name"].split()[0].lower() for p in store.list_products()}
    brand_words = [w for w in words if w in brands]
    if brand_words:
        keyword = " ".join(([keyword] if keyword else []) + brand_words)

    if not (category or keyword or min_price or max_price):
        # Try the leftover words as a plain keyword search.
        leftovers = [w for w in words if w not in STOP_WORDS and not w.isdigit() and len(w) > 2]
        if not leftovers:
            return None
        keyword = " ".join(leftovers)

    if any(w in words for w in ("cheap", "cheapest", "lowest")):
        sort_by = "price_asc"
    else:
        sort_by = "rating_desc"

    result = execute_tool(ctx, "search_products", {
        "category": category, "query": keyword, "min_price": min_price,
        "max_price": max_price, "sort_by": sort_by,
    })
    if result["count"] == 0:
        ctx.card_ids = []
        return "I couldn't find anything matching that. Try a different budget or category, like \"show laptops\"."

    top = result["products"][:4]
    lines = [f"- {p['name']}: {_money(p['price_bdt'])}, {_rating(p)}" for p in top]
    best = top[0]
    return (
        f"I found {result['count']} match{'es' if result['count'] != 1 else ''}. Top picks:\n"
        + "\n".join(lines)
        + f"\n\n{best['name']} looks like the strongest choice here. Say \"add {best['name']} to cart\" to buy it."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def respond(ctx, text):
    low = text.lower().strip()
    tokens = set(_tokens(low))

    if re.match(r"^(?:add|new)\s+(?:a\s+|new\s+)*product\b", low):
        return _add_product(ctx, text)

    if low in ("pay", "order", "buy", "checkout") or any(
        phrase in low for phrase in (
            "checkout", "check out", "place order", "place my order", "pay now",
            "proceed to pay", "confirm order", "confirm my order", "complete order", "complete my order",
        )
    ):
        return _checkout(ctx)

    if tokens & {"remove", "delete"}:
        return _remove(ctx, low)

    all_products = store.list_products()
    if tokens & {"add", "buy", "order", "take", "get", "want", "purchase"}:
        matches = _match_products(low, all_products)
        if matches:
            return _add_to_cart(ctx, text, low, matches)

    if tokens & {"cart", "basket"}:
        return _show_cart(ctx)

    if re.match(r"^(hi|hello|hey|hola|salam|assalamu)\b", low):
        return "Hi! I'm Ruhi, your Dokan shopping assistant. Tell me what you're looking for and your budget.\n\n" + HELP

    if tokens & {"help", "commands"}:
        return HELP

    reply = _search(ctx, low)
    return reply or ("Sorry, I didn't get that.\n\n" + HELP)
