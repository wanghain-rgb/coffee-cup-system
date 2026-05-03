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
        <a class="brand" href="/">{APP_NAME}</a>
        <nav>
          <a href="/">Catalogue</a>
          <a href="/quote">Request Quote</a>
          {admin_links}
        </nav>
      </header>
      <main>{body}</main>
      <footer>Disposable coffee cup sales and inventory MVP for Australian B2B suppliers.</footer>
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
        with db() as conn:
            products = conn.execute(
                "SELECT sku, name, size, qty_per_carton, sell_price FROM products WHERE active = 1 ORDER BY sku"
            ).fetchall()
        cards = ""
        for p in products:
            cards += f"""
            <article class="product-card">
              <div class="sku">{esc(p["sku"])}</div>
              <h2>{esc(p["name"])}</h2>
              <dl>
                <div><dt>Size</dt><dd>{esc(p["size"])}</dd></div>
                <div><dt>Carton</dt><dd>{esc(p["qty_per_carton"])} units</dd></div>
                <div><dt>Indicative</dt><dd>{money(p["sell_price"])} / carton</dd></div>
              </dl>
            </article>
            """
        body = f"""
        <section class="hero">
          <div>
            <p class="eyebrow">Australia B2B coffee cup supply</p>
            <h1>Disposable cups, lids and carton pricing for cafes.</h1>
            <p>Browse core products and request a quote based on your expected monthly volume.</p>
            <a class="button primary" href="/quote">Request a quote</a>
          </div>
        </section>
        <section class="section-head">
          <h2>Product Catalogue</h2>
          <p>Simple public catalogue for cafes and takeaway shops.</p>
        </section>
        <section class="grid">{cards}</section>
        """
        self.respond(layout("Product Catalogue", body, self.is_authed()))

    def quote(self):
        if self.command == "POST":
            f = self.form()
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
                        f.get("product_interest"),
                        f.get("monthly_volume"),
                        f.get("message"),
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
        body = """
        <section class="panel narrow">
          <h1>Request a Quote</h1>
          <form method="post" class="form">
            <label>Business name<input name="business_name" required></label>
            <label>Contact name<input name="contact_name"></label>
            <label>Email<input name="email" type="email" required></label>
            <label>Phone<input name="phone"></label>
            <label>Product interest<input name="product_interest" placeholder="8oz cups, 12oz cups, lids"></label>
            <label>Monthly volume<input name="monthly_volume" placeholder="e.g. 10 cartons per month"></label>
            <label>Message<textarea name="message" rows="4"></textarea></label>
            <button class="button primary" type="submit">Send request</button>
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
    server = ThreadingHTTPServer(("127.0.0.1", port), App)
    print(f"{APP_NAME} running at http://127.0.0.1:{port}")
    print("Admin login: admin / admin123")
    server.serve_forever()


if __name__ == "__main__":
    main()
