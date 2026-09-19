# Dokan - shop by chatting

Dokan is a small online electronics store where you do everything through a chat with **Arfat**, the shopping assistant. Ask for a product, add it to your cart, pay with bKash, Nagad or card, and even add new products to the store, all from the chat box. The product list and cart update live next to it.

Payments are a **demo**. No real money moves and nothing is sent to bKash, Nagad or a bank.

## Quick start

You need Python 3.9 or newer.

```bash
cd dokan-ai-shop
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

A virtual environment (`venv`) keeps the packages inside the project folder. Newer Ubuntu and Debian versions require this and refuse a plain `pip install` with an "externally-managed-environment" error. If `python3 -m venv` fails, run `sudo apt install python3-venv` first.

Next time, you only need:

```bash
cd dokan-ai-shop
source venv/bin/activate
python app.py
```

Open http://127.0.0.1:5000 in your browser.

### Turn on the AI assistant (optional)

Without a key the shop runs in **basic mode**: Ruhi understands a set of simple commands (listed below). To let Claude understand normal sentences:

1. Copy `.env.example` to `.env`
2. Put your Anthropic API key in it: `ANTHROPIC_API_KEY=sk-ant-...`
3. Restart `python app.py`

The badge at the top right of the page shows which mode is running. If the AI service ever fails, the shop falls back to basic mode automatically.

## What you can say to Arafat

With the AI on, just talk normally. Examples:

- "I need a phone under 40,000 taka with a good camera"
- "Add the second one to my cart"
- "Checkout"
- "I want to add a new product" (Ruhi asks for the name, category, price and stock)

In basic mode, use these commands:

| Say this | What happens |
| --- | --- |
| `best phone under 40000` / `show laptops` | Searches the catalog and shows product cards |
| `add PulseBuds Pro to cart` (`2x` for two) | Adds to the cart |
| `show my cart` / `remove PulseBuds Pro` | Shows or edits the cart |
| `checkout` | Opens the payment popup |
| `add product: Name, Category, Price, Stock` | Adds a new product to the store |

## Paying (demo)

Saying "checkout", or pressing **Pay** in the cart, opens the payment popup:

- **bKash / Nagad**: enter a mobile number (11 digits, like `01712345678`), then a 4 or 5 digit PIN.
- **Card**: card number, name, expiry (`MM/YY`, in the future) and a 3 or 4 digit CVV.

Any details that look valid are accepted. Press **Fill demo details** in the popup to fill them in automatically. After a short "processing" screen you get a success screen with an order ID and transaction ID, and a receipt appears in the chat. Stock is reduced and the cart is emptied.

PINs, CVVs and full card numbers are checked and discarded. They are never saved. Only a masked hint (like `017****678`) is stored with the order.

## Product pictures

Each product shows a line icon by default. To use a real picture instead:

1. Copy the picture into `static/images/` (for example `samsung-galaxy-s24.jpg`).
2. Open `data/products.json` and add an `"image"` line to that product:

```json
{"id": 4, "name": "Samsung Galaxy S24", "category": "Smartphone", "price": 105000, "rating": 4.6,
 "stock": 10, "icon": "phone", "image": "samsung-galaxy-s24.jpg", "specs": ["6.2\" Dynamic AMOLED 2X, 120Hz"]}
```

3. Stop the server (Ctrl+C) and start it again with `python app.py`. The server reads `products.json` once at startup, so changes to the file need a restart.
4. Refresh the browser (Ctrl+Shift+R if you still see the old picture).

You can also use a web address, like `"image": "https://example.com/phone.jpg"`. If the file name is wrong or the picture fails to load, Dokan quietly shows the icon instead. The picture appears in the product list, the cart and the chat cards. A square picture around 600 x 600 pixels, with a plain or transparent background, looks best.

## Adding products

Through the chat, as above. New products are saved to `data/products.json`, so they are still there after a restart. To add many at once, you can also edit that file directly, then restart the server. Each product looks like this:

```json
{"id": 40, "name": "PulseBuds Max", "category": "Audio", "price": 6500, "rating": 4.5,
 "stock": 25, "icon": "headphones", "specs": ["Active noise cancellation", "40hr battery"]}
```

Available icons: laptop, phone, tablet, buds, headphones, speaker, mic, watch, keyboard, mouse, hub, monitor, power, charger, camera, gamepad, home, router, storage, box.

Orders are saved to `data/orders.json`.

## Project layout

```
dokan-ai-shop/
├── app.py               Flask server and API routes
├── ai_agent.py          Claude chat: sends messages, runs tools, keeps history
├── fallback_agent.py    Basic-mode assistant (no API key needed)
├── tools.py             What the assistant can do: search, cart, checkout, add product
├── store.py             Products, carts and orders (saved as JSON)
├── payments.py          Demo payment checks
├── config.py            Settings and .env loader
├── requirements.txt
├── .env.example
├── data/
│   └── products.json    The catalog (48 products to start)
└── static/
    ├── index.html
    ├── css/             style.css (layout, catalog, cart), chat.css, payment.css
    └── js/
        ├── main.js      Starts everything
        ├── api.js       Talks to the Python server
        ├── state.js     Shared cart and product data
        ├── catalog.js   Search, categories, product grid
        ├── cart.js      Cart drawer
        ├── chat.js      Chat window
        ├── payment.js   Payment popup
        ├── icons.js     Product icons and category colors
        └── utils.js     Small helpers
```

## API (for reference)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/config` | Which mode is running |
| GET | `/api/products` | Catalog and categories |
| GET | `/api/cart` | Current cart |
| POST | `/api/cart/items` | Add `{product_id, quantity}` |
| PATCH / DELETE | `/api/cart/items/<id>` | Change quantity / remove |
| POST | `/api/chat` | Send `{message}`, get the reply, product cards and any UI action |
| POST | `/api/pay` | Demo payment, places the order |

Each browser gets its own cart and chat through a random ID sent in the `X-Session-Id` header.

## Before using this for real

This is a demo, so a few things are deliberately simple:

- Payments are simulated. A real shop needs the official bKash, Nagad or card gateway APIs, which handle PINs and card data on their side.
- Anyone can add products through the chat. A real store would put that behind an admin login.
- Carts and chats are kept in memory and reset when the server restarts.
- Orders and products are stored in JSON files. Use a database for anything with real traffic.
