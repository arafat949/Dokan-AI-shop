// Shopping cart: header button, slide-out drawer, and the add / change / remove actions.

import { api } from "./api.js";
import { hueFor, productVisual } from "./icons.js";
import { openPayment } from "./payment.js";
import { state, subscribe, update } from "./state.js";
import { $, escapeHtml, fmt, toast } from "./utils.js";

const drawer = () => $("#cartDrawer");
const overlay = () => $("#cartOverlay");

/* ---------- Actions ---------- */
export async function addItem(productId, quantity = 1) {
  try {
    const { cart, added } = await api.addToCart(productId, quantity);
    update({ cart });
    toast(`${added} added to your cart`);
    const btn = $("#cartBtn");
    btn.classList.remove("bump");
    void btn.offsetWidth; // restart the animation
    btn.classList.add("bump");
  } catch (error) {
    toast(error.message);
  }
}

async function changeQuantity(productId, quantity) {
  try {
    update({ cart: await api.setQuantity(productId, quantity) });
  } catch (error) {
    toast(error.message);
  }
}

async function removeItem(productId) {
  try {
    update({ cart: await api.removeItem(productId) });
  } catch (error) {
    toast(error.message);
  }
}

/** Reload the cart from the server (used after the chat changes it). */
export async function refreshCart() {
  update({ cart: await api.cart() });
}

/* ---------- Drawer open / close ---------- */
export function openCart() {
  drawer().classList.add("open");
  overlay().classList.add("open");
  drawer().setAttribute("aria-hidden", "false");
}

export function closeCart() {
  drawer().classList.remove("open");
  overlay().classList.remove("open");
  drawer().setAttribute("aria-hidden", "true");
}

/* ---------- Rendering ---------- */
function render() {
  const { items, total, count } = state.cart;
  $("#cartTotal").textContent = fmt(total);
  $("#cartCount").textContent = count;

  const body = $("#cartBody");
  const foot = $("#cartFoot");

  if (items.length === 0) {
    body.innerHTML = `
      <div class="cart-empty">
        <strong>Your cart is empty</strong>
        Ask Ruhi in the chat, or add something from the product list.
      </div>`;
    foot.innerHTML = "";
    return;
  }

  body.innerHTML = items.map((item) => `
    <div class="cart-row" style="--hue:${hueFor(item.category)}">
      <div class="cart-thumb">${productVisual(item)}</div>
      <div>
        <div class="cart-name">${escapeHtml(item.name)}</div>
        <div class="cart-unit">${fmt(item.price)} each</div>
        <div class="qty">
          <button type="button" data-dec="${item.id}" aria-label="Decrease quantity of ${escapeHtml(item.name)}">−</button>
          <span>${item.qty}</span>
          <button type="button" data-inc="${item.id}" aria-label="Increase quantity of ${escapeHtml(item.name)}" ${item.qty >= item.stock ? "disabled" : ""}>+</button>
        </div>
      </div>
      <div class="cart-line">
        <strong>${fmt(item.line_total)}</strong>
        <button type="button" class="remove-btn" data-remove="${item.id}">Remove</button>
      </div>
    </div>`).join("");

  foot.innerHTML = `
    <div class="total-row"><span>Total</span><strong>${fmt(total)}</strong></div>
    <button type="button" class="btn-checkout" id="checkoutBtn">Pay ${fmt(total)}</button>`;
}

/* ---------- Setup ---------- */
export function initCart() {
  subscribe(render);
  render();

  $("#cartBtn").addEventListener("click", openCart);
  $("#cartClose").addEventListener("click", closeCart);
  overlay().addEventListener("click", closeCart);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && drawer().classList.contains("open")) closeCart();
  });

  // One listener handles every button inside the drawer.
  drawer().addEventListener("click", (e) => {
    const inc = e.target.closest("[data-inc]");
    const dec = e.target.closest("[data-dec]");
    const rem = e.target.closest("[data-remove]");
    const pay = e.target.closest("#checkoutBtn");

    const find = (id) => state.cart.items.find((i) => i.id === Number(id));
    if (inc) changeQuantity(Number(inc.dataset.inc), find(inc.dataset.inc).qty + 1);
    if (dec) changeQuantity(Number(dec.dataset.dec), find(dec.dataset.dec).qty - 1);
    if (rem) removeItem(Number(rem.dataset.remove));
    if (pay) {
      closeCart();
      openPayment();
    }
  });
}
