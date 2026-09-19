// Product catalog: search box, category chips, sorting and the product grid.

import { api } from "./api.js";
import { addItem } from "./cart.js";
import { hueFor, productVisual } from "./icons.js";
import { state, subscribe, update } from "./state.js";
import { $, escapeHtml, fmt } from "./utils.js";

const filters = { search: "", category: "All", sort: "featured" };

/** Fetch the latest products (stock changes after orders, and the chat can add products). */
export async function reloadProducts() {
  const { products, categories } = await api.products();
  update({ products, categories });
}

function visibleProducts() {
  const words = filters.search.toLowerCase().split(/\s+/).filter(Boolean);

  let list = state.products.filter((p) => {
    if (filters.category !== "All" && p.category !== filters.category) return false;
    const haystack = `${p.name} ${p.category} ${p.specs.join(" ")}`.toLowerCase();
    return words.every((w) => haystack.includes(w));
  });

  if (filters.sort === "price_asc") list.sort((a, b) => a.price - b.price);
  else if (filters.sort === "price_desc") list.sort((a, b) => b.price - a.price);
  else if (filters.sort === "rating") list.sort((a, b) => (b.rating || 0) - (a.rating || 0));
  return list;
}

function cardHtml(p) {
  const inCart = state.cart.items.find((i) => i.id === p.id);
  const soldOut = p.stock <= 0;
  const low = !soldOut && p.stock <= 5;
  const stockText = soldOut ? "Sold out" : low ? `Only ${p.stock} left` : "In stock";
  const rating = p.rating ? `<span class="rating">★ ${p.rating.toFixed(1)}</span>` : `<span class="rating new">New</span>`;

  return `
    <article class="card" style="--hue:${hueFor(p.category)}">
      <div class="card-visual ${p.image ? "has-photo" : ""}">
        <span class="card-cat">${escapeHtml(p.category)}</span>
        ${inCart ? `<span class="card-incart">${inCart.qty} in cart</span>` : ""}
        <div class="card-icon">${productVisual(p)}</div>
      </div>
      <div class="card-body">
        <h3 class="card-name">${escapeHtml(p.name)}</h3>
        <ul class="specs">${p.specs.slice(0, 2).map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul>
        <div class="card-meta">${rating}<span class="stock ${low || soldOut ? "low" : ""}">${stockText}</span></div>
        <div class="card-foot">
          <span class="price">${fmt(p.price)}</span>
          <button type="button" class="btn-add" data-add="${p.id}" ${soldOut ? "disabled" : ""}>Add</button>
        </div>
      </div>
    </article>`;
}

function render() {
  // Category chips
  const categories = ["All", ...state.categories];
  if (!categories.includes(filters.category)) filters.category = "All";
  $("#categoryChips").innerHTML = categories.map((c) => `
    <button type="button" class="chip ${c === filters.category ? "active" : ""}" data-category="${escapeHtml(c)}"
            role="tab" aria-selected="${c === filters.category}">${escapeHtml(c)}</button>`).join("");

  // Grid
  const list = visibleProducts();
  $("#resultCount").textContent = `${list.length} of ${state.products.length}`;

  $("#catalogGrid").innerHTML = list.length
    ? list.map(cardHtml).join("")
    : `<div class="empty-state">
         <strong>No products match</strong>
         Try a different word or category.
         <br><button type="button" id="clearFilters">Clear filters</button>
       </div>`;
}

export function initCatalog() {
  subscribe(render);

  $("#searchInput").addEventListener("input", (e) => {
    filters.search = e.target.value;
    render();
  });
  $("#sortSelect").addEventListener("change", (e) => {
    filters.sort = e.target.value;
    render();
  });

  $("#categoryChips").addEventListener("click", (e) => {
    const chip = e.target.closest("[data-category]");
    if (!chip) return;
    filters.category = chip.dataset.category;
    render();
  });

  $("#catalogGrid").addEventListener("click", (e) => {
    const add = e.target.closest("[data-add]");
    if (add) addItem(Number(add.dataset.add));

    if (e.target.closest("#clearFilters")) {
      filters.search = "";
      filters.category = "All";
      $("#searchInput").value = "";
      render();
    }
  });
}
