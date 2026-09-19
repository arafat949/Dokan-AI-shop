"""Chat brain of Dokan.

`chat()` sends the customer's message to Claude with the shop tools attached
and keeps running tools until Claude has a final answer. If there is no API
key (or the AI service fails), the rule-based fallback assistant answers.
"""

import json
import logging
import threading

import config
import fallback_agent
import store
from tools import TOOLS, ToolContext, execute_tool

log = logging.getLogger("dokan.ai")

MAX_TOOL_STEPS = 6
MAX_HISTORY = 30

SYSTEM_PROMPT = """You are Arafat, the shopping assistant for Dokan, an online electronics store in Bangladesh. All prices are in Bangladeshi Taka (BDT, shown as ৳). Be friendly, short and clear. Always reply in English.

Rules:
1. Never guess prices, stock or specs. Call search_products to get real data.
2. When the customer gives a budget, recommend the best value option and explain why in one or two lines.
3. When there are several options, give a short comparison (price, key spec, rating).
4. When the customer wants a product, call add_to_cart. If it is unclear which product they mean, ask.
5. When the customer says they want to order, check out or pay, call checkout. This opens a secure payment popup where they choose bKash, Nagad or Card. Never ask for phone numbers, PINs or card details in the chat. The order is only confirmed after they pay in the popup, so never say it is confirmed before that.
6. Store owners can add products by chatting. When someone wants to add a product, collect the name, category, price (BDT) and stock. If something is missing, ask for it in one short message. Once you have everything, call add_product. Specs and rating are optional.
7. Keep answers under about 120 words. Use plain text only: no headings, no bold markers. Use simple "- " bullets when listing options."""

_histories = {}
_history_lock = threading.Lock()
_client = None


def ai_enabled():
    return bool(config.ANTHROPIC_API_KEY)


def _get_client():
    global _client
    if _client is None:
        import anthropic  # imported here so basic mode works without the package
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _get_history(session_id):
    with _history_lock:
        return _histories.setdefault(session_id, [])


def _trim(history):
    """Keep the history short, always starting at a plain customer message."""
    if len(history) <= MAX_HISTORY:
        return
    cut = len(history) - MAX_HISTORY
    while cut < len(history):
        message = history[cut]
        if message["role"] == "user" and isinstance(message["content"], str):
            break
        cut += 1
    del history[:cut]


def _run_claude(history, ctx):
    """Talk to Claude, running its tool calls, until it gives a final answer."""
    client = _get_client()
    texts = []
    for _ in range(MAX_TOOL_STEPS):
        response = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history,
        )
        history.append({"role": "assistant", "content": response.content})

        texts.extend(b.text.strip() for b in response.content if b.type == "text" and b.text.strip())
        tool_calls = [b for b in response.content if b.type == "tool_use"]
        if not tool_calls:
            break

        results = []
        for call in tool_calls:
            outcome = execute_tool(ctx, call.name, call.input)
            results.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": json.dumps(outcome),
            })
        history.append({"role": "user", "content": results})
    return "\n\n".join(texts)


def chat(session_id, message):
    """Handle one customer message. Returns a dict for the frontend."""
    ctx = ToolContext(session_id)
    history = _get_history(session_id)
    reply, mode = None, "basic"

    if ai_enabled():
        snapshot = list(history)
        try:
            history.append({"role": "user", "content": message})
            _trim(history)
            reply = _run_claude(history, ctx)
            mode = "ai"
        except Exception as e:  # noqa: BLE001 - any AI failure is handled below
            log.warning("AI request failed: %s", e)
            history[:] = snapshot  # drop the half-finished turn
            if ctx.executed:
                # Something already happened (e.g. an item was added). Don't repeat it.
                mode = "ai"
                reply = ("I ran into a problem with the AI service, but your last action went through. "
                         "Please check your cart and tell me what to do next.")

    if reply is None:
        # No API key, or the AI service failed before doing anything: use basic mode.
        ctx = ToolContext(session_id)
        reply = fallback_agent.respond(ctx, message)
        if ai_enabled():
            reply = "(The AI service is not responding, so I'm using basic mode for now.)\n\n" + reply
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        _trim(history)

    return {
        "reply": reply or "Done!",
        "mode": mode,
        "cards": [p for p in (store.get_product(i) for i in ctx.card_ids) if p],
        "ui_actions": ctx.ui_actions,
        "catalog_changed": ctx.catalog_changed,
    }


def record_event(session_id, note):
    """Tell the assistant about something that happened outside the chat (e.g. a payment)."""
    history = _get_history(session_id)
    history.append({"role": "user", "content": f"[Store system message] {note}"})
    history.append({"role": "assistant", "content": "Thanks, noted."})
