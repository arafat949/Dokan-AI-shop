// Chat with Arafat: sending messages, showing replies, product cards and order receipts.

import { api } from "./api.js";
import { addItem } from "./cart.js";
import { reloadProducts } from "./catalog.js";
import { hueFor, productVisual } from "./icons.js";
import { openPayment } from "./payment.js";
import { update } from "./state.js";
import { $, escapeHtml, fmt } from "./utils.js";

let busy = false;

const WELCOME =
  "Hi, I'm Arafat, Dokan's shopping assistant.\n\n" +
  "Tell me what you need and your budget, and I'll find the best match. " +
  "I can also add items to your cart, take you through payment with bKash, Nagad or card, " +
  "and add new products to the store.";

/* ---------- Building blocks ---------- */
function scrollToBottom() {
  const body = $("#chatBody");
  body.scrollTop = body.scrollHeight;
}

/** Escape the text, then turn **bold** into <strong>. */
function formatText(text) {
  return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

function cardsHtml(products) {
  if (!products || products.length === 0) return "";
  return `<div class="chat-cards">${products.map((p) => `
    <div class="chat-card" style="--hue:${hueFor(p.category)}">
      <div class="chat-card-icon">${productVisual(p)}</div>
      <div>
        <div class="chat-card-name">${escapeHtml(p.name)}</div>
        <div class="chat-card-price">${fmt(p.price)}</div>
      </div>
      <button type="button" class="btn-add" data-add="${p.id}" ${p.stock <= 0 ? "disabled" : ""}>Add</button>
    </div>`).join("")}</div>`;
}

function receiptHtml(order, methodLabel) {
  const rows = order.items.map((i) =>
    `<div class="receipt-row"><span>${escapeHtml(i.name)} × ${i.qty}</span><span>${fmt(i.price * i.qty)}</span></div>`
  ).join("");
  return `
    <div class="receipt">
      <h4>Order ${escapeHtml(order.order_id)} confirmed</h4>
      ${rows}
      <div class="receipt-row"><span>Paid with</span><span>${escapeHtml(methodLabel)}</span></div>
      <div class="receipt-row"><span>Transaction ID</span><span>${escapeHtml(order.transaction_id)}</span></div>
      <div class="receipt-row total"><span>Total paid</span><span>${fmt(order.total)}</span></div>
    </div>`;
}

function addMessage(role, text, extraHtml = "") {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  const who = role === "user" ? "You" : role === "assistant" ? "Arafat" : "";
  el.innerHTML = `
    ${who ? `<div class="msg-who">${who}</div>` : ""}
    <div class="bubble">${formatText(text)}</div>
    ${extraHtml}`;
  $("#chatBody").appendChild(el);
  scrollToBottom();
}

function showTyping() {
  const el = document.createElement("div");
  el.className = "msg assistant";
  el.id = "typingRow";
  el.innerHTML = `<div class="msg-who">Arafat</div><div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>`;
  $("#chatBody").appendChild(el);
  scrollToBottom();
}

function hideTyping() {
  $("#typingRow")?.remove();
}

/* ---------- Sending ---------- */
async function send(rawText) {
  const text = rawText.trim();
  if (!text || busy) return;

  busy = true;
  $("#chatInput").value = "";
  $("#sendBtn").disabled = true;
  addMessage("user", text);
  showTyping();

  try {
    const result = await api.chat(text);
    hideTyping();
    addMessage("assistant", result.reply, cardsHtml(result.cards));

    update({ cart: result.cart });
    if (result.catalog_changed) await reloadProducts();
    if (result.ui_actions.some((a) => a.type === "open_payment")) openPayment();
  } catch (error) {
    hideTyping();
    addMessage("note", error.message);
  } finally {
    busy = false;
    $("#sendBtn").disabled = false;
    $("#chatInput").focus();
  }
}

/* ---------- Setup ---------- */
export function initChat() {
  addMessage("assistant", WELCOME);

  $("#chatForm").addEventListener("submit", (e) => {
    e.preventDefault();
    send($("#chatInput").value);
  });

  $("#suggestions").addEventListener("click", (e) => {
    const button = e.target.closest("[data-ask]");
    if (button) send(button.dataset.ask);
  });

  // "Add" buttons on product cards inside the chat.
  $("#chatBody").addEventListener("click", (e) => {
    const add = e.target.closest("[data-add]");
    if (add) addItem(Number(add.dataset.add));
  });

  // Events fired by the payment popup.
  document.addEventListener("order:placed", (e) => {
    const { order, method_label } = e.detail;
    addMessage(
      "assistant",
      "Payment received. Thank you for shopping with Dokan! Here is your receipt.",
      receiptHtml(order, method_label)
    );
  });

  document.addEventListener("payment:cancelled", () => {
    addMessage("note", "Payment cancelled. Your cart is saved. Say \"checkout\" whenever you're ready.");
  });
}
