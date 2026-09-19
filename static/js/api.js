// Every call to the Python server goes through here.

const SESSION_KEY = "dokan-session-id";

/** A random ID stored in the browser so the server can keep this visitor's cart and chat. */
function sessionId() {
  let id = null;
  try { id = localStorage.getItem(SESSION_KEY); } catch { /* storage blocked */ }
  if (!id) {
    id = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()) + Math.random().toString(16).slice(2);
    try { localStorage.setItem(SESSION_KEY, id); } catch { /* ignore */ }
  }
  return id;
}

async function request(path, { method = "GET", body } = {}) {
  let response;
  try {
    response = await fetch(path, {
      method,
      headers: { "Content-Type": "application/json", "X-Session-Id": sessionId() },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Can't reach the Dokan server. Is it still running?");
  }

  let data = {};
  try { data = await response.json(); } catch { /* empty body */ }

  if (!response.ok) {
    const error = new Error(data.error || "Something went wrong. Please try again.");
    error.field = data.field;
    throw error;
  }
  return data;
}

export const api = {
  config: () => request("/api/config"),
  products: () => request("/api/products"),
  cart: () => request("/api/cart"),
  addToCart: (productId, quantity = 1) =>
    request("/api/cart/items", { method: "POST", body: { product_id: productId, quantity } }),
  setQuantity: (productId, quantity) =>
    request(`/api/cart/items/${productId}`, { method: "PATCH", body: { quantity } }),
  removeItem: (productId) => request(`/api/cart/items/${productId}`, { method: "DELETE" }),
  chat: (message) => request("/api/chat", { method: "POST", body: { message } }),
  pay: (payload) => request("/api/pay", { method: "POST", body: payload }),
};
