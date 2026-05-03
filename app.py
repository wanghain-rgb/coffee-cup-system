from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from http.cookies import SimpleCookie
import html
import hmac
import mimetypes
import os
import sqlite3
import sys


APP_NAME = "CupFlow"
DB_PATH = os.path.join(os.path.dirname(__file__), "cupflow.sqlite3")
SECRET = os.environ.get("CUPFLOW_SECRET", "change-this-local-dev-secret")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
PUBLIC_PRODUCTS = [
    {
        "id": "SW8",
        "name": "Single Wall Kraft Coffee Cup",
        "size": "8 oz",
        "type": "Single Wall",
        "carton": "1000 cups per box",
        "lid": "90mm universal lid compatible",
    },
    {
        "id": "SW12",
        "name": "Single Wall Kraft Coffee Cup",
        "size": "12 oz",
        "type": "Single Wall",
        "carton": "1000 cups per box",
        "lid": "90mm universal lid compatible",
    },
    {
        "id": "SW16",
        "name": "Single Wall Kraft Coffee Cup",
        "size": "16 oz",
        "type": "Single Wall",
        "carton": "1000 cups per box",
        "lid": "90mm universal lid compatible",
    },
    {
        "id": "SWLID",
        "name": "90mm Plastic Lid",
        "size": "90mm lids",
        "type": "Single Wall compatible",
        "carton": "Box quantity as currently defined",
        "lid": "Fits 8 oz, 12 oz and 16 oz cups",
    },
    {
        "id": "DW8",
        "name": "Double Wall Kraft Coffee Cup",
        "size": "8 oz",
        "type": "Double Wall",
        "carton": "500 cups per box",
        "lid": "90mm universal lid compatible",
    },
    {
        "id": "DW12",
        "name": "Double Wall Kraft Coffee Cup",
        "size": "12 oz",
        "type": "Double Wall",
        "carton": "500 cups per box",
        "lid": "90mm universal lid compatible",
    },
    {
        "id": "DW16",
        "name": "Double Wall Kraft Coffee Cup",
        "size": "16 oz",
        "type": "Double Wall",
        "carton": "500 cups per box",
        "lid": "90mm universal lid compatible",
    },
    {
        "id": "DWLID",
        "name": "90mm Plastic Lid",
        "size": "90mm lids",
        "type": "Double Wall compatible",
        "carton": "Box quantity as currently defined",
        "lid": "Fits 8 oz, 12 oz and 16 oz cups",
    },
]


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def money(value):
    return f"${float(value or 0):,.2f}"


def esc(value):
    return html.escape("" if value is None else str(value))


