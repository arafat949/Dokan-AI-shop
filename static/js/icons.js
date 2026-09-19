// Product pictures: a real image if the product has one, otherwise a line icon.
// Icons are drawn with currentColor so CSS can tint them per category.

import { escapeHtml } from "./utils.js";

const wrap = (inner) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;

const ICONS = {
  laptop: wrap('<rect x="4" y="5" width="16" height="10" rx="1.2"/><path d="M2 18h20l-1.5-3h-17z"/>'),
  phone: wrap('<rect x="7" y="2.5" width="10" height="19" rx="2"/><path d="M10.5 18.5h3"/>'),
  tablet: wrap('<rect x="4.5" y="3" width="15" height="18" rx="2"/><path d="M11 18h2"/>'),
  buds: wrap('<circle cx="8" cy="9" r="3"/><circle cx="16" cy="9" r="3"/><path d="M8 12v4a3 3 0 003 3M16 12v4a3 3 0 01-3 3"/>'),
  headphones: wrap('<path d="M4 15v-3a8 8 0 0116 0v3"/><rect x="3" y="14" width="4" height="7" rx="1.5"/><rect x="17" y="14" width="4" height="7" rx="1.5"/>'),
  speaker: wrap('<rect x="6" y="2.5" width="12" height="19" rx="3"/><circle cx="12" cy="14.5" r="3.5"/><circle cx="12" cy="7" r="1"/>'),
  mic: wrap('<rect x="9" y="2.5" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0013 0M12 17.5V21M8.5 21h7"/>'),
  watch: wrap('<rect x="7" y="7" width="10" height="10" rx="2.5"/><path d="M9 7V4h6v3M9 17v3h6v-3"/>'),
  keyboard: wrap('<rect x="2.5" y="6" width="19" height="12" rx="1.5"/><path d="M6 10h.01M9 10h.01M12 10h.01M15 10h.01M18 10h.01M7 14.5h10"/>'),
  mouse: wrap('<rect x="7" y="2.5" width="10" height="19" rx="5"/><path d="M12 2.5V9"/>'),
  hub: wrap('<rect x="3" y="10" width="18" height="8" rx="1.5"/><path d="M7 10V6.5M12 10V6.5M17 10V6.5M7 14h2M11 14h2M15 14h2"/>'),
  monitor: wrap('<rect x="3" y="4" width="18" height="12" rx="1.2"/><path d="M9 20h6M12 16v4"/>'),
  power: wrap('<rect x="6" y="3" width="12" height="18" rx="2"/><path fill="currentColor" stroke="none" d="M13 7l-4 6h3l-1 4 4-6h-3z"/>'),
  charger: wrap('<rect x="6" y="7" width="12" height="13" rx="2"/><path d="M10 7V3.5M14 7V3.5M12.5 11l-2 3h3l-1 3"/>'),
  camera: wrap('<path d="M3 8.5A1.5 1.5 0 014.5 7H8l1.5-2h5L16 7h3.5A1.5 1.5 0 0121 8.5v9a1.5 1.5 0 01-1.5 1.5h-15A1.5 1.5 0 013 17.5z"/><circle cx="12" cy="13" r="3.5"/>'),
  gamepad: wrap('<path d="M7 8h10a4 4 0 014 4v2.5a2.5 2.5 0 01-4.3 1.7L15 14.5H9l-1.7 1.7A2.5 2.5 0 013 14.5V12a4 4 0 014-4z"/><path d="M8 10.5v3M6.5 12h3M15.5 11.5h.01M17.5 13h.01"/>'),
  home: wrap('<path d="M3.5 11L12 4l8.5 7"/><path d="M5.5 10v9.5h13V10"/><path d="M10 19.5v-5h4v5"/>'),
  router: wrap('<rect x="3" y="13" width="18" height="6" rx="1.5"/><path d="M7 16h.01M10 16h.01M7 13V9M17 13V9M9.5 6.5a3.5 3.5 0 015 0"/>'),
  storage: wrap('<rect x="4" y="3.5" width="16" height="17" rx="2"/><path d="M4 15h16M8 18h.01"/>'),
  box: wrap('<path d="M12 3l8.5 4.5v9L12 21l-8.5-4.5v-9z"/><path d="M3.5 7.5L12 12l8.5-4.5M12 12v9"/>'),
};

export function iconSvg(name) {
  return ICONS[name] || ICONS.box;
}

/**
 * What to show for a product.
 * - product.image = "phone.jpg"  -> static/images/phone.jpg
 * - product.image = "https://..." -> that web address
 * - no image (or it fails to load) -> the product's icon
 */
export function productVisual(product) {
  if (!product.image) return iconSvg(product.icon);
  const src = /^https?:\/\//i.test(product.image) ? product.image : `/static/images/${encodeURI(product.image)}`;
  return `<img class="product-img" src="${escapeHtml(src)}" alt="" loading="lazy" data-icon="${escapeHtml(product.icon || "box")}">`;
}

// If an image is missing or broken, quietly swap it for the icon.
document.addEventListener("error", (e) => {
  const img = e.target;
  if (!(img instanceof HTMLImageElement) || !img.classList.contains("product-img")) return;
  img.closest(".card-visual")?.classList.remove("has-photo");
  img.outerHTML = iconSvg(img.dataset.icon);
}, true);

// Each category gets its own color (a hue on the color wheel).
const CATEGORY_HUES = {
  Laptop: 205, Smartphone: 265, Tablet: 305, Audio: 340, Watch: 18,
  Accessories: 42, Monitor: 175, Power: 95, Camera: 355, Gaming: 140,
  "Smart Home": 55, Networking: 225, Storage: 285,
};

/** Known categories get a fixed hue; new categories get a stable one from their name. */
export function hueFor(category) {
  if (category in CATEGORY_HUES) return CATEGORY_HUES[category];
  let hash = 0;
  for (const ch of category) hash = (hash * 31 + ch.charCodeAt(0)) % 360;
  return hash;
}
