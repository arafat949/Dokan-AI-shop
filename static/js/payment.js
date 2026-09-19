// The payment popup. Demo only: no real money moves.
//
// bKash / Nagad: step 1 = account number, step 2 = PIN.
// Card: number, name, expiry and CVV on one screen.
// On success it fires an "order:placed" event; on close-without-paying, "payment:cancelled".

import { api } from "./api.js";
import { state, update } from "./state.js";
import { $, $$, escapeHtml, fmt, sleep, toast } from "./utils.js";

const METHODS = {
  bkash: { label: "bKash", numberLabel: "Your bKash account number", pinLabel: "Enter your bKash PIN" },
  nagad: { label: "Nagad", numberLabel: "Your Nagad account number", pinLabel: "Enter your Nagad PIN" },
  card: { label: "Card payment" },
};

const MOBILE = /^01[3-9]\d{8}$/;

let method = "bkash";
let busy = false;
let completed = false;
let returnFocus = null;

const modal = () => $("#payModal");
const digits = (value) => value.replace(/\D/g, "");

/* ---------- Views and steps ---------- */
function showView(name) {
  $("#viewForm").hidden = name !== "form";
  $("#viewProcessing").hidden = name !== "processing";
  $("#viewSuccess").hidden = name !== "success";
}

function showWalletStep(step) {
  $("#stepNumber").hidden = step !== "number";
  $("#stepPin").hidden = step !== "pin";

  if (step === "pin") {
    const number = $("#walletNumber").value;
    $("#pinAccount").textContent = `${METHODS[method].label} account ${number.slice(0, 3)}****${number.slice(-3)}`;
    $("#walletPin").focus();
  } else {
    $("#walletNumber").focus();
  }
}

function selectMethod(next) {
  method = next;
  $("#payCard").dataset.method = next;
  $("#payBrand").textContent = METHODS[next].label;

  $$(".pay-method").forEach((button) => {
    const active = button.dataset.method === next;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });

  const isCard = next === "card";
  $("#walletForm").hidden = isCard;
  $("#cardForm").hidden = !isCard;
  clearErrors();

  if (isCard) {
    $("#cardNumber").focus();
  } else {
    $("#walletNumberLabel").textContent = METHODS[next].numberLabel;
    $("#walletPinLabel").textContent = METHODS[next].pinLabel;
    $("#walletPin").value = "";
    showWalletStep("number");
  }
}

/* ---------- Errors ---------- */
const ERROR_IDS = {
  walletNumber: "errWalletNumber", walletPin: "errWalletPin",
  cardNumber: "errCardNumber", cardName: "errCardName", cardExpiry: "errCardExpiry", cardCvv: "errCardCvv",
};

function clearErrors() {
  Object.entries(ERROR_IDS).forEach(([inputId, errorId]) => {
    $(`#${errorId}`).textContent = "";
    $(`#${inputId}`).classList.remove("invalid");
  });
  $("#payError").textContent = "";
}

function fail(inputId, message) {
  clearErrors();
  $(`#${ERROR_IDS[inputId]}`).textContent = message;
  $(`#${inputId}`).classList.add("invalid");
  $(`#${inputId}`).focus();
  return false;
}

// Server field names -> input ids
const FIELD_TO_INPUT = {
  number: "walletNumber", pin: "walletPin",
  card_number: "cardNumber", name: "cardName", expiry: "cardExpiry", cvv: "cardCvv",
};

function showServerError(error) {
  const inputId = FIELD_TO_INPUT[error.field];
  if (!inputId) {
    clearErrors();
    $("#payError").textContent = error.message;
    return;
  }
  if (inputId === "walletNumber") showWalletStep("number");
  fail(inputId, error.message);
}

/* ---------- Validation (the server checks again) ---------- */
function validateWalletNumber() {
  if (!MOBILE.test($("#walletNumber").value)) {
    return fail("walletNumber", "Enter a valid 11-digit mobile number, like 01712345678.");
  }
  clearErrors();
  return true;
}

function validateWalletPin() {
  const length = $("#walletPin").value.length;
  if (length < 4 || length > 5) return fail("walletPin", "Enter your 4 or 5 digit PIN.");
  clearErrors();
  return true;
}

function validateCard() {
  if (!/^\d{13,19}$/.test(digits($("#cardNumber").value))) return fail("cardNumber", "Enter a valid card number.");
  if ($("#cardName").value.trim().length < 2) return fail("cardName", "Enter the name on the card.");

  const match = $("#cardExpiry").value.match(/^(\d{2})\/(\d{2})$/);
  if (!match || +match[1] < 1 || +match[1] > 12) return fail("cardExpiry", "Enter the expiry date as MM/YY.");
  const now = new Date();
  if (2000 + +match[2] < now.getFullYear() || (2000 + +match[2] === now.getFullYear() && +match[1] < now.getMonth() + 1)) {
    return fail("cardExpiry", "This card has expired.");
  }

  if (!/^\d{3,4}$/.test($("#cardCvv").value)) return fail("cardCvv", "Enter the 3 or 4 digit security code.");
  clearErrors();
  return true;
}