def init_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                size TEXT NOT NULL,
                qty_per_carton INTEGER NOT NULL DEFAULT 1000,
                sell_price REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name TEXT NOT NULL,
                contact_name TEXT,
                email TEXT,
                phone TEXT,
                suburb TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS quote_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name TEXT NOT NULL,
                contact_name TEXT,
                email TEXT NOT NULL,
                phone TEXT,
                product_interest TEXT,
                monthly_volume TEXT,
                message TEXT,
                status TEXT NOT NULL DEFAULT 'New',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS purchase_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier TEXT NOT NULL,
                invoice_no TEXT,
                freight_cost REAL NOT NULL DEFAULT 0,
                batch_date TEXT NOT NULL DEFAULT CURRENT_DATE,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS purchase_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL REFERENCES purchase_batches(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id),
                qty_cartons INTEGER NOT NULL,
                unit_cost REAL NOT NULL,
                freight_alloc REAL NOT NULL DEFAULT 0,
                remaining_cartons INTEGER NOT NULL,
                landed_unit_cost REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sales_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL REFERENCES customers(id),
                order_date TEXT NOT NULL DEFAULT CURRENT_DATE,
                status TEXT NOT NULL DEFAULT 'Entered',
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS sales_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id),
                qty_cartons INTEGER NOT NULL,
                sell_price REAL NOT NULL,
                cost_price REAL NOT NULL,
                revenue REAL NOT NULL,
                cost REAL NOT NULL,
                gross_profit REAL NOT NULL
            );
            """
        )

        product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if product_count == 0:
            conn.executemany(
                """
                INSERT INTO products (sku, name, size, qty_per_carton, sell_price)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    ("CUP-8DW", "8oz Double Wall Coffee Cup", "8oz", 500, 72.00),
                    ("CUP-12SW", "12oz Single Wall Coffee Cup", "12oz", 1000, 89.00),
                    ("LID-80W", "White Sip Lid 80mm", "80mm", 1000, 42.00),
                ],
            )
        customer_count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        if customer_count == 0:
            conn.execute(
                """
                INSERT INTO customers (business_name, contact_name, email, phone, suburb, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "Sample Cafe",
                    "Alex Chen",
                    "orders@samplecafe.example",
                    "0400 000 000",
                    "Surry Hills",
                    "Demo customer for first sales order.",
                ),
            )


def sign(value):
    digest = hmac.new(SECRET.encode(), value.encode(), "sha256").hexdigest()
    return f"{value}.{digest}"


def verify(signed):
    if not signed or "." not in signed:
        return None
    value, digest = signed.rsplit(".", 1)
    expected = hmac.new(SECRET.encode(), value.encode(), "sha256").hexdigest()
    return value if hmac.compare_digest(digest, expected) else None


def layout(title, body, authed=False):
    admin_links = ""
    if authed:
        admin_links = """
        <a href="/admin">Dashboard</a>
        <a href="/admin/products">Products</a>
        <a href="/admin/customers">Customers</a>
        <a href="/admin/purchases">Purchases</a>
        <a href="/admin/inventory">Inventory</a>
        <a href="/admin/sales">Sales</a>
        <a href="/admin/quotes">Quotes</a>
        <a href="/admin/logout">Logout</a>
        """
    else:
        admin_links = '<a href="/admin/login">Admin</a>'
    return f"""<!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{esc(title)} | {APP_NAME}</title>
      <link rel="stylesheet" href="/static/styles.css">
    </head>
    <body>
      <header class="topbar">
        <a class="brand" href="/">
          <span class="brand-mark">A</span>
          <span><strong>AUREA</strong><small>Packaging Supply Pty Ltd</small></span>
        </a>
        <nav>
          <a href="/">View Products</a>
          <a href="/#contact">Contact Us</a>
          <a class="nav-cta" href="/quote">Request Quote</a>
          {admin_links}
        </nav>
      </header>
      <main>{body}</main>
      <footer>AUREA Packaging Supply Pty Ltd &middot; Melbourne, Australia &middot; info@aureapackaging.com.au</footer>
    </body>
    </html>"""


def table(headers, rows):
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = ""
    for row in rows:
        body += "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def product_options(conn):
    rows = conn.execute("SELECT id, sku, name FROM products WHERE active = 1 ORDER BY sku").fetchall()
    return "".join(f'<option value="{r["id"]}">{esc(r["sku"])} - {esc(r["name"])}</option>' for r in rows)


def customer_options(conn):
    rows = conn.execute("SELECT id, business_name FROM customers ORDER BY business_name").fetchall()
    return "".join(f'<option value="{r["id"]}">{esc(r["business_name"])}</option>' for r in rows)


def product_by_id():
    return {product["id"]: product for product in PUBLIC_PRODUCTS}


def quick_order_rows():
    rows = ""
    for product in PUBLIC_PRODUCTS:
        product_id = esc(product["id"])
        rows += f"""
        <article class="quick-order-item" data-product-row>
          <div>
            <strong>{esc(product["name"])}</strong>
            <span>{esc(product["size"])} &middot; {esc(product["type"])}</span>
          </div>
          <div>{esc(product["carton"])}</div>
          <div>{esc(product["lid"])}</div>
          <label>Boxes
            <input type="number" min="0" step="1" inputmode="numeric" value="0" data-product-id="{product_id}">
          </label>
          <label>Notes
            <input type="text" placeholder="Optional" data-product-note="{product_id}">
          </label>
        </article>
        """
    return rows


def parse_quick_order_items(items_value):
    products = product_by_id()
    selected = []
    for raw_item in (items_value or "").split("|"):
        parts = raw_item.split(":", 2)
        if len(parts) < 2:
            continue
        product = products.get(parts[0])
        if not product:
            continue
        try:
            boxes = int(parts[1])
        except ValueError:
            continue
        if boxes < 1:
            continue
        selected.append(
            {
                "product": product,
                "boxes": boxes,
                "note": parts[2].strip() if len(parts) > 2 else "",
            }
        )
    return selected


def quick_order_summary_text(selected):
    if not selected:
        return ""
    lines = []
    for item in selected:
        product = item["product"]
        note = f" - Note: {item['note']}" if item["note"] else ""
        lines.append(
            f"{product['name']} ({product['size']}, {product['type']}) - "
            f"{item['boxes']} boxes - {product['carton']}{note}"
        )
    return "\n".join(lines)


def quick_order_table(selected):
    if not selected:
        return """
        <div class="quote-empty">
          <strong>No products selected yet.</strong>
          <p>Please choose at least one product from Quick Order so we can prepare the right final price.</p>
          <a class="button primary" href="/#quick-order">Choose Products</a>
        </div>
        """
    rows = ""
    for item in selected:
        product = item["product"]
        note = f"<small>{esc(item['note'])}</small>" if item["note"] else ""
        rows += f"""
        <tr>
          <td>{esc(product["name"])}{note}</td>
          <td>{esc(product["size"])}</td>
          <td>{esc(product["type"])}</td>
          <td>{esc(item["boxes"])}</td>
        </tr>
        """
    return f"""
    <div class="quick-summary-table">
      <table>
        <thead>
          <tr><th>Product</th><th>Size</th><th>Type</th><th>Boxes requested</th></tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """


class App(BaseHTTPRequestHandler):
    def do_GET(self):
        self.route()

    def do_POST(self):
        self.route()

    def route(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/static/"):
            return self.static_file(path)
        routes = {
            "/": self.catalogue,
            "/quote": self.quote,
            "/admin/login": self.login,
            "/admin/logout": self.logout,
            "/admin": self.admin,
            "/admin/products": self.admin_products,
            "/admin/customers": self.admin_customers,
            "/admin/purchases": self.admin_purchases,
            "/admin/inventory": self.admin_inventory,
            "/admin/sales": self.admin_sales,
            "/admin/quotes": self.admin_quotes,
        }
        handler = routes.get(path)
        if not handler:
            return self.respond("Not found", 404)
        return handler()

    def is_authed(self):
        cookie = SimpleCookie(self.headers.get("Cookie"))
        token = cookie.get("cupflow_session")
        return verify(token.value if token else None) == "admin"

    def require_admin(self):
        if self.is_authed():
            return True
        self.redirect("/admin/login")
        return False

    def form(self):
        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length).decode("utf-8") if length else ""
        return {k: v[0].strip() for k, v in parse_qs(data).items()}

    def respond(self, content, status=200, content_type="text/html", cookies=None):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        if cookies:
            for cookie in cookies:
                self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def catalogue(self):
        quick_rows = quick_order_rows()
        body = f"""
        <section class="hero">
          <div class="hero-copy">
            <p class="eyebrow">AUREA Packaging Supply Pty Ltd</p>
            <h1>Premium Kraft Coffee Cups with Lids</h1>
            <p>Premium quality packaging solutions for cafes, takeaway shops and coffee businesses across Australia.</p>
            <div class="hero-actions">
              <a class="button primary" href="#quick-order">Start Quick Order</a>
              <a class="button ghost" href="#contact">Contact Us</a>
              <a class="button ghost" href="#products">View Products</a>
            </div>
          </div>
          <aside class="hero-badge">
            <span>Premium Insulation</span>
            Keeps drinks hot longer
          </aside>
        </section>

        <section class="benefits" aria-label="Key benefits">
          <article><strong>Sustainable</strong><span>Eco-friendly materials</span></article>
          <article><strong>Strong &amp; Reliable</strong><span>Durable and leak-proof design</span></article>
          <article><strong>Perfect Fit</strong><span>90mm universal lid compatible</span></article>
          <article><strong>Premium Insulation</strong><span>Keeps drinks hot longer</span></article>
        </section>

        <section id="products" class="section-head">
          <p class="eyebrow">B2B supply catalogue</p>
          <h2>Premium Kraft Coffee Cups</h2>
          <p>Indicative pricing is available on request. Final price is confirmed after reviewing quantity, delivery area and availability.</p>
        </section>

        <section class="pricing-grid">
          <article class="product-card featured">
            <p class="sku">Single Wall Kraft Coffee Cup</p>
            <h2>1000 cups in a box</h2>
            <div class="price-list">
              <div><span>8 oz</span><strong>Bulk pricing available</strong><a class="mini-quote" href="#quick-order">Add to Quick Order</a></div>
              <div><span>12 oz</span><strong>Best price based on quantity</strong><a class="mini-quote" href="#quick-order">Add to Quick Order</a></div>
              <div><span>16 oz</span><strong>Request final price</strong><a class="mini-quote" href="#quick-order">Add to Quick Order</a></div>
              <div><span>90mm lids</span><strong>Indicative pricing on request</strong><a class="mini-quote" href="#quick-order">Add to Quick Order</a></div>
            </div>
            <a class="button primary" href="#quick-order">Request Final Price</a>
          </article>

          <article class="product-card featured">
            <p class="sku">Double Wall Kraft Coffee Cup</p>
            <h2>500 cups in a box</h2>
            <div class="price-list">
              <div><span>8 oz</span><strong>Bulk pricing available</strong><a class="mini-quote" href="#quick-order">Add to Quick Order</a></div>
              <div><span>12 oz</span><strong>Best price based on quantity</strong><a class="mini-quote" href="#quick-order">Add to Quick Order</a></div>
              <div><span>16 oz</span><strong>Request final price</strong><a class="mini-quote" href="#quick-order">Add to Quick Order</a></div>
              <div><span>90mm lids</span><strong>Indicative pricing on request</strong><a class="mini-quote" href="#quick-order">Add to Quick Order</a></div>
            </div>
            <a class="button primary" href="#quick-order">Request Final Price</a>
          </article>

          <article class="promo-card">
            <p class="eyebrow">B2B final pricing</p>
            <h2>Build one quick order enquiry and we will confirm the best final price manually.</h2>
            <p>Final pricing depends on quantity, delivery area, customer type and current availability.</p>
            <a class="button ghost" href="#quick-order">Start Quick Order</a>
          </article>
        </section>

        <section id="quick-order" class="quick-order-section">
          <div class="section-head">
            <p class="eyebrow">Quick Order</p>
            <h2>Select Products Once</h2>
            <p>Enter the number of boxes you need, then submit one enquiry for manual final pricing.</p>
          </div>
          <form class="quick-order-form" action="/quote" method="get">
            <input type="hidden" name="items" id="quick_order_items">
            <div class="quick-order-head">
              <span>Product</span>
              <span>Carton quantity</span>
              <span>Lid compatibility</span>
              <span>Quantity</span>
              <span>Notes</span>
            </div>
            <div class="quick-order-list">
              {quick_rows}
            </div>
            <p class="quick-warning" id="quick_order_warning" role="alert">Please enter at least one box quantity before requesting a final price.</p>
            <div class="quick-order-actions">
              <span>Bulk pricing available. No payment or checkout.</span>
              <button class="button primary" type="submit">Request Final Price</button>
            </div>
          </form>
          <script>
            const quickOrderForm = document.querySelector(".quick-order-form");
            const quickOrderItems = document.getElementById("quick_order_items");
            const quickOrderWarning = document.getElementById("quick_order_warning");

            quickOrderForm.addEventListener("submit", (event) => {{
              const selected = [];
              document.querySelectorAll("[data-product-id]").forEach((input) => {{
                const boxes = Number.parseInt(input.value || "0", 10);
                if (boxes > 0) {{
                  const id = input.dataset.productId;
                  const noteInput = document.querySelector(`[data-product-note="${{id}}"]`);
                  const note = noteInput ? noteInput.value.trim().replace(/[|:]/g, " ") : "";
                  selected.push(`${{id}}:${{boxes}}:${{note}}`);
                }}
              }});

              if (!selected.length) {{
                event.preventDefault();
                quickOrderWarning.classList.add("show");
                quickOrderWarning.scrollIntoView({{ behavior: "smooth", block: "center" }});
                return;
              }}

              quickOrderWarning.classList.remove("show");
              quickOrderItems.value = selected.join("|");
            }});
          </script>
        </section>

        <section class="spec-section">
          <div class="section-head">
            <p class="eyebrow">Product specifications</p>
            <h2>Designed for a 90mm Universal Lid</h2>
          </div>

          <div class="spec-grid">
            <article class="spec-card">
              <h3>Single Wall Kraft Coffee Cup</h3>
              <dl>
                <div><dt>8 oz</dt><dd>90mm top &middot; 85.5mm height &middot; 56.5mm bottom</dd></div>
                <div><dt>12 oz</dt><dd>90mm top &middot; 116mm height &middot; 58mm bottom</dd></div>
                <div><dt>16 oz</dt><dd>90mm top &middot; 136mm height &middot; 58mm bottom</dd></div>
              </dl>
            </article>

            <article class="spec-card">
              <h3>Double Wall Kraft Coffee Cup</h3>
              <dl>
                <div><dt>8 oz</dt><dd>90mm top &middot; 85.5mm height &middot; 56.5mm bottom</dd></div>
                <div><dt>12 oz</dt><dd>90mm top &middot; 116mm height &middot; 58mm bottom</dd></div>
                <div><dt>16 oz</dt><dd>90mm top &middot; 136mm height &middot; 58mm bottom</dd></div>
              </dl>
            </article>

            <article class="spec-card lid-card">
              <h3>Lid</h3>
              <dl>
                <div><dt>Type</dt><dd>90mm plastic lid</dd></div>
                <div><dt>Height</dt><dd>23mm</dd></div>
                <div><dt>Fit</dt><dd>90mm universal lid</dd></div>
              </dl>
            </article>
          </div>
        </section>

        <section id="contact" class="contact-section">
          <div>
            <p class="eyebrow">Your trusted partner</p>
            <h2>Premium packaging supply across Australia</h2>
            <p>Speak with Stone Wang for product availability, bulk carton pricing and cafe supply requirements.</p>
          </div>
          <div class="contact-card">
            <strong>Stone Wang</strong>
            <a href="tel:0497278099">0497278099</a>
            <a href="mailto:info@aureapackaging.com.au">info@aureapackaging.com.au</a>
            <a href="https://www.aureapackaging.com.au">www.aureapackaging.com.au</a>
            <span>Melbourne, Australia</span>
          </div>
        </section>
        """
        self.respond(layout("Product Catalogue", body, self.is_authed()))

    def quote(self):
        if self.command == "POST":
            f = self.form()
            order_summary = f.get("order_summary") or f.get("product_interest") or ""
            delivery = f.get("delivery_suburb") or ""
            customer_message = f.get("message") or ""
            message_parts = []
            if order_summary:
                message_parts.append(f"Selected products:\n{order_summary}")
            if delivery:
                message_parts.append(f"Delivery suburb/postcode: {delivery}")
            if customer_message:
                message_parts.append(f"Customer message:\n{customer_message}")
            saved_message = "\n\n".join(message_parts) if message_parts else customer_message
            with db() as conn:
                conn.execute(
                    """
                    INSERT INTO quote_requests
                    (business_name, contact_name, email, phone, product_interest, monthly_volume, message)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f.get("business_name"),
                        f.get("contact_name"),
                        f.get("email"),
                        f.get("phone"),
                        order_summary,
                        f.get("monthly_volume"),
                        saved_message,
                    ),
                )
            body = """
            <section class="panel narrow">
              <h1>Thanks, your quote request has been received.</h1>
              <p>Admin users can review it in the quote request inbox.</p>
              <a class="button" href="/">Back to catalogue</a>
            </section>
            """
            return self.respond(layout("Quote Sent", body, self.is_authed()))
        query = parse_qs(urlparse(self.path).query)
        selected = parse_quick_order_items(query.get("items", [""])[0])
        summary_text = quick_order_summary_text(selected)
        summary_table = quick_order_table(selected)
        total_boxes = sum(item["boxes"] for item in selected)
        disabled = "" if selected else "disabled"
        body = f"""
        <section class="panel narrow quote-panel">
          <p class="eyebrow">AUREA Packaging Supply Pty Ltd</p>
          <h1>Quick Order Enquiry</h1>
          <div class="quote-summary">
            <h2>Selected products</h2>
            {summary_table}
            <p class="final-price-note">Final price will be confirmed based on quantity, delivery area and availability.</p>
          </div>
          <form method="post" class="form quote-form">
            <textarea hidden name="product_interest">{esc(summary_text)}</textarea>
            <textarea hidden name="order_summary">{esc(summary_text)}</textarea>
            <input type="hidden" name="monthly_volume" value="{esc(f'{total_boxes} boxes requested' if total_boxes else '')}">
            <div class="quote-detail-grid">
              <label>Business name<input name="business_name" required {disabled}></label>
              <label>Contact person<input name="contact_name" required {disabled}></label>
              <label>Phone<input name="phone" required {disabled}></label>
              <label>Email<input name="email" type="email" required {disabled}></label>
              <label>Delivery suburb / postcode<input name="delivery_suburb" required {disabled}></label>
            </div>
            <label>Message / special request<textarea name="message" rows="4" placeholder="Delivery timing, invoice details, or any special requirements" {disabled}></textarea></label>
            <button class="button primary" type="submit" {disabled}>Submit Quick Order Enquiry</button>
          </form>
        </section>
        """
        self.respond(layout("Request Quote", body, self.is_authed()))

    def login(self):
        if self.command == "POST":
            f = self.form()
            if f.get("username") == ADMIN_USER and f.get("password") == ADMIN_PASSWORD:
                cookie = f"cupflow_session={sign('admin')}; HttpOnly; SameSite=Lax; Path=/"
                self.send_response(303)
                self.send_header("Location", "/admin")
                self.send_header("Set-Cookie", cookie)
                self.end_headers()
                return
            error = '<p class="alert">Invalid login. Try admin / admin123 for local demo.</p>'
        else:
            error = ""
        body = f"""
        <section class="panel narrow">
          <h1>Admin Login</h1>
          {error}
          <form method="post" class="form">
            <label>Username<input name="username" required value="admin"></label>
            <label>Password<input name="password" type="password" required></label>
            <button class="button primary" type="submit">Login</button>
          </form>
        </section>
        """
        self.respond(layout("Admin Login", body, False))

    def logout(self):
        self.respond(
            layout("Logged out", '<section class="panel narrow"><h1>Logged out</h1><a class="button" href="/">Home</a></section>'),
            cookies=["cupflow_session=; Max-Age=0; Path=/"],
        )

    def admin(self):
        if not self.require_admin():
            return
        with db() as conn:
            stats = {
                "Products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
                "Customers": conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
                "Quote requests": conn.execute("SELECT COUNT(*) FROM quote_requests").fetchone()[0],
                "Sales orders": conn.execute("SELECT COUNT(*) FROM sales_orders").fetchone()[0],
            }
            gp = conn.execute("SELECT COALESCE(SUM(gross_profit),0) FROM sales_lines").fetchone()[0]
        stat_cards = "".join(f'<div class="stat"><strong>{esc(v)}</strong><span>{esc(k)}</span></div>' for k, v in stats.items())
        body = f"""
        <section class="section-head"><h1>Admin Dashboard</h1><p>Small-business controls for products, customers, stock and gross profit.</p></section>
        <section class="stats">{stat_cards}<div class="stat"><strong>{money(gp)}</strong><span>Total gross profit</span></div></section>
        <section class="panel">
          <h2>Workflow</h2>
          <p>Create product masters, add purchase batches to stock, enter sales orders, and use FIFO landed cost to calculate gross profit.</p>
        </section>
        """
        self.respond(layout("Admin Dashboard", body, True))

    def admin_products(self):
        if not self.require_admin():
            return
        if self.command == "POST":
            f = self.form()
            with db() as conn:
                conn.execute(
                    """
                    INSERT INTO products (sku, name, size, qty_per_carton, sell_price, active)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f.get("sku"),
                        f.get("name"),
                        f.get("size"),
                        int(f.get("qty_per_carton") or 0),
                        float(f.get("sell_price") or 0),
                        1 if f.get("active") == "on" else 0,
                    ),
                )
            return self.redirect("/admin/products")
        with db() as conn:
            rows = conn.execute("SELECT * FROM products ORDER BY sku").fetchall()
        product_rows = [
            [esc(r["sku"]), esc(r["name"]), esc(r["size"]), esc(r["qty_per_carton"]), money(r["sell_price"]), "Yes" if r["active"] else "No"]
            for r in rows
        ]
        body = f"""
        <section class="section-head"><h1>Product Master</h1><p>Maintain cup and lid SKUs, carton sizes and default sell prices.</p></section>
        {table(["SKU", "Name", "Size", "Qty/carton", "Sell price", "Active"], product_rows)}
        <section class="panel">
          <h2>Add product</h2>
          <form method="post" class="form grid-form">
            <label>SKU<input name="sku" required></label>
            <label>Name<input name="name" required></label>
            <label>Size<input name="size" required></label>
            <label>Qty per carton<input name="qty_per_carton" type="number" required></label>
            <label>Sell price<input name="sell_price" type="number" step="0.01" required></label>
            <label class="check"><input name="active" type="checkbox" checked> Active</label>
            <button class="button primary" type="submit">Add product</button>
          </form>
        </section>
        """
        self.respond(layout("Product Master", body, True))

    def admin_customers(self):
        if not self.require_admin():
            return
        if self.command == "POST":
            f = self.form()
            with db() as conn:
                conn.execute(
                    """
                    INSERT INTO customers (business_name, contact_name, email, phone, suburb, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (f.get("business_name"), f.get("contact_name"), f.get("email"), f.get("phone"), f.get("suburb"), f.get("notes")),
                )
            return self.redirect("/admin/customers")
        with db() as conn:
            rows = conn.execute("SELECT * FROM customers ORDER BY business_name").fetchall()
        customer_rows = [
            [esc(r["business_name"]), esc(r["contact_name"]), esc(r["email"]), esc(r["phone"]), esc(r["suburb"]), esc(r["notes"])]
            for r in rows
        ]
        body = f"""
        <section class="section-head"><h1>Customer Master</h1><p>Cafe and takeaway customer records.</p></section>
        {table(["Business", "Contact", "Email", "Phone", "Suburb", "Notes"], customer_rows)}
        <section class="panel">
          <h2>Add customer</h2>
          <form method="post" class="form grid-form">
            <label>Business name<input name="business_name" required></label>
            <label>Contact name<input name="contact_name"></label>
            <label>Email<input name="email" type="email"></label>
            <label>Phone<input name="phone"></label>
            <label>Suburb<input name="suburb"></label>
            <label>Notes<textarea name="notes" rows="3"></textarea></label>
            <button class="button primary" type="submit">Add customer</button>
          </form>
        </section>
        """
        self.respond(layout("Customer Master", body, True))

    def admin_purchases(self):
        if not self.require_admin():
            return
        if self.command == "POST":
            f = self.form()
            qty = int(f.get("qty_cartons") or 0)
            unit_cost = float(f.get("unit_cost") or 0)
            freight = float(f.get("freight_cost") or 0)
            landed = unit_cost + (freight / qty if qty else 0)
            with db() as conn:
                cur = conn.execute(
                    "INSERT INTO purchase_batches (supplier, invoice_no, freight_cost, batch_date, notes) VALUES (?, ?, ?, ?, ?)",
                    (f.get("supplier"), f.get("invoice_no"), freight, f.get("batch_date"), f.get("notes")),
                )
                conn.execute(
                    """
                    INSERT INTO purchase_lines
                    (batch_id, product_id, qty_cartons, unit_cost, freight_alloc, remaining_cartons, landed_unit_cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (cur.lastrowid, int(f.get("product_id")), qty, unit_cost, freight, qty, landed),
                )
            return self.redirect("/admin/purchases")
        with db() as conn:
            opts = product_options(conn)
            rows = conn.execute(
                """
                SELECT b.batch_date, b.supplier, b.invoice_no, p.sku, p.name, l.qty_cartons,
                       l.remaining_cartons, l.unit_cost, l.freight_alloc, l.landed_unit_cost
                FROM purchase_lines l
                JOIN purchase_batches b ON b.id = l.batch_id
                JOIN products p ON p.id = l.product_id
                ORDER BY b.batch_date DESC, l.id DESC
                """
            ).fetchall()
        purchase_rows = [
            [
                esc(r["batch_date"]),
                esc(r["supplier"]),
                esc(r["invoice_no"]),
                esc(r["sku"]),
                esc(r["name"]),
                esc(r["qty_cartons"]),
                esc(r["remaining_cartons"]),
                money(r["unit_cost"]),
                money(r["freight_alloc"]),
                money(r["landed_unit_cost"]),
            ]
            for r in rows
        ]
        body = f"""
        <section class="section-head"><h1>Purchase Batch Management</h1><p>Record inbound cartons and allocate freight into landed unit cost.</p></section>
        {table(["Date", "Supplier", "Invoice", "SKU", "Product", "Purchased", "Remaining", "Unit cost", "Freight", "Landed cost"], purchase_rows)}
        <section class="panel">
          <h2>Add purchase batch</h2>
          <form method="post" class="form grid-form">
            <label>Supplier<input name="supplier" required></label>
            <label>Invoice no<input name="invoice_no"></label>
            <label>Date<input name="batch_date" type="date" required></label>
            <label>Product<select name="product_id" required>{opts}</select></label>
            <label>Qty cartons<input name="qty_cartons" type="number" min="1" required></label>
            <label>Unit cost/carton<input name="unit_cost" type="number" step="0.01" required></label>
            <label>Freight cost<input name="freight_cost" type="number" step="0.01" value="0"></label>
            <label>Notes<textarea name="notes" rows="3"></textarea></label>
            <button class="button primary" type="submit">Receive stock</button>
          </form>
        </section>
        """
        self.respond(layout("Purchase Batches", body, True))

    def admin_inventory(self):
        if not self.require_admin():
            return
        with db() as conn:
            rows = conn.execute(
                """
                SELECT p.sku, p.name, COALESCE(SUM(l.remaining_cartons),0) AS cartons,
                       COALESCE(SUM(l.remaining_cartons * l.landed_unit_cost),0) AS stock_value
                FROM products p
                LEFT JOIN purchase_lines l ON l.product_id = p.id
                GROUP BY p.id
                ORDER BY p.sku
                """
            ).fetchall()
        inv_rows = [[esc(r["sku"]), esc(r["name"]), esc(r["cartons"]), money(r["stock_value"])] for r in rows]
        body = f"""
        <section class="section-head"><h1>Inventory Balance</h1><p>On-hand cartons and stock value from remaining purchase batches.</p></section>
        {table(["SKU", "Product", "On hand cartons", "Stock value"], inv_rows)}
        """
        self.respond(layout("Inventory Balance", body, True))

    def admin_sales(self):
        if not self.require_admin():
            return
        message = ""
        if self.command == "POST":
            f = self.form()
            product_id = int(f.get("product_id"))
            qty = int(f.get("qty_cartons") or 0)
            sell_price = float(f.get("sell_price") or 0)
            with db() as conn:
                stock = conn.execute(
                    "SELECT COALESCE(SUM(remaining_cartons),0) FROM purchase_lines WHERE product_id = ?",
                    (product_id,),
                ).fetchone()[0]
                if qty <= 0 or stock < qty:
                    message = '<p class="alert">Not enough stock for this sales order.</p>'
                else:
                    cost_total = self.allocate_fifo(conn, product_id, qty)
                    revenue = qty * sell_price
                    cur = conn.execute(
                        "INSERT INTO sales_orders (customer_id, order_date, status, notes) VALUES (?, ?, ?, ?)",
                        (int(f.get("customer_id")), f.get("order_date"), "Entered", f.get("notes")),
                    )
                    conn.execute(
                        """
                        INSERT INTO sales_lines
                        (order_id, product_id, qty_cartons, sell_price, cost_price, revenue, cost, gross_profit)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (cur.lastrowid, product_id, qty, sell_price, cost_total / qty, revenue, cost_total, revenue - cost_total),
                    )
                    return self.redirect("/admin/sales")
        with db() as conn:
            product_opts = product_options(conn)
            customer_opts = customer_options(conn)
            default_sell = conn.execute("SELECT sell_price FROM products ORDER BY sku LIMIT 1").fetchone()
            rows = conn.execute(
                """
                SELECT o.order_date, c.business_name, p.sku, p.name, l.qty_cartons,
                       l.sell_price, l.cost_price, l.revenue, l.cost, l.gross_profit
                FROM sales_lines l
                JOIN sales_orders o ON o.id = l.order_id
                JOIN customers c ON c.id = o.customer_id
                JOIN products p ON p.id = l.product_id
                ORDER BY o.order_date DESC, o.id DESC
                """
            ).fetchall()
        sales_rows = [
            [
                esc(r["order_date"]),
                esc(r["business_name"]),
                esc(r["sku"]),
                esc(r["name"]),
                esc(r["qty_cartons"]),
                money(r["sell_price"]),
                money(r["cost_price"]),
                money(r["revenue"]),
                money(r["cost"]),
                money(r["gross_profit"]),
            ]
            for r in rows
        ]
        body = f"""
        <section class="section-head"><h1>Sales Order Entry</h1><p>Create one-line sales orders and calculate gross profit from FIFO batch cost.</p></section>
        {message}
        {table(["Date", "Customer", "SKU", "Product", "Qty", "Sell/carton", "Cost/carton", "Revenue", "Cost", "Gross profit"], sales_rows)}
        <section class="panel">
          <h2>Add sales order</h2>
          <form method="post" class="form grid-form">
            <label>Customer<select name="customer_id" required>{customer_opts}</select></label>
            <label>Date<input name="order_date" type="date" required></label>
            <label>Product<select name="product_id" required>{product_opts}</select></label>
            <label>Qty cartons<input name="qty_cartons" type="number" min="1" required></label>
            <label>Sell price/carton<input name="sell_price" type="number" step="0.01" value="{esc(default_sell[0] if default_sell else 0)}" required></label>
            <label>Notes<textarea name="notes" rows="3"></textarea></label>
            <button class="button primary" type="submit">Create order</button>
          </form>
        </section>
        """
        self.respond(layout("Sales Orders", body, True))

    def allocate_fifo(self, conn, product_id, qty):
        remaining = qty
        cost_total = 0.0
        rows = conn.execute(
            """
            SELECT id, remaining_cartons, landed_unit_cost
            FROM purchase_lines
            WHERE product_id = ? AND remaining_cartons > 0
            ORDER BY id
            """,
            (product_id,),
        ).fetchall()
        for row in rows:
            if remaining <= 0:
                break
            take = min(remaining, row["remaining_cartons"])
            cost_total += take * row["landed_unit_cost"]
            conn.execute(
                "UPDATE purchase_lines SET remaining_cartons = remaining_cartons - ? WHERE id = ?",
                (take, row["id"]),
            )
            remaining -= take
        if remaining:
            raise ValueError("Insufficient stock")
        return cost_total

    def admin_quotes(self):
        if not self.require_admin():
            return
        with db() as conn:
            rows = conn.execute("SELECT * FROM quote_requests ORDER BY created_at DESC").fetchall()
        quote_rows = [
            [
                esc(r["created_at"]),
                esc(r["status"]),
                esc(r["business_name"]),
                esc(r["contact_name"]),
                esc(r["email"]),
                esc(r["phone"]),
                esc(r["product_interest"]),
                esc(r["monthly_volume"]),
                esc(r["message"]),
            ]
            for r in rows
        ]
        body = f"""
        <section class="section-head"><h1>Quote Requests</h1><p>Inbox for public website enquiries.</p></section>
        {table(["Created", "Status", "Business", "Contact", "Email", "Phone", "Products", "Volume", "Message"], quote_rows)}
        """
        self.respond(layout("Quote Requests", body, True))

    def static_file(self, path):
        rel = path.removeprefix("/static/").replace("/", os.sep)
        static_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
        file_path = os.path.abspath(os.path.join(static_root, rel))
        if os.path.commonpath([static_root, file_path]) != static_root or not os.path.isfile(file_path):
            return self.respond("Not found", 404, content_type="text/plain")
        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        with open(file_path, "rb") as f:
            self.wfile.write(f.read())

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

def main():
    init_db()
    port = int(os.environ.get("PORT", "8000"))
    host = "0.0.0.0"
    server = ThreadingHTTPServer((host, port), App)
    print(f"{APP_NAME} running at http://{host}:{port}")
    print("Admin login: admin / admin123")
    server.serve_forever()

if __name__ == "__main__":
    main()
