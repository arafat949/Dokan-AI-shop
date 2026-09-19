// Entry point: start every part of the page, then load data from the server.

import { api } from "./api.js";
import { initCart } from "./cart.js";
import { initCatalog, reloadProducts } from "./catalog.js";
import { initChat } from "./chat.js";
import { initPayment } from "./payment.js";
import { state, subscribe, update } from "./state.js";
import { $, toast } from "./utils.js";

function renderModeBadge() {
  const badge = $("#modeBadge");
  if (!("ai_enabled" in state.config)) return;

  badge.hidden = false;
  if (state.config.ai_enabled) {
    badge.textContent = "Claude AI is on";
    badge.className = "mode-badge ai";
    badge.title = `Model: ${state.config.model}`;
  } else {
    badge.textContent = "Basic mode";
    badge.className = "mode-badge";
    badge.title = "Add ANTHROPIC_API_KEY to the .env file to turn on the AI assistant.";
  }
}

async function start() {
  initCatalog();
  initCart();
  initChat();
  initPayment();
  subscribe(renderModeBadge);

  try {
    const [config, catalog, cart] = await Promise.all([api.config(), api.products(), api.cart()]);
    update({ config, products: catalog.products, categories: catalog.categories, cart });
  } catch (error) {
    toast(error.message);
  }

  // After an order, stock has changed, so reload the product list.
  document.addEventListener("order:placed", () => reloadProducts().catch(() => {}));
}

start();