/* ---------- Paying ---------- */
function renderSuccess({ order, method_label }) {
  $("#successLine").textContent = `Thank you! Order ${order.order_id} is confirmed.`;
  const rows = [
    ["Order ID", order.order_id],
    ["Transaction ID", order.transaction_id],
    ["Paid with", `${method_label} (${order.account})`],
    ["Amount paid", fmt(order.total)],
  ];
  $("#successDetails").innerHTML = rows
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`)
    .join("");
}

async function submitPayment(payload) {
  busy = true;
  showView("processing");

  // Wait at least a moment so the "processing" screen feels real.
  const [result] = await Promise.all([api.pay(payload).catch((e) => e), sleep(1600)]);
  busy = false;

  if (result instanceof Error) {
    showView("form");
    showServerError(result);
    return;
  }

  completed = true;
  update({ cart: result.cart });
  renderSuccess(result);
  showView("success");
  document.dispatchEvent(new CustomEvent("order:placed", { detail: result }));
}

/* ---------- Open / close ---------- */
export function openPayment() {
  if (!modal().hidden) return;
  if (state.cart.items.length === 0) {
    toast("Your cart is empty");
    return;
  }

  completed = false;
  busy = false;
  returnFocus = document.activeElement;

  ["walletNumber", "walletPin", "cardNumber", "cardName", "cardExpiry", "cardCvv"].forEach((id) => { $(`#${id}`).value = ""; });
  $("#payAmount").textContent = fmt(state.cart.total);
  $("#payWalletBtn").textContent = `Pay ${fmt(state.cart.total)}`;
  $("#payCardBtn").textContent = `Pay ${fmt(state.cart.total)}`;

  showView("form");
  modal().hidden = false;
  document.body.classList.add("modal-open");
  selectMethod("bkash");
}

function closePayment() {
  if (busy || modal().hidden) return;
  modal().hidden = true;
  document.body.classList.remove("modal-open");
  if (!completed) document.dispatchEvent(new CustomEvent("payment:cancelled"));
  if (returnFocus && returnFocus.focus) returnFocus.focus();
}

/* ---------- Setup ---------- */
export function initPayment() {
  modal().addEventListener("click", (e) => {
    if (e.target.closest("[data-close]")) closePayment();
  });

  $$(".pay-method").forEach((button) => {
    button.addEventListener("click", () => selectMethod(button.dataset.method));
  });

  // Input formatting
  const digitsOnly = (id) => $(`#${id}`).addEventListener("input", (e) => { e.target.value = digits(e.target.value); });
  digitsOnly("walletNumber");
  digitsOnly("walletPin");
  digitsOnly("cardCvv");

  $("#cardNumber").addEventListener("input", (e) => {
    e.target.value = digits(e.target.value).slice(0, 19).replace(/(.{4})/g, "$1 ").trim();
  });
  $("#cardExpiry").addEventListener("input", (e) => {
    const d = digits(e.target.value).slice(0, 4);
    e.target.value = d.length > 2 ? `${d.slice(0, 2)}/${d.slice(2)}` : d;
  });

  // bKash / Nagad: number first, then PIN
  $("#walletForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const onPinStep = !$("#stepPin").hidden;
    if (!onPinStep) {
      if (validateWalletNumber()) showWalletStep("pin");
      return;
    }
    if (validateWalletPin()) {
      submitPayment({ method, number: $("#walletNumber").value, pin: $("#walletPin").value });
    }
  });
  $("#pinBack").addEventListener("click", () => { clearErrors(); showWalletStep("number"); });

  // Card
  $("#cardForm").addEventListener("submit", (e) => {
    e.preventDefault();
    if (!validateCard()) return;
    submitPayment({
      method: "card",
      card_number: $("#cardNumber").value,
      name: $("#cardName").value,
      expiry: $("#cardExpiry").value,
      cvv: $("#cardCvv").value,
    });
  });

  // Demo helper
  $("#fillDemo").addEventListener("click", () => {
    if (method === "card") {
      const year = String((new Date().getFullYear() + 2) % 100).padStart(2, "0");
      $("#cardNumber").value = "4242 4242 4242 4242";
      $("#cardName").value = "Demo Customer";
      $("#cardExpiry").value = `12/${year}`;
      $("#cardCvv").value = "123";
    } else {
      $("#walletNumber").value = "01712345678";
      $("#walletPin").value = method === "nagad" ? "1234" : "12345";
    }
    clearErrors();
  });

  // Keyboard: Esc closes, Tab stays inside the popup
  document.addEventListener("keydown", (e) => {
    if (modal().hidden) return;
    if (e.key === "Escape") closePayment();
    if (e.key === "Tab") {
      const focusable = $$("button, input, [href]", $("#payCard")).filter((el) => el.offsetParent !== null && !el.disabled);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
}
