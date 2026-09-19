"""The actions the chat assistant can perform.

`TOOLS` describes them to Claude. `execute_tool()` runs them for real against
the store. The rule-based fallback assistant uses the same function, so both
modes behave identically.
"""

import store
from store import StoreError

TOOLS = [
    {
        "name": "search_products",
        "description": (
            "Search the live product catalog by category, price range or keywords. "
            "Always call this instead of guessing product details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords, e.g. 'wireless earbuds'. Optional."},
                "category": {
                    "type": "string",
                    "description": "One of: Laptop, Smartphone, Tablet, Audio, Watch, Accessories, "
                                   "Monitor, Power, Camera, Gaming, Smart Home, Networking, Storage. Optional.",
                },
                "max_price": {"type": "number", "description": "Maximum price in BDT. Optional."},
                "min_price": {"type": "number", "description": "Minimum price in BDT. Optional."},
                "sort_by": {
                    "type": "string",
                    "enum": ["price_asc", "price_desc", "rating_desc", "best_value"],
                    "description": "How to rank the results. Optional.",
                },
            },
        },
    },
    {
        "name": "add_to_cart",
        "description": "Add a product to the customer's cart using its exact product id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "number"},
                "quantity": {"type": "number", "description": "Defaults to 1."},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "remove_from_cart",
        "description": "Remove a product from the cart by product id.",
        "input_schema": {
            "type": "object",
            "properties": {"product_id": {"type": "number"}},
            "required": ["product_id"],
        },
    },
    {
        "name": "get_cart",
        "description": "Get everything currently in the customer's cart, with the total price.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "checkout",
        "description": (
            "Start checkout. This opens a secure payment popup on the customer's screen where they "
            "choose bKash, Nagad or Card and enter their details. The order is NOT placed until the "
            "customer completes payment in that popup. Only call this when the customer clearly says "
            "they want to order, checkout or pay."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "add_product",
        "description": (
            "Add a brand-new product to the store catalog. Only call this once you know the name, "
            "category, price in BDT and stock quantity."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "category": {"type": "string", "description": "Use an existing category when one fits."},
                "price": {"type": "number", "description": "Price in BDT."},
                "stock": {"type": "number", "description": "Units available."},
                "rating": {"type": "number", "description": "0 to 5. Optional - leave out for new items."},
                "specs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Up to 4 short spec lines. Optional.",
                },
                "icon": {
                    "type": "string",
                    "enum": store.VALID_ICONS,
                    "description": "Icon to show for the product. Optional - one is chosen from the category.",
                },
            },
            "required": ["name", "category", "price", "stock"],
        },
    },
]


class ToolContext:
    """Collects side effects of a chat turn so the frontend can react to them."""

    def __init__(self, session_id):
        self.session_id = session_id
        self.card_ids = []          # products to show as cards under the reply
        self.ui_actions = []        # e.g. {"type": "open_payment"}
        self.catalog_changed = False
        self.executed = 0           # how many tools have run this turn


def _summary(product):
    return {
        "id": product["id"], "name": product["name"], "category": product["category"],
        "price_bdt": product["price"], "rating": product["rating"],
        "stock": product["stock"], "specs": product["specs"],
    }


def _cart_summary(session_id):
    cart = store.get_cart(session_id)
    return {
        "items": [
            {"id": i["id"], "name": i["name"], "qty": i["qty"],
             "price_bdt": i["price"], "line_total_bdt": i["line_total"]}
            for i in cart["items"]
        ],
        "total_bdt": cart["total"],
    }


def execute_tool(ctx, name, args):
    """Run one tool. Always returns a dict; problems come back as {"error": ...}."""
    args = args or {}
    ctx.executed += 1
    try:
        if name == "search_products":
            results = store.search_products(
                query=args.get("query"), category=args.get("category"),
                min_price=args.get("min_price"), max_price=args.get("max_price"),
                sort_by=args.get("sort_by"),
            )
            ctx.card_ids = [p["id"] for p in results[:3]]
            return {"count": len(results), "products": [_summary(p) for p in results[:12]]}

        if name == "add_to_cart":
            product = store.add_to_cart(ctx.session_id, int(args["product_id"]), args.get("quantity", 1))
            return {"success": True, "added": product["name"], "cart": _cart_summary(ctx.session_id)}

        if name == "remove_from_cart":
            store.remove_from_cart(ctx.session_id, int(args["product_id"]))
            return {"success": True, "cart": _cart_summary(ctx.session_id)}

        if name == "get_cart":
            return _cart_summary(ctx.session_id)

        if name == "checkout":
            cart = store.get_cart(ctx.session_id)
            if not cart["items"]:
                return {"error": "The cart is empty. Add a product first."}
            ctx.ui_actions.append({"type": "open_payment"})
            return {
                "status": "payment_popup_opened",
                "total_bdt": cart["total"],
                "note": "The payment popup is now open. The order is only confirmed after the "
                        "customer pays. Do not say the order is confirmed yet.",
            }

        if name == "add_product":
            product = store.add_product(
                name=args.get("name"), category=args.get("category"),
                price=args.get("price"), stock=args.get("stock"),
                rating=args.get("rating"), specs=args.get("specs"), icon=args.get("icon"),
            )
            ctx.catalog_changed = True
            ctx.card_ids = [product["id"]]
            return {"success": True, "product": _summary(product)}

    except StoreError as e:
        return {"error": str(e)}
    except (KeyError, TypeError, ValueError):
        return {"error": "Invalid arguments for this tool."}

    return {"error": f"Unknown tool: {name}"}
