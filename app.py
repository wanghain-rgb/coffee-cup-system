from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from http.cookies import SimpleCookie
from datetime import date, timedelta
from email.message import EmailMessage
import html
import hmac
import mimetypes
import os
import smtplib
import sqlite3
import sys
import traceback

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None


APP_NAME = "CupFlow"
# Render's normal/free filesystem is ephemeral. If this SQLite file is stored
# there, business data can be lost on redeploy/restart/spin-down. Use
# PostgreSQL or a Render persistent disk for production data.
DB_PATH = os.path.join(os.path.dirname(__file__), "cupflow.sqlite3")
DATABASE_URL = os.environ.get("DATABASE_URL")
SECRET = os.environ.get("CUPFLOW_SECRET", "change-this-local-dev-secret")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
SITE_URL = "https://aureapackaging.com.au"
SEO_TITLE = "Premium Coffee Cups & Packaging Supplies Melbourne | AUREA Packaging"
SEO_DESCRIPTION = (
    "Bulk coffee cups, lids, takeaway packaging and cafe supplies in Melbourne. "
    "Fast delivery, reliable supply and competitive pricing for cafes and takeaway shops."
)
SEO_IMAGE = f"{SITE_URL}/static/hero-cups.png"
PUBLIC_PRODUCTS = [
    {
        "id": "SW8",
        "name": "Single Wall Kraft Coffee Cup",
        "size": "8 oz",
        "type": "Single Wall",
        "carton": "1000 cups per box",
        "lid": "90mm universal lid compatible",
        "image": "/static/single-wall-8oz.png",
        "quote_price": 49.90,
    },
    {
        "id": "SW12",
        "name": "Single Wall Kraft Coffee Cup",
        "size": "12 oz",
        "type": "Single Wall",
        "carton": "1000 cups per box",
        "lid": "90mm universal lid compatible",
        "image": "/static/single-wall-12oz.png",
        "quote_price": 61.90,
    },
    {
        "id": "SW16",
        "name": "Single Wall Kraft Coffee Cup",
        "size": "16 oz",
        "type": "Single Wall",
        "carton": "1000 cups per box",
        "lid": "90mm universal lid compatible",
        "image": "/static/single-wall-16oz.png",
        "quote_price": 79.90,
    },
    {
        "id": "SWLID",
        "name": "90mm Plastic Lid",
        "size": "90mm lids",
        "type": "Single Wall compatible",
        "carton": "1000 lids per box",
        "lid": "Fits 8 oz, 12 oz and 16 oz cups",
        "image": "/static/lid-90mm.png",
        "quote_price": 39.90,
    },
    {
        "id": "DW8",
        "name": "Double Wall Kraft Coffee Cup",
        "size": "8 oz",
        "type": "Double Wall",
        "carton": "1000 cups per box",
        "lid": "90mm universal lid compatible",
        "image": "/static/double-wall-8oz.png",
        "quote_price": 45.00,
    },
    {
        "id": "DW12",
        "name": "Double Wall Kraft Coffee Cup",
        "size": "12 oz",
        "type": "Double Wall",
        "carton": "1000 cups per box",
        "lid": "90mm universal lid compatible",
        "image": "/static/double-wall-12oz.png",
        "quote_price": 50.00,
    },
    {
        "id": "DW16",
        "name": "Double Wall Kraft Coffee Cup",
        "size": "16 oz",
        "type": "Double Wall",
        "carton": "1000 cups per box",
        "lid": "90mm universal lid compatible",
        "image": "/static/double-wall-16oz.png",
        "quote_price": 60.00,
    },
    {
        "id": "DWLID",
        "name": "90mm Plastic Lid",
        "size": "90mm lids",
        "type": "Double Wall compatible",
        "carton": "1000 lids per box",
        "lid": "Fits 8 oz, 12 oz and 16 oz cups",
        "image": "/static/lid-90mm.png",
        "quote_price": 45.00,
    },
]


class DbCursor:
    def __init__(self, cursor, lastrowid=None):
        self.cursor = cursor
        self.lastrowid = lastrowid if lastrowid is not None else getattr(cursor, "lastrowid", None)
        self.rowcount = getattr(cursor, "rowcount", -1)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()


class DbConnection:
    RETURNING_TABLES = {"quote_requests", "purchase_batches", "purchase_orders", "sales_orders", "invoices"}

    def __init__(self):
        self.is_postgres = bool(DATABASE_URL)
        if self.is_postgres:
            if psycopg2 is None:
                raise RuntimeError("DATABASE_URL is set but psycopg2 is not installed.")
            self.conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
        else:
            self.conn = sqlite3.connect(DB_PATH)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.conn.close()

    def _sql(self, sql):
        return sql.replace("?", "%s") if self.is_postgres else sql

    def _insert_returning_sql(self, sql):
        if not self.is_postgres or "RETURNING" in sql.upper():
            return sql
        cleaned = sql.strip()
        upper = cleaned.upper()
        if not upper.startswith("INSERT INTO "):
            return sql
        table = cleaned.split()[2].strip('"')
        if table in self.RETURNING_TABLES:
            return f"{sql.rstrip()} RETURNING id"
        return sql

    def execute(self, sql, params=()):
        cursor = self.conn.cursor()
        sql = self._insert_returning_sql(self._sql(sql))
        cursor.execute(sql, params)
        lastrowid = None
        if self.is_postgres and "RETURNING id" in sql:
            row = cursor.fetchone()
            lastrowid = row["id"] if row else None
        return DbCursor(cursor, lastrowid)

    def executemany(self, sql, seq):
        cursor = self.conn.cursor()
        cursor.executemany(self._sql(sql), seq)
        return DbCursor(cursor)

    def executescript(self, script):
        if not self.is_postgres:
            return self.conn.executescript(script)
        cursor = self.conn.cursor()
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
        return cursor

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()


def db():
    return DbConnection()


def money(value):
    return f"${float(value or 0):,.2f}"


def display_date(value):
    if not value:
        return ""
    try:
        return date.fromisoformat(str(value)).strftime("%d/%m/%Y")
    except ValueError:
        return str(value)


def esc(value):
    return html.escape("" if value is None else str(value))


def ensure_column(conn, table, column, ddl):
    if conn.is_postgres:
        existing = {
            row["column_name"]
            for row in conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = ?
                """,
                (table,),
            ).fetchall()
        }
    else:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


SQLITE_SCHEMA = """
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

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_code TEXT UNIQUE NOT NULL,
    supplier_name TEXT NOT NULL,
    abn TEXT,
    contact_person TEXT,
    email TEXT,
    phone TEXT,
    address_line_1 TEXT,
    address_line_2 TEXT,
    suburb TEXT,
    state TEXT,
    postcode TEXT,
    country TEXT,
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1
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

CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    order_date TEXT NOT NULL DEFAULT CURRENT_DATE,
    status TEXT NOT NULL DEFAULT 'Draft',
    subtotal_ex_gst REAL NOT NULL DEFAULT 0,
    gst_amount REAL NOT NULL DEFAULT 0,
    total_inc_gst REAL NOT NULL DEFAULT 0,
    notes TEXT,
    confirmed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchase_order_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_order_id INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    product_code TEXT,
    description TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 0,
    unit_price_ex_gst REAL NOT NULL DEFAULT 0,
    gst_amount REAL NOT NULL DEFAULT 0,
    subtotal_ex_gst REAL NOT NULL DEFAULT 0,
    total_inc_gst REAL NOT NULL DEFAULT 0
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

CREATE TABLE IF NOT EXISTS company_master (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    company_name TEXT NOT NULL DEFAULT 'AUREA Packaging Supply Pty Ltd',
    abn TEXT,
    address TEXT,
    phone TEXT,
    email TEXT,
    website TEXT,
    bank_name TEXT,
    account_name TEXT,
    bsb TEXT,
    account_number TEXT,
    payment_instructions TEXT
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    sales_order_id INTEGER REFERENCES sales_orders(id),
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    customer_business_name TEXT,
    customer_abn TEXT,
    billing_address TEXT,
    shipping_address TEXT,
    issue_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Draft',
    subtotal_ex_gst REAL NOT NULL DEFAULT 0,
    gst_amount REAL NOT NULL DEFAULT 0,
    total_inc_gst REAL NOT NULL DEFAULT 0,
    total_paid REAL NOT NULL DEFAULT 0,
    balance_due REAL NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoice_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id),
    product_code TEXT,
    description TEXT NOT NULL,
    size TEXT,
    product_type TEXT,
    carton_quantity INTEGER,
    quantity REAL NOT NULL DEFAULT 0,
    unit_price_ex_gst REAL NOT NULL DEFAULT 0,
    tax_type TEXT NOT NULL DEFAULT 'GST',
    subtotal_ex_gst REAL NOT NULL DEFAULT 0,
    gst_amount REAL NOT NULL DEFAULT 0,
    total_inc_gst REAL NOT NULL DEFAULT 0
);
"""

POSTGRES_SCHEMA = SQLITE_SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")


def init_db():
    with db() as conn:
        conn.executescript(POSTGRES_SCHEMA if conn.is_postgres else SQLITE_SCHEMA)
        ensure_column(conn, "customers", "abn", "abn TEXT")
        ensure_column(conn, "customers", "billing_address", "billing_address TEXT")
        ensure_column(conn, "customers", "shipping_address", "shipping_address TEXT")
        ensure_column(conn, "products", "product_type", "product_type TEXT")
        ensure_column(conn, "products", "tax_type", "tax_type TEXT NOT NULL DEFAULT 'GST'")
        ensure_column(conn, "products", "barcode", "barcode TEXT")
        ensure_column(conn, "products", "stock_qty", "stock_qty REAL NOT NULL DEFAULT 0")
        ensure_column(conn, "products", "avg_cost", "avg_cost REAL NOT NULL DEFAULT 0")
        ensure_column(conn, "invoices", "sales_order_id", "sales_order_id INTEGER REFERENCES sales_orders(id)")
        ensure_column(conn, "invoices", "customer_business_name", "customer_business_name TEXT")
        ensure_column(conn, "invoices", "customer_abn", "customer_abn TEXT")
        ensure_column(conn, "invoices", "billing_address", "billing_address TEXT")
        ensure_column(conn, "invoices", "shipping_address", "shipping_address TEXT")

        if conn.is_postgres:
            conn.execute(
                """
                INSERT INTO company_master
                (id, company_name, phone, email, website, address, payment_instructions)
                VALUES (1, 'AUREA Packaging Supply Pty Ltd', '0497278099',
                        'info@aureapackaging.com.au', 'https://aureapackaging.com.au',
                        'Melbourne, Australia', 'Payment terms: To be confirmed.')
                ON CONFLICT (id) DO NOTHING
                """
            )
        else:
            conn.execute(
                """
                INSERT OR IGNORE INTO company_master
                (id, company_name, phone, email, website, address, payment_instructions)
                VALUES (1, 'AUREA Packaging Supply Pty Ltd', '0497278099',
                        'info@aureapackaging.com.au', 'https://aureapackaging.com.au',
                        'Melbourne, Australia', 'Payment terms: To be confirmed.')
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


def layout(title, body, authed=False, noindex=False):
    admin_links = ""
    if authed:
        admin_links = """
        <a href="/admin">Dashboard</a>
        <a href="/admin/products">Products</a>
        <a href="/admin/customers">Customers</a>
        <a href="/admin/suppliers">Suppliers</a>
        <a href="/admin/company">Company</a>
        <a href="/admin/invoices">Invoices</a>
        <a href="/admin/purchase-orders">Purchase Orders</a>
        <a href="/admin/purchases">Purchases</a>
        <a href="/admin/inventory">Inventory</a>
        <a href="/admin/sales">Sales</a>
        <a href="/admin/quotes">Quotes</a>
        <a href="/admin/logout">Logout</a>
        """
    else:
        admin_links = '<a href="/admin/login">Admin</a>'
    page_title = SEO_TITLE if title == "Product Catalogue" else f"{esc(title)} | AUREA Packaging"
    robots_meta = '<meta name="robots" content="noindex, nofollow">' if noindex else ""
    seo_meta = "" if noindex else f"""
      <meta name="description" content="{esc(SEO_DESCRIPTION)}">
      <link rel="canonical" href="{SITE_URL}/">
      <meta property="og:title" content="{esc(SEO_TITLE)}">
      <meta property="og:description" content="{esc(SEO_DESCRIPTION)}">
      <meta property="og:type" content="website">
      <meta property="og:url" content="{SITE_URL}/">
      <meta property="og:site_name" content="AUREA Packaging Supply">
      <meta property="og:image" content="{SEO_IMAGE}">
      <meta name="twitter:card" content="summary_large_image">
      <meta name="twitter:title" content="{esc(SEO_TITLE)}">
      <meta name="twitter:description" content="{esc(SEO_DESCRIPTION)}">
      <meta name="twitter:image" content="{SEO_IMAGE}">
      <script type="application/ld+json">{{
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": "AUREA Packaging Supply Pty Ltd",
        "url": "{SITE_URL}/",
        "email": "info@aureapackaging.com.au",
        "telephone": "0497278099",
        "address": {{
          "@type": "PostalAddress",
          "addressLocality": "Melbourne",
          "addressCountry": "AU"
        }},
        "description": "Supplier of coffee cups, lids and takeaway packaging products for cafes and food businesses in Melbourne and across Australia."
      }}</script>"""
    return f"""<!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{page_title}</title>
      <meta name="google-site-verification" content="F7E9xybe9tWEfOtvIs2FOdnGqitnThBp62z9NdeDtuI" />
      {robots_meta}
      {seo_meta}
      <link rel="icon" href="/static/aurea-logo.png">
      <link rel="stylesheet" href="/static/styles.css">
    </head>
    <body>
      <header class="topbar">
        <a class="brand" href="/">
          <img class="brand-logo" src="/static/aurea-logo.png" alt="AUREA Packaging Supply Pty Ltd">
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


def supplier_options(conn, selected_id=None):
    rows = conn.execute("SELECT id, supplier_code, supplier_name FROM suppliers WHERE active = 1 OR id = ? ORDER BY supplier_name", (selected_id or 0,)).fetchall()
    opts = ['<option value="">Select supplier</option>']
    for r in rows:
        selected = "selected" if str(r["id"]) == str(selected_id or "") else ""
        opts.append(
            f'<option value="{esc(r["id"])}" {selected}>{esc(r["supplier_code"])} - {esc(r["supplier_name"])}</option>'
        )
    return "".join(opts)


def customer_options(conn, selected_id=None):
    rows = conn.execute("SELECT id, business_name FROM customers ORDER BY business_name").fetchall()
    return "".join(
        f'<option value="{r["id"]}" {"selected" if str(r["id"]) == str(selected_id or "") else ""}>{esc(r["business_name"])}</option>'
        for r in rows
    )


def invoice_description(name, size):
    name = (name or "").strip()
    size = (size or "").strip()
    if not size:
        return name
    if name.lower().endswith(size.lower()):
        return name
    return f"{name} {size}".strip()


def invoice_description_display(description, size):
    description = (description or "").strip()
    size = (size or "").strip()
    if size and description.lower().endswith(size.lower()) and len(description) > len(size):
        return description[: -len(size)].strip()
    return description


def invoice_product_options(conn, selected_id=None):
    selected_id = selected_id or 0
    rows = conn.execute(
        """
        SELECT id, sku, name, size, qty_per_carton, sell_price, product_type, tax_type
        FROM products
        WHERE active = 1 OR id = ?
        ORDER BY sku
        """,
        (selected_id,),
    ).fetchall()
    opts = ['<option value="">Select product</option>']
    for r in rows:
        description = invoice_description(r["name"], r["size"])
        selected = "selected" if str(r["id"]) == str(selected_id) else ""
        opts.append(
            f'<option value="{esc(r["id"])}" {selected} '
            f'data-code="{esc(r["sku"])}" '
            f'data-description="{esc(description)}" '
            f'data-size="{esc(r["size"])}" '
            f'data-type="{esc(r["product_type"] or "")}" '
            f'data-carton="{esc(r["qty_per_carton"])}" '
            f'data-price="{esc(r["sell_price"])}" '
            f'data-tax="{esc(r["tax_type"] or "GST")}">'
            f'{esc(r["sku"])} - {esc(description)}</option>'
        )
    return "".join(opts)


def status_options(selected_status="Draft"):
    statuses = ["Draft", "Sent", "Paid", "Cancelled"]
    return "".join(
        f'<option {"selected" if status == selected_status else ""}>{status}</option>'
        for status in statuses
    )


def parse_invoice_lines(conn, form_data, max_lines=8):
    selected_lines = []
    subtotal_total = 0.0
    gst_total = 0.0
    for i in range(1, max_lines + 1):
        product_id = form_data.get(f"line_product_{i}")
        qty = float(form_data.get(f"line_qty_{i}") or 0)
        unit_price = float(form_data.get(f"line_price_{i}") or 0)
        if not product_id or qty <= 0:
            continue
        product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not product:
            continue
        tax_type = product["tax_type"] or "GST"
        line_subtotal = qty * unit_price
        line_gst = line_subtotal * 0.10 if tax_type == "GST" else 0.0
        selected_lines.append(
            {
                "product_id": int(product_id),
                "product_code": product["sku"],
                "description": invoice_description(product["name"], product["size"]),
                "size": product["size"],
                "product_type": product["product_type"] or "",
                "carton_quantity": product["qty_per_carton"],
                "quantity": qty,
                "unit_price_ex_gst": unit_price,
                "tax_type": tax_type,
                "subtotal_ex_gst": line_subtotal,
                "gst_amount": line_gst,
                "total_inc_gst": line_subtotal + line_gst,
            }
        )
        subtotal_total += line_subtotal
        gst_total += line_gst
    return selected_lines, subtotal_total, gst_total


def insert_invoice_lines(conn, invoice_id, selected_lines):
    for line in selected_lines:
        conn.execute(
            """
            INSERT INTO invoice_lines
            (invoice_id, product_id, product_code, description, size, product_type,
             carton_quantity, quantity, unit_price_ex_gst, tax_type, subtotal_ex_gst,
             gst_amount, total_inc_gst)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice_id,
                line["product_id"],
                line["product_code"],
                line["description"],
                line["size"],
                line["product_type"],
                line["carton_quantity"],
                line["quantity"],
                line["unit_price_ex_gst"],
                line["tax_type"],
                line["subtotal_ex_gst"],
                line["gst_amount"],
                line["total_inc_gst"],
            ),
        )


def customer_snapshot(conn, customer_id):
    customer = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if not customer:
        return {
            "business_name": "",
            "abn": "",
            "billing_address": "",
            "shipping_address": "",
        }
    billing_address = customer["billing_address"] or customer["suburb"] or ""
    shipping_address = customer["shipping_address"] or billing_address
    return {
        "business_name": customer["business_name"],
        "abn": customer["abn"] or "",
        "billing_address": billing_address,
        "shipping_address": shipping_address,
    }


def create_invoice_from_sales_order(conn, sales_order_id):
    existing = conn.execute("SELECT id FROM invoices WHERE sales_order_id = ? ORDER BY id LIMIT 1", (sales_order_id,)).fetchone()
    if existing:
        return existing["id"], False

    order = conn.execute(
        """
        SELECT o.*, c.business_name
        FROM sales_orders o
        JOIN customers c ON c.id = o.customer_id
        WHERE o.id = ?
        """,
        (sales_order_id,),
    ).fetchone()
    if not order:
        return None, False

    sales_lines = conn.execute(
        """
        SELECT l.*, p.sku, p.name, p.size, p.product_type, p.qty_per_carton, p.tax_type
        FROM sales_lines l
        JOIN products p ON p.id = l.product_id
        WHERE l.order_id = ?
        ORDER BY l.id
        """,
        (sales_order_id,),
    ).fetchall()
    if not sales_lines:
        return None, False

    selected_lines = []
    subtotal_total = 0.0
    gst_total = 0.0
    for line in sales_lines:
        tax_type = line["tax_type"] or "GST"
        line_subtotal = float(line["qty_cartons"] or 0) * float(line["sell_price"] or 0)
        line_gst = line_subtotal * 0.10 if tax_type == "GST" else 0.0
        selected_lines.append(
            {
                "product_id": line["product_id"],
                "product_code": line["sku"],
                "description": invoice_description(line["name"], line["size"]),
                "size": line["size"],
                "product_type": line["product_type"] or "",
                "carton_quantity": line["qty_per_carton"],
                "quantity": line["qty_cartons"],
                "unit_price_ex_gst": line["sell_price"],
                "tax_type": tax_type,
                "subtotal_ex_gst": line_subtotal,
                "gst_amount": line_gst,
                "total_inc_gst": line_subtotal + line_gst,
            }
        )
        subtotal_total += line_subtotal
        gst_total += line_gst

    issue_date = date.today().isoformat()
    due_date = (date.fromisoformat(issue_date) + timedelta(days=7)).isoformat()
    total_inc_gst = subtotal_total + gst_total
    invoice_number = next_invoice_number(conn, issue_date)
    payment_terms = "Payment due within 7 days of invoice date."
    snapshot = customer_snapshot(conn, order["customer_id"])
    cur = conn.execute(
        """
        INSERT INTO invoices
        (invoice_number, sales_order_id, customer_id, customer_business_name, customer_abn,
         billing_address, shipping_address, issue_date, due_date, status, subtotal_ex_gst,
         gst_amount, total_inc_gst, total_paid, balance_due, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            invoice_number,
            sales_order_id,
            order["customer_id"],
            snapshot["business_name"],
            snapshot["abn"],
            snapshot["billing_address"],
            snapshot["shipping_address"],
            issue_date,
            due_date,
            "Sent",
            subtotal_total,
            gst_total,
            total_inc_gst,
            0,
            total_inc_gst,
            payment_terms,
        ),
    )
    invoice_id = cur.lastrowid
    insert_invoice_lines(conn, invoice_id, selected_lines)
    conn.execute("UPDATE sales_orders SET status = ? WHERE id = ?", ("Invoiced", sales_order_id))
    return invoice_id, True


def invoice_line_form_rows(conn, existing_lines=None, max_lines=8):
    existing_lines = list(existing_lines or [])
    rows = ""
    for i in range(1, max_lines + 1):
        line = existing_lines[i - 1] if i <= len(existing_lines) else None
        selected_product = line["product_id"] if line else None
        product_opts = invoice_product_options(conn, selected_product)
        rows += f"""
        <div class="invoice-line-entry">
          <label>Product<select name="line_product_{i}" data-invoice-product>{product_opts}</select></label>
          <label>Code<input name="line_code_{i}" data-line-code readonly value="{esc(line["product_code"] if line else "")}"></label>
          <label>Description<input name="line_description_{i}" data-line-description readonly value="{esc(invoice_description_display(line["description"], line["size"]) if line else "")}"></label>
          <label>UoM<input name="line_carton_{i}" data-line-carton readonly value="{esc(line["carton_quantity"] if line else "")}"></label>
          <label>Tax<input name="line_tax_{i}" data-line-tax readonly value="{esc(line["tax_type"] if line else "")}"></label>
          <label>Quantity<input name="line_qty_{i}" type="number" min="0" step="1" data-line-qty value="{esc(line["quantity"] if line else "")}"></label>
          <label>Unit price ex GST<input name="line_price_{i}" type="number" min="0" step="0.01" data-line-price value="{esc(line["unit_price_ex_gst"] if line else "")}"></label>
          <label>Total inc GST<input data-line-total readonly value="{money(line["total_inc_gst"]) if line else ""}"></label>
        </div>
        """
    return rows


INVOICE_FORM_SCRIPT = """
          <script>
            const moneyFormat = new Intl.NumberFormat("en-AU", { style: "currency", currency: "AUD" });
            const updateInvoiceTotal = () => {
              let total = 0;
              document.querySelectorAll(".invoice-line-entry").forEach((row) => {
                const qty = Number.parseFloat(row.querySelector("[data-line-qty]").value || "0");
                const price = Number.parseFloat(row.querySelector("[data-line-price]").value || "0");
                const tax = row.querySelector("[data-line-tax]").value || "GST";
                const subtotal = qty * price;
                const lineTotal = subtotal + (tax === "GST" ? subtotal * 0.1 : 0);
                row.querySelector("[data-line-total]").value = lineTotal ? moneyFormat.format(lineTotal) : "";
                total += lineTotal;
              });
              document.querySelector("[data-invoice-total]").textContent = moneyFormat.format(total);
            };
            document.querySelectorAll("[data-invoice-product]").forEach((select) => {
              select.addEventListener("change", () => {
                const row = select.closest(".invoice-line-entry");
                const option = select.selectedOptions[0];
                row.querySelector("[data-line-code]").value = option.dataset.code || "";
                row.querySelector("[data-line-description]").value = option.dataset.description || "";
                row.querySelector("[data-line-carton]").value = option.dataset.carton || "";
                row.querySelector("[data-line-tax]").value = option.dataset.tax || "GST";
                row.querySelector("[data-line-price]").value = option.dataset.price || "";
                updateInvoiceTotal();
              });
            });
            document.querySelectorAll("[data-line-qty], [data-line-price]").forEach((input) => {
              input.addEventListener("input", updateInvoiceTotal);
            });
            updateInvoiceTotal();
          </script>
"""


def po_product_options(conn, selected_id=None):
    rows = conn.execute(
        """
        SELECT id, sku, name, size, sell_price, tax_type
        FROM products
        WHERE active = 1 OR id = ?
        ORDER BY sku
        """,
        (selected_id or 0,),
    ).fetchall()
    opts = ['<option value="">Select product</option>']
    for r in rows:
        description = invoice_description(r["name"], r["size"])
        selected = "selected" if str(r["id"]) == str(selected_id or "") else ""
        opts.append(
            f'<option value="{esc(r["id"])}" {selected} '
            f'data-code="{esc(r["sku"])}" '
            f'data-description="{esc(description)}" '
            f'data-price="{esc(r["sell_price"])}" '
            f'data-tax="{esc(r["tax_type"] or "GST")}">'
            f'{esc(r["sku"])} - {esc(description)}</option>'
        )
    return "".join(opts)


def po_line_form_rows(conn, existing_lines=None, max_lines=8, locked=False):
    existing_lines = list(existing_lines or [])
    rows = ""
    disabled = "disabled" if locked else ""
    for i in range(1, max_lines + 1):
        line = existing_lines[i - 1] if i <= len(existing_lines) else None
        product_opts = po_product_options(conn, line["product_id"] if line else None)
        rows += f"""
        <div class="po-line-entry">
          <label>Product<select name="po_product_{i}" data-po-product {disabled}>{product_opts}</select></label>
          <label>Code<input data-po-code readonly value="{esc(line["product_code"] if line else "")}"></label>
          <label>Description<input data-po-description readonly value="{esc(line["description"] if line else "")}"></label>
          <label>Quantity<input name="po_qty_{i}" type="number" min="0" step="1" data-po-qty value="{esc(line["quantity"] if line else "")}" {disabled}></label>
          <label>Unit ex GST<input name="po_price_{i}" type="number" min="0" step="0.01" data-po-price value="{esc(line["unit_price_ex_gst"] if line else "")}" {disabled}></label>
          <label>GST<input data-po-gst readonly value="{money(line["gst_amount"]) if line else ""}"></label>
          <label>Total<input data-po-total readonly value="{money(line["total_inc_gst"]) if line else ""}"></label>
        </div>
        """
    return rows


PO_FORM_SCRIPT = """
          <script>
            const poMoneyFormat = new Intl.NumberFormat("en-AU", { style: "currency", currency: "AUD" });
            const updatePoTotal = () => {
              let total = 0;
              document.querySelectorAll(".po-line-entry").forEach((row) => {
                const qty = Number.parseFloat(row.querySelector("[data-po-qty]").value || "0");
                const price = Number.parseFloat(row.querySelector("[data-po-price]").value || "0");
                const tax = row.querySelector("[data-po-product]").selectedOptions[0]?.dataset.tax || "GST";
                const subtotal = qty * price;
                const gst = tax === "GST" ? subtotal * 0.1 : 0;
                const lineTotal = subtotal + gst;
                row.querySelector("[data-po-gst]").value = gst ? poMoneyFormat.format(gst) : "";
                row.querySelector("[data-po-total]").value = lineTotal ? poMoneyFormat.format(lineTotal) : "";
                total += lineTotal;
              });
              const totalEl = document.querySelector("[data-po-live-total]");
              if (totalEl) totalEl.textContent = poMoneyFormat.format(total);
            };
            document.querySelectorAll("[data-po-product]").forEach((select) => {
              select.addEventListener("change", () => {
                const row = select.closest(".po-line-entry");
                const option = select.selectedOptions[0];
                row.querySelector("[data-po-code]").value = option.dataset.code || "";
                row.querySelector("[data-po-description]").value = option.dataset.description || "";
                row.querySelector("[data-po-price]").value = option.dataset.price || "";
                updatePoTotal();
              });
            });
            document.querySelectorAll("[data-po-qty], [data-po-price]").forEach((input) => {
              input.addEventListener("input", updatePoTotal);
            });
            updatePoTotal();
          </script>
"""


def parse_po_lines(conn, form_data, max_lines=8):
    selected_lines = []
    subtotal_total = 0.0
    gst_total = 0.0
    for i in range(1, max_lines + 1):
        product_id = form_data.get(f"po_product_{i}")
        qty = float(form_data.get(f"po_qty_{i}") or 0)
        unit_price = float(form_data.get(f"po_price_{i}") or 0)
        if not product_id or qty <= 0:
            continue
        product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not product:
            continue
        tax_type = product["tax_type"] or "GST"
        line_subtotal = qty * unit_price
        line_gst = line_subtotal * 0.10 if tax_type == "GST" else 0.0
        selected_lines.append(
            {
                "product_id": int(product_id),
                "product_code": product["sku"],
                "description": invoice_description(product["name"], product["size"]),
                "quantity": qty,
                "unit_price_ex_gst": unit_price,
                "gst_amount": line_gst,
                "subtotal_ex_gst": line_subtotal,
                "total_inc_gst": line_subtotal + line_gst,
            }
        )
        subtotal_total += line_subtotal
        gst_total += line_gst
    return selected_lines, subtotal_total, gst_total


def insert_po_lines(conn, purchase_order_id, selected_lines):
    for line in selected_lines:
        conn.execute(
            """
            INSERT INTO purchase_order_lines
            (purchase_order_id, product_id, product_code, description, quantity,
             unit_price_ex_gst, gst_amount, subtotal_ex_gst, total_inc_gst)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                purchase_order_id,
                line["product_id"],
                line["product_code"],
                line["description"],
                line["quantity"],
                line["unit_price_ex_gst"],
                line["gst_amount"],
                line["subtotal_ex_gst"],
                line["total_inc_gst"],
            ),
        )


def product_inventory_baseline(conn, product_id):
    product = conn.execute("SELECT stock_qty, avg_cost FROM products WHERE id = ?", (product_id,)).fetchone()
    stock_qty = float(product["stock_qty"] or 0) if product else 0.0
    avg_cost = float(product["avg_cost"] or 0) if product else 0.0
    if stock_qty <= 0:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(remaining_cartons),0) AS qty,
                   COALESCE(SUM(remaining_cartons * landed_unit_cost),0) AS value
            FROM purchase_lines
            WHERE product_id = ?
            """,
            (product_id,),
        ).fetchone()
        stock_qty = float(row["qty"] or 0)
        avg_cost = (float(row["value"] or 0) / stock_qty) if stock_qty else 0.0
    return stock_qty, avg_cost


def apply_purchase_order_to_inventory(conn, purchase_order_id):
    po = conn.execute(
        """
        SELECT po.*, s.supplier_name
        FROM purchase_orders po
        JOIN suppliers s ON s.id = po.supplier_id
        WHERE po.id = ?
        """,
        (purchase_order_id,),
    ).fetchone()
    if not po or po["status"] != "Draft":
        return False
    lines = conn.execute("SELECT * FROM purchase_order_lines WHERE purchase_order_id = ? ORDER BY id", (purchase_order_id,)).fetchall()
    if not lines:
        return False
    locked = conn.execute(
        "UPDATE purchase_orders SET status = 'Confirmed', confirmed_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'Draft'",
        (purchase_order_id,),
    )
    if locked.rowcount != 1:
        return False
    batch = conn.execute(
        "INSERT INTO purchase_batches (supplier, invoice_no, freight_cost, batch_date, notes) VALUES (?, ?, ?, ?, ?)",
        (po["supplier_name"], f"PO-{purchase_order_id}", 0, po["order_date"], po["notes"]),
    )
    for line in lines:
        current_qty, current_avg = product_inventory_baseline(conn, line["product_id"])
        received_qty = float(line["quantity"] or 0)
        unit_cost = float(line["unit_price_ex_gst"] or 0)
        new_qty = current_qty + received_qty
        new_avg = (((current_qty * current_avg) + (received_qty * unit_cost)) / new_qty) if new_qty else 0.0
        conn.execute(
            """
            INSERT INTO purchase_lines
            (batch_id, product_id, qty_cartons, unit_cost, freight_alloc, remaining_cartons, landed_unit_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (batch.lastrowid, line["product_id"], int(received_qty), unit_cost, 0, int(received_qty), unit_cost),
        )
        conn.execute("UPDATE products SET stock_qty = ?, avg_cost = ? WHERE id = ?", (new_qty, new_avg, line["product_id"]))
    return True


def next_invoice_number(conn, issue_date):
    prefix = f"INV-{issue_date.replace('-', '')}-"
    row = conn.execute(
        "SELECT invoice_number FROM invoices WHERE invoice_number LIKE ? ORDER BY invoice_number DESC LIMIT 1",
        (f"{prefix}%",),
    ).fetchone()
    next_number = 1
    if row:
        try:
            next_number = int(row["invoice_number"].rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):
            next_number = 1
    return f"{prefix}{next_number:04d}"


def company_master(conn):
    row = conn.execute("SELECT * FROM company_master WHERE id = 1").fetchone()
    if row:
        return row
    conn.execute(
        "INSERT INTO company_master (id, company_name) VALUES (1, 'AUREA Packaging Supply Pty Ltd')"
    )
    return conn.execute("SELECT * FROM company_master WHERE id = 1").fetchone()


def split_address_lines(value):
    value = (value or "").strip()
    if not value:
        return []
    if "\n" in value or "\r" in value:
        raw_lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    else:
        raw_lines = value.split(",")
    return [line.strip() for line in raw_lines if line.strip()]


def invoice_address_html(name, address):
    lines = [name] + split_address_lines(address)
    if address and not any(line.lower() == "australia" for line in lines):
        lines.append("Australia")
    return "".join(f"<p>{esc(line)}</p>" for line in lines if line)


def company_invoice_html(company):
    company_lines = [f'<strong>{esc(company["company_name"])}</strong>']
    company_lines.extend(f"<span>{esc(line)}</span>" for line in split_address_lines(company["address"]))
    if company["phone"]:
        company_lines.append(f'<span>Phone: {esc(company["phone"])}</span>')
    if company["email"]:
        company_lines.append(f'<span>{esc(company["email"])}</span>')
    if company["website"]:
        company_lines.append(f'<span>{esc(company["website"])}</span>')
    if company["abn"]:
        company_lines.append(f'<span>ABN: {esc(company["abn"])}</span>')
    return "".join(company_lines)


def product_by_id():
    return {product["id"]: product for product in PUBLIC_PRODUCTS}


def quick_order_rows():
    rows = ""
    for product in PUBLIC_PRODUCTS:
        product_id = esc(product["id"])
        rows += f"""
        <article class="quick-order-item" data-product-row>
          <span class="selected-badge">Selected</span>
          <div class="quick-product">
            <span class="quick-thumb-wrap">
              <img class="quick-thumb" src="{esc(product["image"])}" alt="{esc(product["name"])} {esc(product["size"])}">
              <img class="quick-preview" src="{esc(product["image"])}" alt="">
            </span>
            <div>
              <strong>{esc(product["name"])}</strong>
              <span>{esc(product["size"])} &middot; {esc(product["type"])}</span>
            </div>
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


def quotation_lines(selected):
    rows = ""
    total = 0
    for item in selected:
        product = item["product"]
        unit_price = float(product["quote_price"])
        subtotal = unit_price * item["boxes"]
        total += subtotal
        note = f"<small>{esc(item['note'])}</small>" if item["note"] else ""
        rows += f"""
        <tr>
          <td>{esc(product["name"])}{note}</td>
          <td>{esc(product["size"])}</td>
          <td>{esc(product["type"])}</td>
          <td>{esc(item["boxes"])}</td>
          <td>{money(unit_price)}</td>
          <td>{money(subtotal)}</td>
        </tr>
        """
    return rows, total


def quotation_email_lines(selected):
    lines = []
    total = 0
    for item in selected:
        product = item["product"]
        unit_price = float(product["quote_price"])
        subtotal = unit_price * item["boxes"]
        total += subtotal
        lines.append(
            {
                "name": product["name"],
                "size": product["size"],
                "type": product["type"],
                "boxes": item["boxes"],
                "unit_price": unit_price,
                "subtotal": subtotal,
                "note": item["note"],
            }
        )
    return lines, total


def email_products_text(lines):
    rows = []
    for line in lines:
        note = f" Note: {line['note']}" if line["note"] else ""
        rows.append(
            f"- {line['name']} | {line['size']} | {line['type']} | "
            f"{line['boxes']} boxes | {money(line['unit_price'])} | {money(line['subtotal'])}{note}"
        )
    return "\n".join(rows)


def email_products_html(lines):
    rows = ""
    for line in lines:
        note = f"<br><small>{esc(line['note'])}</small>" if line["note"] else ""
        rows += f"""
        <tr>
          <td>{esc(line["name"])}{note}</td>
          <td>{esc(line["size"])}</td>
          <td>{esc(line["type"])}</td>
          <td>{esc(line["boxes"])}</td>
          <td>{money(line["unit_price"])}</td>
          <td>{money(line["subtotal"])}</td>
        </tr>
        """
    return f"""
    <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;">
      <thead>
        <tr>
          <th align="left">Product name</th>
          <th align="left">Size</th>
          <th align="left">Type</th>
          <th align="left">Boxes requested</th>
          <th align="left">Unit price</th>
          <th align="left">Line subtotal</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """


def build_customer_quote_email(quote_number, quote_date, form_data, selected):
    lines, total = quotation_email_lines(selected)
    products_text = email_products_text(lines)
    products_html = email_products_html(lines)
    subject = "Your quotation from AUREA Packaging Supply"
    text = f"""Thank you for your enquiry.

Quotation number: {quote_number}
Quotation date: {quote_date}
Business name: {form_data.get("business_name")}

Selected products:
{products_text}

Total amount: {money(total)}
Valid for 7 days.

This is an indicative quotation. Final price is subject to stock availability, delivery area and order confirmation.

Contact:
Stone Wang
0497278099
info@aureapackaging.com.au

We will contact you shortly to confirm delivery and final details.
"""
    html_body = f"""
    <div style="font-family:Arial,sans-serif;color:#12201a;line-height:1.5;">
      <h1 style="color:#06241c;">Your quotation from AUREA Packaging Supply</h1>
      <p>Thank you for your enquiry.</p>
      <p><strong>Quotation number:</strong> {esc(quote_number)}<br>
      <strong>Quotation date:</strong> {esc(quote_date)}<br>
      <strong>Business name:</strong> {esc(form_data.get("business_name"))}</p>
      {products_html}
      <h2>Total amount: {money(total)}</h2>
      <p><strong>Valid for 7 days.</strong></p>
      <p>This is an indicative quotation. Final price is subject to stock availability, delivery area and order confirmation.</p>
      <p><strong>Contact</strong><br>Stone Wang<br>0497278099<br>info@aureapackaging.com.au</p>
      <p>We will contact you shortly to confirm delivery and final details.</p>
    </div>
    """
    return subject, text, html_body


def build_owner_notification_email(quote_number, form_data, selected):
    lines, total = quotation_email_lines(selected)
    products_text = email_products_text(lines)
    products_html = email_products_html(lines)
    business_name = form_data.get("business_name") or "Unknown business"
    subject = f"New Quick Order Enquiry - {business_name}"
    text = f"""New Quick Order Enquiry

Customer business name: {business_name}
Contact person: {form_data.get("contact_name")}
Phone: {form_data.get("phone")}
Email: {form_data.get("email")}
Delivery suburb / postcode: {form_data.get("delivery_suburb")}
Quotation number: {quote_number}

Selected products:
{products_text}

Total amount: {money(total)}

Customer message:
{form_data.get("message") or "No message provided."}
"""
    html_body = f"""
    <div style="font-family:Arial,sans-serif;color:#12201a;line-height:1.5;">
      <h1 style="color:#06241c;">New Quick Order Enquiry</h1>
      <p><strong>Customer business name:</strong> {esc(business_name)}<br>
      <strong>Contact person:</strong> {esc(form_data.get("contact_name"))}<br>
      <strong>Phone:</strong> {esc(form_data.get("phone"))}<br>
      <strong>Email:</strong> {esc(form_data.get("email"))}<br>
      <strong>Delivery suburb / postcode:</strong> {esc(form_data.get("delivery_suburb"))}<br>
      <strong>Quotation number:</strong> {esc(quote_number)}</p>
      {products_html}
      <h2>Total amount: {money(total)}</h2>
      <p><strong>Customer message:</strong><br>{esc(form_data.get("message") or "No message provided.")}</p>
    </div>
    """
    return subject, text, html_body


def smtp_config():
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"]
    config = {key: os.environ.get(key) for key in required}
    config["OWNER_EMAIL"] = os.environ.get("OWNER_EMAIL")
    missing = [key for key, value in config.items() if not value]
    if missing:
        print(f"Quotation email not configured. Missing: {', '.join(missing)}")
        return None
    try:
        config["SMTP_PORT"] = int(config["SMTP_PORT"])
    except ValueError:
        print("Quotation email not configured. SMTP_PORT must be a number.")
        return None
    return config


def send_email(to_email, subject, text_body, html_body=None):
    config = smtp_config()
    if not config:
        return False
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config["SMTP_FROM"]
    message["To"] = to_email
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    try:
        if config["SMTP_PORT"] == 465:
            smtp = smtplib.SMTP_SSL(config["SMTP_HOST"], config["SMTP_PORT"], timeout=10)
        else:
            smtp = smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"], timeout=10)
        with smtp:
            if config["SMTP_PORT"] != 465:
                smtp.starttls()
            smtp.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
            smtp.send_message(message)
        print(f"Quotation email sent to {to_email}")
        return True
    except Exception as exc:
        print(f"Quotation email failed for {to_email}: {exc}")
        return False


def send_quotation_emails(quote_number, quote_date, form_data, selected):
    customer_subject, customer_text, customer_html = build_customer_quote_email(
        quote_number, quote_date, form_data, selected
    )
    customer_sent = send_email(form_data.get("email"), customer_subject, customer_text, customer_html)
    owner_email = os.environ.get("OWNER_EMAIL")
    if owner_email:
        owner_subject, owner_text, owner_html = build_owner_notification_email(quote_number, form_data, selected)
        send_email(owner_email, owner_subject, owner_text, owner_html)
    return customer_sent


def quotation_page(quote_number, quote_date, form_data, selected, email_sent=False):
    rows, total = quotation_lines(selected)
    delivery = form_data.get("delivery_suburb") or ""
    message = form_data.get("message") or ""
    email_notice = (
        "Quotation email has been sent to your email address."
        if email_sent
        else "Your quotation has been generated. We will contact you shortly."
    )
    return f"""
    <section class="quotation-page">
      <div class="quotation-actions no-print">
        <button class="button primary" type="button" onclick="window.print()">Print Quotation</button>
        <a class="button ghost" href="/">Back to Home</a>
      </div>

      <div class="quotation-document">
        <header class="quotation-header">
          <div>
            <div class="document-brand">
              <img src="/static/aurea-logo-light.png" alt="AUREA Packaging Supply Pty Ltd">
            </div>
            <h1>Quotation Draft</h1>
            <p>This is an indicative quotation. Final price is subject to stock availability, delivery area and order confirmation.</p>
          </div>
          <dl>
            <div><dt>Quotation number</dt><dd>{esc(quote_number)}</dd></div>
            <div><dt>Quotation date</dt><dd>{esc(quote_date)}</dd></div>
            <div><dt>Validity</dt><dd>Valid for 7 days.</dd></div>
          </dl>
        </header>

        <section class="quotation-customer">
          <h2>Customer Details</h2>
          <dl>
            <div><dt>Business name</dt><dd>{esc(form_data.get("business_name"))}</dd></div>
            <div><dt>Contact person</dt><dd>{esc(form_data.get("contact_name"))}</dd></div>
            <div><dt>Phone</dt><dd>{esc(form_data.get("phone"))}</dd></div>
            <div><dt>Email</dt><dd>{esc(form_data.get("email"))}</dd></div>
            <div><dt>Delivery suburb / postcode</dt><dd>{esc(delivery)}</dd></div>
          </dl>
        </section>

        <section class="quotation-lines">
          <h2>Selected Products</h2>
          <div class="quotation-table">
            <table>
              <thead>
                <tr>
                  <th>Product name</th>
                  <th>Size</th>
                  <th>Type</th>
                  <th>Boxes requested</th>
                  <th>Unit price</th>
                  <th>Line subtotal</th>
                </tr>
              </thead>
              <tbody>{rows}</tbody>
              <tfoot>
                <tr><th colspan="5">Estimated total for your order</th><td>{money(total)}</td></tr>
              </tfoot>
            </table>
          </div>
        </section>

        <section class="quotation-notes">
          <h2>Notes</h2>
          <p class="email-status">{esc(email_notice)}</p>
          <p>Payment terms: To be confirmed.</p>
          <p>Delivery fee may apply depending on location and order quantity.</p>
          <p>Prices may vary based on stock and demand.</p>
          <p>{esc(message) if message else "No special request provided."}</p>
        </section>

        <section class="quotation-next no-print">
          <div>
            <h2>Ready to proceed?</h2>
            <p>Confirm your order enquiry or speak with us directly so we can lock in availability and final pricing.</p>
          </div>
          <div class="quotation-next-actions">
            <a class="button primary" href="mailto:stone.wang@aureapackaging.com.au?subject=Confirm%20Quotation%20{esc(quote_number)}">Confirm This Order</a>
            <a class="button ghost" href="mailto:stone.wang@aureapackaging.com.au">Contact Us</a>
            <a class="button ghost" href="tel:0412345678">Call Now</a>
          </div>
          <div class="quotation-contact">
            <a href="tel:0412345678">0412 345 678</a>
            <a href="mailto:stone.wang@aureapackaging.com.au">stone.wang@aureapackaging.com.au</a>
          </div>
        </section>
      </div>
    </section>
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
        if path.startswith("/admin/invoices/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[3] == "edit":
                return self.admin_invoice_edit(parts[2])
            if len(parts) == 4 and parts[3] == "delete":
                return self.admin_invoice_delete(parts[2])
            if len(parts) == 3:
                return self.admin_invoice_print(parts[2])
            return self.respond("Not found", 404, content_type="text/plain")
        if path.startswith("/admin/sales/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[3] == "issue-invoice":
                return self.admin_sales_issue_invoice(parts[2])
            if len(parts) == 3:
                return self.admin_sales_detail(parts[2])
            return self.respond("Not found", 404, content_type="text/plain")
        if path.startswith("/admin/purchase-orders/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[3] == "edit":
                return self.admin_purchase_order_edit(parts[2])
            if len(parts) == 4 and parts[3] == "confirm":
                return self.admin_purchase_order_confirm(parts[2])
            if len(parts) == 4 and parts[3] == "delete":
                return self.admin_purchase_order_delete(parts[2])
            if len(parts) == 3:
                return self.admin_purchase_order_detail(parts[2])
            return self.respond("Not found", 404, content_type="text/plain")
        routes = {
            "/": self.catalogue,
            "/quote": self.quote,
            "/robots.txt": self.robots_txt,
            "/sitemap.xml": self.sitemap_xml,
            "/admin/login": self.login,
            "/admin/logout": self.logout,
            "/admin": self.admin,
            "/admin/products": self.admin_products,
            "/admin/customers": self.admin_customers,
            "/admin/suppliers": self.admin_suppliers,
            "/admin/company": self.admin_company,
            "/admin/invoices": self.admin_invoices,
            "/admin/purchase-orders": self.admin_purchase_orders,
            "/admin/purchases": self.admin_purchases,
            "/admin/inventory": self.admin_inventory,
            "/admin/sales": self.admin_sales,
            "/admin/quotes": self.admin_quotes,
        }
        handler = routes.get(path)
        if not handler:
            return self.respond("Not found", 404)
        try:
            return handler()
        except Exception as exc:
            print(f"Unhandled error while serving {path}: {exc}")
            traceback.print_exc()
            return self.respond("Sorry, something went wrong. Please try again.", 500)

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

    def robots_txt(self):
        content = f"""User-agent: *
Allow: /

Sitemap: {SITE_URL}/sitemap.xml
"""
        self.respond(content, content_type="text/plain")

    def sitemap_xml(self):
        content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{SITE_URL}/</loc></url>
  <url><loc>{SITE_URL}/quote</loc></url>
</urlset>
"""
        self.respond(content, content_type="application/xml")

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
            <h1>Premium Coffee Cups &amp; Packaging for Cafes</h1>
            <p>Fast delivery across Melbourne. Best pricing based on quantity.</p>
            <ul class="hero-trust">
              <li><span>&#10003;</span>Bulk pricing for cafes</li>
              <li><span>&#10003;</span>Fast delivery across Melbourne</li>
              <li><span>&#10003;</span>Reliable supply for takeaway shops</li>
            </ul>
            <div class="hero-actions">
              <a class="button primary" href="#quick-order">Get Best Price Now</a>
            </div>
          </div>
        </section>

        <section class="category-section">
          <div class="section-head">
            <p class="eyebrow">Cafe Supply Range</p>
            <h2>Products for Your Cafe</h2>
            <p>Choose the packaging essentials you need, then send one quick enquiry for final B2B pricing.</p>
          </div>
          <div class="category-grid">
            <a class="category-card" href="#quick-order">
              <img src="/static/single-wall-12oz.png" alt="">
              <strong>Coffee Cups</strong>
              <span>Single and double wall kraft cups for everyday takeaway coffee.</span>
            </a>
            <a class="category-card" href="#quick-order">
              <img src="/static/lid-90mm.png" alt="">
              <strong>Lids</strong>
              <span>90mm compatible lids for core 8 oz, 12 oz and 16 oz cup sizes.</span>
            </a>
            <a class="category-card" href="#quick-order">
              <span class="category-icon">CH</span>
              <strong>Cup Holders</strong>
              <span>Carry trays and holders for busy cafe and delivery service.</span>
            </a>
            <a class="category-card" href="#quick-order">
              <span class="category-icon">PB</span>
              <strong>Paper Bags</strong>
              <span>Takeaway bags for food, retail and cafe counter orders.</span>
            </a>
            <a class="category-card" href="#quick-order">
              <span class="category-icon">ST</span>
              <strong>Straws</strong>
              <span>Simple drink accessories for cold beverage service.</span>
            </a>
            <a class="category-card" href="#quick-order">
              <span class="category-icon">NP</span>
              <strong>Napkins</strong>
              <span>Practical table and takeaway napkins for daily operations.</span>
            </a>
          </div>
        </section>

        <section id="quick-order" class="quick-order-section">
          <div class="section-head">
            <p class="eyebrow">Quick Order</p>
            <h2>Request Best Price</h2>
            <p>Select products, enter box quantities, and submit one enquiry. We confirm your best price manually.</p>
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
              <button class="button primary" type="submit">Request Best Price</button>
            </div>
          </form>
          <script>
            const quickOrderForm = document.querySelector(".quick-order-form");
            const quickOrderItems = document.getElementById("quick_order_items");
            const quickOrderWarning = document.getElementById("quick_order_warning");
            const quickOrderQuantityInputs = document.querySelectorAll("[data-product-id]");

            quickOrderQuantityInputs.forEach((input) => {{
              input.addEventListener("input", () => {{
                const row = input.closest("[data-product-row]");
                const boxes = Number.parseInt(input.value || "0", 10);
                if (row) {{
                  row.classList.toggle("is-selected", boxes > 0);
                }}
              }});
            }});

            quickOrderForm.addEventListener("submit", (event) => {{
              const selected = [];
              quickOrderQuantityInputs.forEach((input) => {{
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

        <section class="why-section">
          <article><span class="feature-icon">FD</span><strong>Fast Delivery</strong><span>Melbourne supply for cafes and takeaway businesses.</span></article>
          <article><span class="feature-icon">BP</span><strong>Bulk Pricing</strong><span>Best pricing based on carton quantity and delivery area.</span></article>
          <article><span class="feature-icon">RS</span><strong>Reliable Supply</strong><span>Consistent kraft cups and lids for busy takeaway shops.</span></article>
          <article><span class="feature-icon">EO</span><strong>Eco-friendly Options</strong><span>Practical packaging options with a cleaner kraft look.</span></article>
        </section>

        <section id="products" class="section-head product-heading">
          <p class="eyebrow">Products</p>
          <h2>Cafe Packaging Essentials</h2>
        </section>

        <section class="product-showcase">
          <article>
            <div class="product-image"></div>
            <h3>Single Wall Kraft Coffee Cups</h3>
            <p>Lightweight everyday cups for takeaway coffee service.</p>
          </article>
          <article>
            <div class="product-image"></div>
            <h3>Double Wall Kraft Coffee Cups</h3>
            <p>Extra insulation and a comfortable hold for hot drinks.</p>
          </article>
          <article>
            <div class="product-image"></div>
            <h3>90mm Lids</h3>
            <p>Universal lids compatible with core 8 oz, 12 oz and 16 oz sizes.</p>
          </article>
        </section>

        <section id="contact" class="contact-section">
          <div>
            <p class="eyebrow">Contact</p>
            <h2>Talk to AUREA</h2>
            <p>Send a quick order enquiry or contact us for cafe packaging supply in Melbourne.</p>
          </div>
          <div class="contact-card">
            <strong>Stone Wang</strong>
            <a href="tel:0412345678">0412 345 678</a>
            <a href="mailto:stone.wang@aureapackaging.com.au">stone.wang@aureapackaging.com.au</a>
            <span>Melbourne, Australia</span>
          </div>
        </section>

        <section class="final-cta">
          <div>
            <p class="eyebrow">Ready to Order?</p>
            <h2>Ready to order for your cafe?</h2>
            <p>Send your product quantities once and we will confirm availability, delivery details and the best final price.</p>
          </div>
          <div class="final-cta-actions">
            <a class="button primary" href="#quick-order">Get Best Price Now</a>
            <a class="button ghost" href="#contact">Contact Us</a>
          </div>
        </section>
        """
        self.respond(layout("Product Catalogue", body, self.is_authed()))

    def quote(self):
        if self.command == "POST":
            f = self.form()
            selected = parse_quick_order_items(f.get("items"))
            if not selected:
                body = """
                <section class="panel narrow quote-panel">
                  <div class="quote-empty">
                    <strong>No products selected yet.</strong>
                    <p>Please choose at least one product from Quick Order before submitting an enquiry.</p>
                    <a class="button primary" href="/#quick-order">Choose Products</a>
                  </div>
                </section>
                """
                return self.respond(layout("Request Quote", body, self.is_authed()))
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
                cur = conn.execute(
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
                quote_id = cur.lastrowid
            today = date.today()
            quote_number = f"AQP-{today:%Y%m%d}-{quote_id:04d}"
            quote_date = today.isoformat()
            email_sent = send_quotation_emails(quote_number, quote_date, f, selected)
            body = quotation_page(quote_number, quote_date, f, selected, email_sent)
            return self.respond(layout("Quotation Draft", body, self.is_authed()))
        query = parse_qs(urlparse(self.path).query)
        items_value = query.get("items", [""])[0]
        selected = parse_quick_order_items(items_value)
        summary_text = quick_order_summary_text(selected)
        summary_table = quick_order_table(selected)
        total_boxes = sum(item["boxes"] for item in selected)
        disabled = "" if selected else "disabled"
        body = f"""
        <section class="panel narrow quote-panel">
          <div class="document-brand quote-brand">
            <img src="/static/aurea-logo-light.png" alt="AUREA Packaging Supply Pty Ltd">
          </div>
          <h1>Quick Order Enquiry</h1>
          <div class="quote-summary">
            <h2>Selected products</h2>
            {summary_table}
            <p class="final-price-note">Final price will be confirmed based on quantity, delivery area and availability.</p>
          </div>
          <form method="post" class="form quote-form">
            <input type="hidden" name="items" value="{esc(items_value)}">
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
        self.respond(layout("Admin Login", body, False, noindex=True))

    def logout(self):
        self.respond(
            layout("Logged out", '<section class="panel narrow"><h1>Logged out</h1><a class="button" href="/">Home</a></section>', noindex=True),
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
        self.respond(layout("Admin Dashboard", body, True, noindex=True))

    def admin_products(self):
        if not self.require_admin():
            return
        error = ""
        notice = ""
        form_product = None
        edit_id = parse_qs(urlparse(self.path).query).get("edit", [""])[0]
        saved = parse_qs(urlparse(self.path).query).get("saved", [""])[0]
        if saved == "added":
            notice = '<p class="notice">Product saved successfully.</p>'
        elif saved == "updated":
            notice = '<p class="notice">Product updated successfully.</p>'
        elif saved == "deactivated":
            notice = '<p class="notice">Product deactivated successfully. Existing historical records are preserved.</p>'
        if self.command == "POST":
            f = self.form()
            action = f.get("action") or "save"
            with db() as conn:
                if action == "deactivate":
                    conn.execute("UPDATE products SET active = 0 WHERE id = ?", (int(f.get("product_id")),))
                    conn.commit()
                    return self.redirect("/admin/products?saved=deactivated")

                product_id = f.get("product_id")
                sku = (f.get("sku") or "").strip()
                required_missing = []
                if not sku:
                    required_missing.append("product code")
                if not (f.get("name") or "").strip():
                    required_missing.append("name")
                if not (f.get("qty_per_carton") or "").strip():
                    required_missing.append("carton quantity")
                if not (f.get("sell_price") or "").strip():
                    required_missing.append("default unit price")
                if not (f.get("tax_type") or "").strip():
                    required_missing.append("tax type")
                try:
                    qty_per_carton = int(f.get("qty_per_carton") or 0)
                    sell_price = float(f.get("sell_price") or 0)
                except ValueError:
                    qty_per_carton = 0
                    sell_price = 0.0
                    required_missing.append("valid numeric carton quantity and unit price")

                if required_missing:
                    error = f'<p class="alert">Please enter {esc(", ".join(required_missing))}.</p>'
                    edit_id = product_id or ""
                    form_product = f
                else:
                    duplicate = conn.execute(
                        "SELECT id FROM products WHERE sku = ? AND (? = '' OR id != ?)",
                        (sku, product_id or "", int(product_id or 0)),
                    ).fetchone()
                    if duplicate:
                        error = '<p class="alert">Product code already exists.</p>'
                        edit_id = product_id or ""
                        form_product = f
                    else:
                        values = (
                            sku,
                            f.get("name"),
                            f.get("size") or "",
                            f.get("product_type"),
                            qty_per_carton,
                            sell_price,
                            f.get("tax_type") or "GST",
                            f.get("barcode"),
                            1 if f.get("active") == "on" else 0,
                        )
                        if product_id:
                            conn.execute(
                                """
                                UPDATE products
                                SET sku = ?, name = ?, size = ?, product_type = ?, qty_per_carton = ?,
                                    sell_price = ?, tax_type = ?, barcode = ?, active = ?
                                WHERE id = ?
                                """,
                                (*values, int(product_id)),
                            )
                            conn.commit()
                            return self.redirect("/admin/products?saved=updated")
                        conn.execute(
                            """
                            INSERT INTO products
                            (sku, name, size, product_type, qty_per_carton, sell_price, tax_type, barcode, active)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            values,
                        )
                        conn.commit()
                        return self.redirect("/admin/products?saved=added")
        with db() as conn:
            rows = conn.execute("SELECT * FROM products ORDER BY sku").fetchall()
            edit_product = None
            if edit_id:
                edit_product = conn.execute("SELECT * FROM products WHERE id = ?", (edit_id,)).fetchone()
                if not edit_product and not form_product:
                    error = '<p class="alert">Product not found. It may have been removed or deactivated.</p>'
        product_rows = [
            [
                esc(r["sku"]),
                esc(r["name"]),
                esc(r["size"]),
                esc(r["product_type"] or ""),
                esc(r["qty_per_carton"]),
                money(r["sell_price"]),
                esc(r["tax_type"] or "GST"),
                esc(r["barcode"] or ""),
                "Yes" if r["active"] else "No",
                (
                    f'<a class="mini-quote" href="/admin/products?edit={esc(r["id"])}">Edit</a> '
                    f'<form method="post" class="inline-form" onsubmit="return confirm(\'Are you sure you want to deactivate this product? Existing historical records will be preserved.\')">'
                    f'<input type="hidden" name="action" value="deactivate">'
                    f'<input type="hidden" name="product_id" value="{esc(r["id"])}">'
                    f'<button class="link-button" type="submit">Delete</button></form>'
                ),
            ]
            for r in rows
        ]
        p = form_product or edit_product
        def product_value(key, default=""):
            if not p:
                return default
            if isinstance(p, dict):
                return p.get(key, default)
            try:
                return p[key]
            except (IndexError, KeyError):
                return default

        form_title = "Edit product" if p else "Add product"
        product_id_value = product_value("product_id") or product_value("id")
        hidden_id = f'<input type="hidden" name="product_id" value="{esc(product_id_value)}">' if product_id_value else ""
        tax_type_value = product_value("tax_type", "GST") or "GST"
        gst_selected = "selected" if tax_type_value == "GST" else ""
        gst_free_selected = "selected" if tax_type_value == "GST Free" else ""
        active_value = product_value("active")
        active_checked = "checked" if active_value in ("on", 1, True, "") or not p else ""
        body = f"""
        <section class="section-head"><h1>Product Master</h1><p>Maintain cup and lid SKUs, carton sizes and default sell prices.</p></section>
        {notice}
        {error}
        {table(["Code", "Name", "Size", "Type", "Carton qty", "Unit price ex GST", "Tax", "Barcode", "Active", "Actions"], product_rows)}
        <section class="panel">
          <h2>{form_title}</h2>
          <p class="help-text">Recommended product code format: CUP-08-SW-001, CUP-12-SW-001, CUP-16-SW-001, CUP-08-DW-001, LID-90-PL-001, BAG-SM-KR-001, NAP-WH-001, STR-BK-001. Meaning: Category - Size - Type/Material - Sequence. Examples: CUP = Coffee Cup, SW = Single Wall, DW = Double Wall, LID = Lid, PL = Plastic, BAG = Bag, NAP = Napkin, STR = Straw.</p>
          <form method="post" class="form grid-form">
            {hidden_id}
            <label>Product code<input name="sku" required value="{esc(product_value("sku"))}"></label>
            <label>Name<input name="name" required value="{esc(product_value("name"))}"></label>
            <label>Size<input name="size" value="{esc(product_value("size"))}"></label>
            <label>Product type<input name="product_type" placeholder="Coffee cups, lids, bags" value="{esc(product_value("product_type"))}"></label>
            <label>Carton quantity<input name="qty_per_carton" type="number" min="0" required value="{esc(product_value("qty_per_carton"))}"></label>
            <label>Default unit price ex GST<input name="sell_price" type="number" min="0" step="0.01" required value="{esc(product_value("sell_price"))}"></label>
            <label>Tax type<select name="tax_type" required><option value="GST" {gst_selected}>GST</option><option value="GST Free" {gst_free_selected}>GST Free</option></select></label>
            <label>Barcode value<input name="barcode" value="{esc(product_value("barcode"))}"></label>
            <label class="check"><input name="active" type="checkbox" {active_checked}> Active</label>
            <button class="button primary" type="submit">{form_title}</button>
          </form>
        </section>
        """
        self.respond(layout("Product Master", body, True, noindex=True))

    def admin_customers(self):
        if not self.require_admin():
            return
        notice = ""
        saved = parse_qs(urlparse(self.path).query).get("saved", [""])[0]
        if saved == "customer":
            notice = '<p class="notice">Customer saved successfully.</p>'
        if self.command == "POST":
            f = self.form()
            with db() as conn:
                customer_id = f.get("customer_id")
                values = (
                    f.get("business_name"),
                    f.get("abn"),
                    f.get("contact_name"),
                    f.get("email"),
                    f.get("phone"),
                    f.get("suburb"),
                    f.get("billing_address"),
                    f.get("shipping_address"),
                    f.get("notes"),
                )
                if customer_id:
                    conn.execute(
                        """
                        UPDATE customers
                        SET business_name = ?, abn = ?, contact_name = ?, email = ?, phone = ?,
                            suburb = ?, billing_address = ?, shipping_address = ?, notes = ?
                        WHERE id = ?
                        """,
                        (*values, int(customer_id)),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO customers
                        (business_name, abn, contact_name, email, phone, suburb, billing_address, shipping_address, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        values,
                    )
                conn.commit()
            return self.redirect("/admin/customers?saved=customer")
        edit_id = parse_qs(urlparse(self.path).query).get("edit", [""])[0]
        with db() as conn:
            rows = conn.execute("SELECT * FROM customers ORDER BY business_name").fetchall()
            edit_customer = None
            if edit_id:
                edit_customer = conn.execute("SELECT * FROM customers WHERE id = ?", (edit_id,)).fetchone()
        customer_rows = [
            [
                esc(r["business_name"]),
                esc(r["abn"] or ""),
                esc(r["contact_name"] or ""),
                esc(r["email"] or ""),
                esc(r["phone"] or ""),
                esc(r["billing_address"] or r["suburb"] or ""),
                f'<a class="mini-quote" href="/admin/customers?edit={esc(r["id"])}">Edit</a>',
            ]
            for r in rows
        ]
        c = edit_customer
        form_title = "Edit customer" if c else "Add customer"
        hidden_id = f'<input type="hidden" name="customer_id" value="{esc(c["id"])}">' if c else ""
        body = f"""
        <section class="section-head"><h1>Customer Master</h1><p>Cafe and takeaway customer records.</p></section>
        {notice}
        {table(["Business", "ABN", "Contact", "Email", "Phone", "Billing address", "Action"], customer_rows)}
        <section class="panel">
          <h2>{form_title}</h2>
          <form method="post" class="form grid-form">
            {hidden_id}
            <label>Business name<input name="business_name" required value="{esc(c["business_name"] if c else "")}"></label>
            <label>ABN<input name="abn" value="{esc(c["abn"] if c else "")}"></label>
            <label>Contact person<input name="contact_name" value="{esc(c["contact_name"] if c else "")}"></label>
            <label>Email<input name="email" type="email" value="{esc(c["email"] if c else "")}"></label>
            <label>Phone<input name="phone" value="{esc(c["phone"] if c else "")}"></label>
            <label>Suburb<input name="suburb" value="{esc(c["suburb"] if c else "")}"></label>
            <label>Billing address<textarea name="billing_address" rows="3">{esc(c["billing_address"] if c else "")}</textarea></label>
            <label>Shipping address<textarea name="shipping_address" rows="3">{esc(c["shipping_address"] if c else "")}</textarea></label>
            <label>Notes<textarea name="notes" rows="3">{esc(c["notes"] if c else "")}</textarea></label>
            <button class="button primary" type="submit">{form_title}</button>
          </form>
        </section>
        """
        self.respond(layout("Customer Master", body, True, noindex=True))

    def admin_suppliers(self):
        if not self.require_admin():
            return
        notice = ""
        error = ""
        saved = parse_qs(urlparse(self.path).query).get("saved", [""])[0]
        if saved == "supplier":
            notice = '<p class="notice">Supplier saved successfully.</p>'
        elif saved == "deactivated":
            notice = '<p class="notice">Supplier deactivated successfully. Existing purchase history is preserved.</p>'
        if self.command == "POST":
            f = self.form()
            action = f.get("action") or "save"
            supplier_id = f.get("supplier_id")
            with db() as conn:
                if action == "deactivate":
                    conn.execute("UPDATE suppliers SET active = 0 WHERE id = ?", (int(supplier_id),))
                    conn.commit()
                    return self.redirect("/admin/suppliers?saved=deactivated")

                supplier_code = (f.get("supplier_code") or "").strip()
                supplier_name = (f.get("supplier_name") or "").strip()
                if not supplier_code or not supplier_name:
                    error = '<p class="alert">Please enter supplier code and supplier name.</p>'
                else:
                    duplicate = conn.execute(
                        "SELECT id FROM suppliers WHERE supplier_code = ? AND (? = '' OR id != ?)",
                        (supplier_code, supplier_id or "", int(supplier_id or 0)),
                    ).fetchone()
                    if duplicate:
                        error = '<p class="alert">Supplier code already exists.</p>'
                    else:
                        values = (
                            supplier_code,
                            supplier_name,
                            f.get("abn"),
                            f.get("contact_person"),
                            f.get("email"),
                            f.get("phone"),
                            f.get("address_line_1"),
                            f.get("address_line_2"),
                            f.get("suburb"),
                            f.get("state"),
                            f.get("postcode"),
                            f.get("country") or "Australia",
                            f.get("notes"),
                            1 if f.get("active") == "on" else 0,
                        )
                        if supplier_id:
                            conn.execute(
                                """
                                UPDATE suppliers
                                SET supplier_code = ?, supplier_name = ?, abn = ?, contact_person = ?,
                                    email = ?, phone = ?, address_line_1 = ?, address_line_2 = ?,
                                    suburb = ?, state = ?, postcode = ?, country = ?, notes = ?, active = ?
                                WHERE id = ?
                                """,
                                (*values, int(supplier_id)),
                            )
                        else:
                            conn.execute(
                                """
                                INSERT INTO suppliers
                                (supplier_code, supplier_name, abn, contact_person, email, phone,
                                 address_line_1, address_line_2, suburb, state, postcode, country, notes, active)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                values,
                            )
                        conn.commit()
                        return self.redirect("/admin/suppliers?saved=supplier")
        edit_id = parse_qs(urlparse(self.path).query).get("edit", [""])[0]
        with db() as conn:
            rows = conn.execute("SELECT * FROM suppliers ORDER BY supplier_name").fetchall()
            edit_supplier = conn.execute("SELECT * FROM suppliers WHERE id = ?", (edit_id,)).fetchone() if edit_id else None
        supplier_rows = [
            [
                esc(r["supplier_code"]),
                esc(r["supplier_name"]),
                esc(r["abn"] or ""),
                esc(r["contact_person"] or ""),
                esc(r["email"] or ""),
                esc(r["phone"] or ""),
                esc(" ".join(part for part in [r["suburb"], r["state"], r["postcode"]] if part)),
                "Yes" if r["active"] else "No",
                (
                    f'<a class="mini-quote" href="/admin/suppliers?edit={esc(r["id"])}">Edit</a> '
                    f'<form method="post" class="inline-form" onsubmit="return confirm(\'Deactivate this supplier? Existing purchase history will be preserved.\')">'
                    f'<input type="hidden" name="action" value="deactivate">'
                    f'<input type="hidden" name="supplier_id" value="{esc(r["id"])}">'
                    f'<button class="link-button" type="submit">Deactivate</button></form>'
                ),
            ]
            for r in rows
        ]
        s = edit_supplier
        form_title = "Edit supplier" if s else "Add supplier"
        hidden_id = f'<input type="hidden" name="supplier_id" value="{esc(s["id"])}">' if s else ""
        active_checked = "checked" if not s or s["active"] else ""
        def supplier_value(key, default=""):
            return esc(s[key] if s else default)
        body = f"""
        <section class="section-head"><h1>Supplier Master</h1><p>Maintain supplier records for purchase orders.</p></section>
        {notice}
        {error}
        {table(["Code", "Supplier", "ABN", "Contact", "Email", "Phone", "Location", "Active", "Action"], supplier_rows)}
        <section class="panel">
          <h2>{form_title}</h2>
          <form method="post" class="form grid-form">
            {hidden_id}
            <label>Supplier code<input name="supplier_code" required value="{supplier_value("supplier_code")}"></label>
            <label>Supplier name<input name="supplier_name" required value="{supplier_value("supplier_name")}"></label>
            <label>ABN<input name="abn" value="{supplier_value("abn")}"></label>
            <label>Contact person<input name="contact_person" value="{supplier_value("contact_person")}"></label>
            <label>Email<input name="email" type="email" value="{supplier_value("email")}"></label>
            <label>Phone<input name="phone" value="{supplier_value("phone")}"></label>
            <label>Address line 1<input name="address_line_1" value="{supplier_value("address_line_1")}"></label>
            <label>Address line 2<input name="address_line_2" value="{supplier_value("address_line_2")}"></label>
            <label>Suburb<input name="suburb" value="{supplier_value("suburb")}"></label>
            <label>State<input name="state" value="{supplier_value("state")}"></label>
            <label>Postcode<input name="postcode" value="{supplier_value("postcode")}"></label>
            <label>Country<input name="country" value="{supplier_value("country", "Australia")}"></label>
            <label>Notes<textarea name="notes" rows="3">{supplier_value("notes")}</textarea></label>
            <label class="check"><input name="active" type="checkbox" {active_checked}> Active</label>
            <button class="button primary" type="submit">{form_title}</button>
          </form>
        </section>
        """
        self.respond(layout("Supplier Master", body, True, noindex=True))

    def admin_company(self):
        if not self.require_admin():
            return
        notice = ""
        error = ""
        saved = parse_qs(urlparse(self.path).query).get("saved", [""])[0]
        if saved == "company":
            notice = '<p class="notice">Company details saved successfully.</p>'
        if self.command == "POST":
            f = self.form()
            if not (f.get("company_name") or "").strip():
                error = '<p class="alert">Please enter company name.</p>'
                c = f
            else:
                try:
                    with db() as conn:
                        conn.execute(
                            """
                            UPDATE company_master
                            SET company_name = ?, abn = ?, address = ?, phone = ?, email = ?, website = ?,
                                bank_name = ?, account_name = ?, bsb = ?, account_number = ?, payment_instructions = ?
                            WHERE id = 1
                            """,
                            (
                                f.get("company_name"),
                                f.get("abn"),
                                f.get("address"),
                                f.get("phone"),
                                f.get("email"),
                                f.get("website"),
                                f.get("bank_name"),
                                f.get("account_name"),
                                f.get("bsb"),
                                f.get("account_number"),
                                f.get("payment_instructions"),
                            ),
                        )
                        conn.commit()
                    return self.redirect("/admin/company?saved=company")
                except Exception as exc:
                    print(f"Failed to save company master: {exc}")
                    traceback.print_exc()
                    error = '<p class="alert">Company details could not be saved. Please try again.</p>'
                    c = f
        else:
            with db() as conn:
                c = company_master(conn)
        body = f"""
        <section class="section-head"><h1>Company Master</h1><p>Company and payment details used on printable invoices.</p></section>
        {notice}
        {error}
        <section class="panel">
          <form method="post" class="form grid-form">
            <label>Company name<input name="company_name" required value="{esc(c["company_name"])}"></label>
            <label>ABN<input name="abn" value="{esc(c["abn"])}"></label>
            <label>Phone<input name="phone" value="{esc(c["phone"])}"></label>
            <label>Email<input name="email" type="email" value="{esc(c["email"])}"></label>
            <label>Website<input name="website" value="{esc(c["website"])}"></label>
            <label>Bank name<input name="bank_name" value="{esc(c["bank_name"])}"></label>
            <label>Account name<input name="account_name" value="{esc(c["account_name"])}"></label>
            <label>BSB<input name="bsb" value="{esc(c["bsb"])}"></label>
            <label>Account number<input name="account_number" value="{esc(c["account_number"])}"></label>
            <label>Address<textarea name="address" rows="3">{esc(c["address"])}</textarea></label>
            <label>Payment instructions<textarea name="payment_instructions" rows="4">{esc(c["payment_instructions"])}</textarea></label>
            <button class="button primary" type="submit">Save company details</button>
          </form>
        </section>
        """
        self.respond(layout("Company Master", body, True, noindex=True))

    def admin_invoices(self):
        if not self.require_admin():
            return
        notice = ""
        saved = parse_qs(urlparse(self.path).query).get("saved", [""])[0]
        if saved == "updated":
            notice = '<p class="notice">Invoice updated successfully.</p>'
        elif saved == "deleted":
            notice = '<p class="notice">Invoice deleted successfully.</p>'
        if self.command == "POST":
            f = self.form()
            issue_date = f.get("issue_date") or date.today().isoformat()
            due_date = f.get("due_date") or (date.fromisoformat(issue_date) + timedelta(days=7)).isoformat()
            with db() as conn:
                selected_lines, subtotal_total, gst_total = parse_invoice_lines(conn, f)
                if not selected_lines:
                    return self.redirect("/admin/invoices")
                total_inc_gst = subtotal_total + gst_total
                total_paid = float(f.get("total_paid") or 0)
                invoice_number = next_invoice_number(conn, issue_date)
                snapshot = customer_snapshot(conn, int(f.get("customer_id")))
                cur = conn.execute(
                    """
                    INSERT INTO invoices
                    (invoice_number, customer_id, customer_business_name, customer_abn,
                     billing_address, shipping_address, issue_date, due_date, status, subtotal_ex_gst,
                     gst_amount, total_inc_gst, total_paid, balance_due, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        invoice_number,
                        int(f.get("customer_id")),
                        snapshot["business_name"],
                        snapshot["abn"],
                        snapshot["billing_address"],
                        snapshot["shipping_address"],
                        issue_date,
                        due_date,
                        f.get("status") or "Draft",
                        subtotal_total,
                        gst_total,
                        total_inc_gst,
                        total_paid,
                        total_inc_gst - total_paid,
                        f.get("notes"),
                    ),
                )
                invoice_id = cur.lastrowid
                insert_invoice_lines(conn, invoice_id, selected_lines)
                conn.commit()
            return self.redirect(f"/admin/invoices/{invoice_id}")

        today = date.today()
        due = today + timedelta(days=7)
        with db() as conn:
            customer_opts = customer_options(conn)
            rows = conn.execute(
                """
                SELECT i.id, i.invoice_number, i.issue_date, i.due_date, i.total_inc_gst,
                       i.balance_due, i.status, c.business_name
                FROM invoices i
                JOIN customers c ON c.id = i.customer_id
                ORDER BY i.issue_date DESC, i.id DESC
                """
            ).fetchall()
            line_rows = invoice_line_form_rows(conn, max_lines=8)
        invoice_rows = [
            [
                esc(r["invoice_number"]),
                esc(r["business_name"]),
                esc(display_date(r["issue_date"])),
                esc(display_date(r["due_date"])),
                money(r["total_inc_gst"]),
                money(r["balance_due"]),
                esc(r["status"]),
                (
                    f'<div class="action-group">'
                    f'<a class="mini-quote" href="/admin/invoices/{esc(r["id"])}">View / Print</a>'
                    f'<a class="mini-quote" href="/admin/invoices/{esc(r["id"])}/edit">Edit</a>'
                    f'<form method="post" action="/admin/invoices/{esc(r["id"])}/delete" class="inline-form" onsubmit="return confirm(\'Delete invoice {esc(r["invoice_number"])}? This cannot be undone.\')">'
                    f'<button class="link-button" type="submit">Delete</button></form>'
                    f'</div>'
                ),
            ]
            for r in rows
        ]
        body = f"""
        <section class="section-head"><h1>Invoices</h1><p>Create invoices from customer and product master data.</p></section>
        {notice}
        {table(["Invoice", "Customer", "Issue date", "Due date", "Total", "Balance", "Status", "Action"], invoice_rows)}
        <section class="panel">
          <h2>Create invoice</h2>
          <form method="post" class="form invoice-form">
            <div class="quote-detail-grid">
              <label>Customer<select name="customer_id" required>{customer_opts}</select></label>
              <label>Issue date<input name="issue_date" type="date" value="{today.isoformat()}" required></label>
              <label>Due date<input name="due_date" type="date" value="{due.isoformat()}" required></label>
              <label>Status<select name="status">{status_options("Draft")}</select></label>
              <label>Total paid<input name="total_paid" type="number" min="0" step="0.01" value="0"></label>
            </div>
            <div class="invoice-line-list">{line_rows}</div>
            <div class="invoice-live-total"><span>Estimated total including GST</span><strong data-invoice-total>$0.00</strong></div>
            <label>Notes<textarea name="notes" rows="3"></textarea></label>
            <button class="button primary" type="submit">Create Draft Invoice</button>
          </form>
          {INVOICE_FORM_SCRIPT}
        </section>
        """
        self.respond(layout("Invoices", body, True, noindex=True))

    def admin_invoice_edit(self, invoice_id):
        if not self.require_admin():
            return
        try:
            invoice_id = int(invoice_id)
        except ValueError:
            return self.respond("Not found", 404, content_type="text/plain")
        error = ""
        if self.command == "POST":
            f = self.form()
            issue_date = f.get("issue_date") or date.today().isoformat()
            due_date = f.get("due_date") or (date.fromisoformat(issue_date) + timedelta(days=7)).isoformat()
            with db() as conn:
                invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
                if not invoice:
                    return self.respond("Not found", 404, content_type="text/plain")
                selected_lines, subtotal_total, gst_total = parse_invoice_lines(conn, f)
                if not selected_lines:
                    error = '<p class="alert">Please add at least one invoice line before saving.</p>'
                else:
                    total_inc_gst = subtotal_total + gst_total
                    total_paid = float(f.get("total_paid") or 0)
                    snapshot = customer_snapshot(conn, int(f.get("customer_id")))
                    # Temporary testing rule:
                    # all invoice statuses are editable/deletable.
                    # Before formal production use,
                    # restrict Sent/Paid invoices.
                    conn.execute(
                        """
                        UPDATE invoices
                        SET customer_id = ?, customer_business_name = ?, customer_abn = ?,
                            billing_address = ?, shipping_address = ?,
                            issue_date = ?, due_date = ?, status = ?,
                            subtotal_ex_gst = ?, gst_amount = ?, total_inc_gst = ?,
                            total_paid = ?, balance_due = ?, notes = ?
                        WHERE id = ?
                        """,
                        (
                            int(f.get("customer_id")),
                            snapshot["business_name"],
                            snapshot["abn"],
                            snapshot["billing_address"],
                            snapshot["shipping_address"],
                            issue_date,
                            due_date,
                            f.get("status") or "Draft",
                            subtotal_total,
                            gst_total,
                            total_inc_gst,
                            total_paid,
                            total_inc_gst - total_paid,
                            f.get("notes"),
                            invoice_id,
                        ),
                    )
                    conn.execute("DELETE FROM invoice_lines WHERE invoice_id = ?", (invoice_id,))
                    insert_invoice_lines(conn, invoice_id, selected_lines)
                    conn.commit()
                    return self.redirect("/admin/invoices?saved=updated")
        with db() as conn:
            invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if not invoice:
                return self.respond("Not found", 404, content_type="text/plain")
            lines = conn.execute("SELECT * FROM invoice_lines WHERE invoice_id = ? ORDER BY id", (invoice_id,)).fetchall()
            customer_opts = customer_options(conn, invoice["customer_id"])
            line_rows = invoice_line_form_rows(conn, lines, max_lines=max(8, len(lines) + 2))
        body = f"""
        <section class="section-head"><h1>Edit Invoice</h1><p>Update invoice {esc(invoice["invoice_number"])}. The invoice number is preserved.</p></section>
        {error}
        <section class="panel">
          <form method="post" class="form invoice-form">
            <div class="quote-detail-grid">
              <label>Customer<select name="customer_id" required>{customer_opts}</select></label>
              <label>Issue date<input name="issue_date" type="date" value="{esc(invoice["issue_date"])}" required></label>
              <label>Due date<input name="due_date" type="date" value="{esc(invoice["due_date"])}" required></label>
              <label>Status<select name="status">{status_options(invoice["status"])}</select></label>
              <label>Total paid<input name="total_paid" type="number" min="0" step="0.01" value="{esc(invoice["total_paid"])}"></label>
            </div>
            <div class="invoice-line-list">{line_rows}</div>
            <div class="invoice-live-total"><span>Estimated total including GST</span><strong data-invoice-total>{money(invoice["total_inc_gst"])}</strong></div>
            <label>Notes<textarea name="notes" rows="3">{esc(invoice["notes"])}</textarea></label>
            <div class="form-actions">
              <button class="button primary" type="submit">Save invoice</button>
              <a class="button secondary" href="/admin/invoices">Cancel</a>
            </div>
          </form>
          {INVOICE_FORM_SCRIPT}
        </section>
        """
        self.respond(layout(f"Edit Invoice {invoice['invoice_number']}", body, True, noindex=True))

    def admin_invoice_delete(self, invoice_id):
        if not self.require_admin():
            return
        if self.command != "POST":
            return self.redirect("/admin/invoices")
        try:
            invoice_id = int(invoice_id)
        except ValueError:
            return self.respond("Not found", 404, content_type="text/plain")
        with db() as conn:
            # Temporary testing rule:
            # all invoice statuses are editable/deletable.
            # Before formal production use,
            # restrict Sent/Paid invoices.
            conn.execute("DELETE FROM invoice_lines WHERE invoice_id = ?", (invoice_id,))
            conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
            conn.commit()
        return self.redirect("/admin/invoices?saved=deleted")

    def admin_invoice_print(self, invoice_id):
        if not self.require_admin():
            return
        notice_value = parse_qs(urlparse(self.path).query).get("notice", [""])[0]
        notice = ""
        if notice_value == "invoice_exists":
            notice = '<p class="notice no-print">Invoice already exists for this sales order.</p>'
        elif notice_value == "invoice_issued":
            notice = '<p class="notice no-print">Invoice issued from sales order.</p>'
        try:
            invoice_id = int(invoice_id)
        except ValueError:
            return self.respond("Not found", 404, content_type="text/plain")
        with db() as conn:
            company = company_master(conn)
            invoice = conn.execute(
                """
                SELECT i.*, c.business_name AS current_business_name, c.abn AS current_abn,
                       c.billing_address AS current_billing_address,
                       c.shipping_address AS current_shipping_address, c.suburb AS current_suburb
                FROM invoices i
                JOIN customers c ON c.id = i.customer_id
                WHERE i.id = ?
                """,
                (invoice_id,),
            ).fetchone()
            if not invoice:
                return self.respond("Not found", 404, content_type="text/plain")
            lines = conn.execute("SELECT * FROM invoice_lines WHERE invoice_id = ? ORDER BY id", (invoice_id,)).fetchall()
        line_rows = "".join(
            f"""
            <tr>
              <td>{esc(line["product_code"])}</td>
              <td>{esc(invoice_description_display(line["description"], line["size"]))}</td>
              <td>{esc(line["carton_quantity"])}</td>
              <td>{esc(line["quantity"])}</td>
              <td>{money(line["unit_price_ex_gst"])}</td>
              <td>{esc(line["tax_type"])}</td>
              <td>{money(line["subtotal_ex_gst"])}</td>
              <td>{money(line["gst_amount"])}</td>
              <td>{money(line["total_inc_gst"])}</td>
            </tr>
            """
            for line in lines
        )
        customer_name = invoice["customer_business_name"] or invoice["current_business_name"]
        bill_to = invoice["billing_address"] or invoice["current_billing_address"] or invoice["current_suburb"] or ""
        ship_to = invoice["shipping_address"] or invoice["current_shipping_address"] or bill_to
        company_block = company_invoice_html(company)
        bill_to_block = invoice_address_html(customer_name, bill_to)
        ship_to_block = invoice_address_html(customer_name, ship_to)
        payment_terms = (
            invoice["notes"]
            if invoice["notes"] == "Payment due within 7 days of invoice date."
            else f"Due by {display_date(invoice['due_date'])}"
        )
        body = f"""
        <section class="invoice-page">
          {notice}
          <div class="quotation-actions no-print">
            <button class="button primary" type="button" onclick="window.print()">Print / Save as PDF</button>
            <a class="button ghost" href="/admin/invoices">Back to Invoices</a>
            <p class="print-note">For clean PDF output, turn off browser Headers and footers in print settings.</p>
          </div>
          <div class="invoice-document">
            <header class="invoice-header">
              <div>
                <img class="invoice-logo" src="/static/aurea-logo.png" alt="AUREA Packaging Supply Pty Ltd">
              </div>
              <div class="invoice-company">
                {company_block}
              </div>
            </header>
            <section class="invoice-title-row">
              <h1>Tax Invoice</h1>
              <div class="invoice-meta">
                <dl>
                  <div><dt>Invoice number</dt><dd>{esc(invoice["invoice_number"])}</dd></div>
                  <div><dt>Issue date</dt><dd>{esc(display_date(invoice["issue_date"]))}</dd></div>
                  <div><dt>Due date</dt><dd>{esc(display_date(invoice["due_date"]))}</dd></div>
                  <div><dt>Status</dt><dd>{esc(invoice["status"])}</dd></div>
                </dl>
              </div>
            </section>
            <section class="invoice-addresses">
              <div><h2>Bill to</h2>{bill_to_block}</div>
              <div><h2>Ship to</h2>{ship_to_block}</div>
            </section>
            <div class="quotation-table invoice-table">
              <table>
                <colgroup>
                  <col class="invoice-col-code">
                  <col class="invoice-col-description">
                  <col class="invoice-col-uom">
                  <col class="invoice-col-qty">
                  <col class="invoice-col-unit">
                  <col class="invoice-col-tax">
                  <col class="invoice-col-subtotal">
                  <col class="invoice-col-gst">
                  <col class="invoice-col-total">
                </colgroup>
                <thead><tr><th>Code</th><th>Description</th><th>UoM</th><th>Qty</th><th>Unit price<br>ex GST</th><th>Tax</th><th>Subtotal</th><th>GST</th><th>Total</th></tr></thead>
                <tbody>{line_rows}</tbody>
              </table>
            </div>
            <section class="invoice-bottom">
              <div class="invoice-totals">
                <div><span>Subtotal excluding GST</span><strong>{money(invoice["subtotal_ex_gst"])}</strong></div>
                <div><span>GST</span><strong>{money(invoice["gst_amount"])}</strong></div>
                <div class="total"><span>Total</span><strong>{money(invoice["total_inc_gst"])}</strong></div>
              </div>
            </section>
            <section class="invoice-payment">
              <h2>Payment Details</h2>
              <div class="invoice-payment-grid">
                <p><span>Bank</span><strong>{esc(company["bank_name"])}</strong></p>
                <p><span>Account name</span><strong>{esc(company["account_name"])}</strong></p>
                <p><span>BSB</span><strong>{esc(company["bsb"])}</strong></p>
                <p><span>Account number</span><strong>{esc(company["account_number"])}</strong></p>
                <p><span>Payment reference</span><strong>{esc(invoice["invoice_number"])}</strong></p>
                <p><span>Payment terms</span><strong>{esc(payment_terms)}</strong></p>
              </div>
              <p class="invoice-payment-instructions">{esc(company["payment_instructions"])}</p>
            </section>
            <footer class="invoice-print-footer">Invoice {esc(invoice["invoice_number"])} &middot; Due {esc(display_date(invoice["due_date"]))} &middot; Balance {money(invoice["balance_due"])}</footer>
          </div>
        </section>
        """
        self.respond(layout(f"Invoice {invoice['invoice_number']}", body, True, noindex=True))

    def admin_purchase_orders(self):
        if not self.require_admin():
            return
        notice = ""
        error = ""
        saved = parse_qs(urlparse(self.path).query).get("saved", [""])[0]
        if saved == "created":
            notice = '<p class="notice">Purchase order created successfully.</p>'
        elif saved == "updated":
            notice = '<p class="notice">Purchase order updated successfully.</p>'
        elif saved == "deleted":
            notice = '<p class="notice">Draft purchase order deleted successfully.</p>'
        elif saved == "confirmed":
            notice = '<p class="notice">Purchase order confirmed and inventory updated.</p>'
        elif saved == "locked":
            error = '<p class="alert">Confirmed purchase orders are locked and cannot be edited or deleted.</p>'
        if self.command == "POST":
            f = self.form()
            with db() as conn:
                selected_lines, subtotal_total, gst_total = parse_po_lines(conn, f)
                if not selected_lines:
                    error = '<p class="alert">Please add at least one purchase order line.</p>'
                elif not f.get("supplier_id"):
                    error = '<p class="alert">Please select a supplier.</p>'
                else:
                    total_inc_gst = subtotal_total + gst_total
                    cur = conn.execute(
                        """
                        INSERT INTO purchase_orders
                        (supplier_id, order_date, status, subtotal_ex_gst, gst_amount, total_inc_gst, notes)
                        VALUES (?, ?, 'Draft', ?, ?, ?, ?)
                        """,
                        (
                            int(f.get("supplier_id")),
                            f.get("order_date") or date.today().isoformat(),
                            subtotal_total,
                            gst_total,
                            total_inc_gst,
                            f.get("notes"),
                        ),
                    )
                    po_id = cur.lastrowid
                    insert_po_lines(conn, po_id, selected_lines)
                    conn.commit()
                    return self.redirect(f"/admin/purchase-orders/{po_id}?saved=created")
        today = date.today().isoformat()
        with db() as conn:
            supplier_opts = supplier_options(conn)
            line_rows = po_line_form_rows(conn, max_lines=8)
            rows = conn.execute(
                """
                SELECT po.*, s.supplier_name
                FROM purchase_orders po
                JOIN suppliers s ON s.id = po.supplier_id
                ORDER BY po.order_date DESC, po.id DESC
                """
            ).fetchall()
        po_rows = [
            [
                f"PO-{esc(r["id"])}",
                esc(display_date(r["order_date"])),
                esc(r["supplier_name"]),
                esc(r["status"]),
                money(r["subtotal_ex_gst"]),
                money(r["gst_amount"]),
                money(r["total_inc_gst"]),
                (
                    f'<div class="action-group">'
                    f'<a class="mini-quote" href="/admin/purchase-orders/{esc(r["id"])}">View</a>'
                    f'<a class="mini-quote" href="/admin/purchase-orders/{esc(r["id"])}/edit">Edit</a>'
                    f'</div>'
                ),
            ]
            for r in rows
        ]
        body = f"""
        <section class="section-head"><h1>Purchase Orders</h1><p>Create draft purchase orders and confirm them into inventory.</p></section>
        {notice}
        {error}
        {table(["PO", "Date", "Supplier", "Status", "Subtotal", "GST", "Total", "Action"], po_rows)}
        <section class="panel">
          <h2>Create purchase order</h2>
          <form method="post" class="form invoice-form">
            <div class="quote-detail-grid">
              <label>Supplier<select name="supplier_id" required>{supplier_opts}</select></label>
              <label>Order date<input name="order_date" type="date" value="{today}" required></label>
            </div>
            <div class="po-line-list">{line_rows}</div>
            <div class="invoice-live-total"><span>Estimated total including GST</span><strong data-po-live-total>$0.00</strong></div>
            <label>Notes<textarea name="notes" rows="3"></textarea></label>
            <button class="button primary" type="submit">Create Purchase Order</button>
          </form>
          {PO_FORM_SCRIPT}
        </section>
        """
        self.respond(layout("Purchase Orders", body, True, noindex=True))

    def admin_purchase_order_detail(self, po_id):
        if not self.require_admin():
            return
        try:
            po_id = int(po_id)
        except ValueError:
            return self.respond("Not found", 404, content_type="text/plain")
        notice = ""
        saved = parse_qs(urlparse(self.path).query).get("saved", [""])[0]
        if saved == "created":
            notice = '<p class="notice">Purchase order created successfully.</p>'
        elif saved == "updated":
            notice = '<p class="notice">Purchase order updated successfully.</p>'
        elif saved == "confirmed":
            notice = '<p class="notice">Purchase order confirmed and inventory updated.</p>'
        with db() as conn:
            po = conn.execute(
                """
                SELECT po.*, s.supplier_name, s.supplier_code
                FROM purchase_orders po
                JOIN suppliers s ON s.id = po.supplier_id
                WHERE po.id = ?
                """,
                (po_id,),
            ).fetchone()
            if not po:
                return self.respond("Not found", 404, content_type="text/plain")
            lines = conn.execute("SELECT * FROM purchase_order_lines WHERE purchase_order_id = ? ORDER BY id", (po_id,)).fetchall()
        line_rows = [
            [
                esc(r["product_code"]),
                esc(r["description"]),
                esc(r["quantity"]),
                money(r["unit_price_ex_gst"]),
                money(r["subtotal_ex_gst"]),
                money(r["gst_amount"]),
                money(r["total_inc_gst"]),
            ]
            for r in lines
        ]
        if po["status"] == "Draft":
            actions = f"""
            <div class="form-actions">
              <form method="post" action="/admin/purchase-orders/{po_id}/confirm" onsubmit="return confirm('Confirm this purchase order and update inventory? This can only be done once.')">
                <button class="button primary" type="submit">Confirm PO</button>
              </form>
              <a class="button secondary" href="/admin/purchase-orders/{po_id}/edit">Edit</a>
              <form method="post" action="/admin/purchase-orders/{po_id}/delete" onsubmit="return confirm('Delete this draft purchase order?')">
                <button class="link-button" type="submit">Delete</button>
              </form>
            </div>
            """
        else:
            actions = '<p class="notice">This purchase order is confirmed and locked from accidental changes.</p>'
        body = f"""
        <section class="section-head"><h1>Purchase Order PO-{esc(po["id"])}</h1><p>Supplier order detail and inventory confirmation.</p></section>
        {notice}
        <section class="panel">
          <div class="invoice-meta">
            <dl>
              <div><dt>Date</dt><dd>{esc(display_date(po["order_date"]))}</dd></div>
              <div><dt>Supplier</dt><dd>{esc(po["supplier_name"])}</dd></div>
              <div><dt>Status</dt><dd>{esc(po["status"])}</dd></div>
              <div><dt>Total</dt><dd>{money(po["total_inc_gst"])}</dd></div>
            </dl>
          </div>
          {actions}
        </section>
        {table(["Code", "Description", "Qty", "Unit ex GST", "Subtotal", "GST", "Total"], line_rows)}
        """
        self.respond(layout(f"Purchase Order PO-{po_id}", body, True, noindex=True))

    def admin_purchase_order_edit(self, po_id):
        if not self.require_admin():
            return
        try:
            po_id = int(po_id)
        except ValueError:
            return self.respond("Not found", 404, content_type="text/plain")
        error = ""
        if self.command == "POST":
            f = self.form()
            with db() as conn:
                po = conn.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()
                if not po:
                    return self.respond("Not found", 404, content_type="text/plain")
                if po["status"] != "Draft":
                    return self.redirect("/admin/purchase-orders?saved=locked")
                selected_lines, subtotal_total, gst_total = parse_po_lines(conn, f)
                if not selected_lines:
                    error = '<p class="alert">Please add at least one purchase order line.</p>'
                elif not f.get("supplier_id"):
                    error = '<p class="alert">Please select a supplier.</p>'
                else:
                    total_inc_gst = subtotal_total + gst_total
                    conn.execute(
                        """
                        UPDATE purchase_orders
                        SET supplier_id = ?, order_date = ?, subtotal_ex_gst = ?,
                            gst_amount = ?, total_inc_gst = ?, notes = ?
                        WHERE id = ?
                        """,
                        (
                            int(f.get("supplier_id")),
                            f.get("order_date") or date.today().isoformat(),
                            subtotal_total,
                            gst_total,
                            total_inc_gst,
                            f.get("notes"),
                            po_id,
                        ),
                    )
                    conn.execute("DELETE FROM purchase_order_lines WHERE purchase_order_id = ?", (po_id,))
                    insert_po_lines(conn, po_id, selected_lines)
                    conn.commit()
                    return self.redirect(f"/admin/purchase-orders/{po_id}?saved=updated")
        with db() as conn:
            po = conn.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()
            if not po:
                return self.respond("Not found", 404, content_type="text/plain")
            if po["status"] != "Draft":
                return self.redirect("/admin/purchase-orders?saved=locked")
            supplier_opts = supplier_options(conn, po["supplier_id"])
            lines = conn.execute("SELECT * FROM purchase_order_lines WHERE purchase_order_id = ? ORDER BY id", (po_id,)).fetchall()
            line_rows = po_line_form_rows(conn, lines, max_lines=max(8, len(lines) + 2))
        body = f"""
        <section class="section-head"><h1>Edit Purchase Order PO-{esc(po_id)}</h1><p>Draft purchase orders can be changed before confirmation.</p></section>
        {error}
        <section class="panel">
          <form method="post" class="form invoice-form">
            <div class="quote-detail-grid">
              <label>Supplier<select name="supplier_id" required>{supplier_opts}</select></label>
              <label>Order date<input name="order_date" type="date" value="{esc(po["order_date"])}" required></label>
            </div>
            <div class="po-line-list">{line_rows}</div>
            <div class="invoice-live-total"><span>Estimated total including GST</span><strong data-po-live-total>{money(po["total_inc_gst"])}</strong></div>
            <label>Notes<textarea name="notes" rows="3">{esc(po["notes"])}</textarea></label>
            <div class="form-actions">
              <button class="button primary" type="submit">Save Purchase Order</button>
              <a class="button secondary" href="/admin/purchase-orders/{esc(po_id)}">Cancel</a>
            </div>
          </form>
          {PO_FORM_SCRIPT}
        </section>
        """
        self.respond(layout(f"Edit PO-{po_id}", body, True, noindex=True))

    def admin_purchase_order_confirm(self, po_id):
        if not self.require_admin():
            return
        if self.command != "POST":
            return self.redirect(f"/admin/purchase-orders/{esc(po_id)}")
        try:
            po_id = int(po_id)
        except ValueError:
            return self.respond("Not found", 404, content_type="text/plain")
        with db() as conn:
            confirmed = apply_purchase_order_to_inventory(conn, po_id)
            conn.commit()
        if confirmed:
            return self.redirect(f"/admin/purchase-orders/{po_id}?saved=confirmed")
        return self.redirect("/admin/purchase-orders?saved=locked")

    def admin_purchase_order_delete(self, po_id):
        if not self.require_admin():
            return
        if self.command != "POST":
            return self.redirect(f"/admin/purchase-orders/{esc(po_id)}")
        try:
            po_id = int(po_id)
        except ValueError:
            return self.respond("Not found", 404, content_type="text/plain")
        with db() as conn:
            po = conn.execute("SELECT status FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()
            if not po:
                return self.respond("Not found", 404, content_type="text/plain")
            if po["status"] != "Draft":
                return self.redirect("/admin/purchase-orders?saved=locked")
            conn.execute("DELETE FROM purchase_order_lines WHERE purchase_order_id = ?", (po_id,))
            conn.execute("DELETE FROM purchase_orders WHERE id = ?", (po_id,))
            conn.commit()
        return self.redirect("/admin/purchase-orders?saved=deleted")

    def admin_purchases(self):
        if not self.require_admin():
            return
        notice = ""
        saved = parse_qs(urlparse(self.path).query).get("saved", [""])[0]
        if saved == "purchase":
            notice = '<p class="notice">Purchase batch saved successfully.</p>'
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
                conn.commit()
            return self.redirect("/admin/purchases?saved=purchase")
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
        {notice}
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
        self.respond(layout("Purchase Batches", body, True, noindex=True))

    def admin_inventory(self):
        if not self.require_admin():
            return
        with db() as conn:
            rows = conn.execute(
                """
                SELECT p.sku, p.name,
                       CASE WHEN COALESCE(p.stock_qty, 0) > 0
                            THEN p.stock_qty
                            ELSE COALESCE(SUM(l.remaining_cartons),0)
                       END AS cartons,
                       CASE WHEN COALESCE(p.stock_qty, 0) > 0
                            THEN p.stock_qty * COALESCE(p.avg_cost, 0)
                            ELSE COALESCE(SUM(l.remaining_cartons * l.landed_unit_cost),0)
                       END AS stock_value,
                       COALESCE(p.avg_cost, 0) AS avg_cost
                FROM products p
                LEFT JOIN purchase_lines l ON l.product_id = p.id
                GROUP BY p.id, p.sku, p.name, p.stock_qty, p.avg_cost
                ORDER BY p.sku
                """
            ).fetchall()
        inv_rows = [[esc(r["sku"]), esc(r["name"]), esc(r["cartons"]), money(r["avg_cost"]), money(r["stock_value"])] for r in rows]
        body = f"""
        <section class="section-head"><h1>Inventory Balance</h1><p>On-hand cartons and stock value from remaining purchase batches.</p></section>
        {table(["SKU", "Product", "On hand cartons", "Average cost", "Stock value"], inv_rows)}
        """
        self.respond(layout("Inventory Balance", body, True, noindex=True))

    def admin_sales(self):
        if not self.require_admin():
            return
        message = ""
        saved = parse_qs(urlparse(self.path).query).get("saved", [""])[0]
        if saved == "sales":
            message = '<p class="notice">Sales order saved successfully.</p>'
        elif saved == "invoice_exists":
            message = '<p class="notice">Invoice already exists for this sales order.</p>'
        elif saved == "invoice_issued":
            message = '<p class="notice">Invoice issued from sales order.</p>'
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
                    conn.execute(
                        "UPDATE products SET stock_qty = CASE WHEN COALESCE(stock_qty, 0) > ? THEN stock_qty - ? ELSE 0 END WHERE id = ?",
                        (qty, qty, product_id),
                    )
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
                    conn.commit()
                    return self.redirect("/admin/sales?saved=sales")
        with db() as conn:
            product_opts = product_options(conn)
            customer_opts = customer_options(conn)
            default_sell = conn.execute("SELECT sell_price FROM products ORDER BY sku LIMIT 1").fetchone()
            rows = conn.execute(
                """
                SELECT o.id, o.order_date, o.status, c.business_name, p.sku, p.name, l.qty_cartons,
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
                esc(display_date(r["order_date"])),
                esc(r["status"]),
                esc(r["business_name"]),
                esc(r["sku"]),
                esc(r["name"]),
                esc(r["qty_cartons"]),
                money(r["sell_price"]),
                money(r["cost_price"]),
                money(r["revenue"]),
                money(r["cost"]),
                money(r["gross_profit"]),
                f'<a class="mini-quote" href="/admin/sales/{esc(r["id"])}">Details</a>',
            ]
            for r in rows
        ]
        body = f"""
        <section class="section-head"><h1>Sales Order Entry</h1><p>Create one-line sales orders and calculate gross profit from FIFO batch cost.</p></section>
        {message}
        {table(["Date", "Status", "Customer", "SKU", "Product", "Qty", "Sell/carton", "Cost/carton", "Revenue", "Cost", "Gross profit", "Action"], sales_rows)}
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
        self.respond(layout("Sales Orders", body, True, noindex=True))

    def admin_sales_detail(self, order_id):
        if not self.require_admin():
            return
        try:
            order_id = int(order_id)
        except ValueError:
            return self.respond("Not found", 404, content_type="text/plain")
        notice = ""
        saved = parse_qs(urlparse(self.path).query).get("saved", [""])[0]
        if saved == "invoice_exists":
            notice = '<p class="notice">Invoice already exists for this sales order.</p>'
        elif saved == "invoice_issued":
            notice = '<p class="notice">Invoice issued from sales order.</p>'
        with db() as conn:
            order = conn.execute(
                """
                SELECT o.*, c.business_name, c.abn, c.billing_address, c.shipping_address, c.suburb
                FROM sales_orders o
                JOIN customers c ON c.id = o.customer_id
                WHERE o.id = ?
                """,
                (order_id,),
            ).fetchone()
            if not order:
                return self.respond("Not found", 404, content_type="text/plain")
            lines = conn.execute(
                """
                SELECT l.*, p.sku, p.name, p.size, p.qty_per_carton, p.tax_type
                FROM sales_lines l
                JOIN products p ON p.id = l.product_id
                WHERE l.order_id = ?
                ORDER BY l.id
                """,
                (order_id,),
            ).fetchall()
            invoice = conn.execute(
                "SELECT id, invoice_number FROM invoices WHERE sales_order_id = ? ORDER BY id LIMIT 1",
                (order_id,),
            ).fetchone()
        line_rows = [
            [
                esc(r["sku"]),
                esc(invoice_description(r["name"], r["size"])),
                esc(r["qty_per_carton"]),
                esc(r["qty_cartons"]),
                money(r["sell_price"]),
                esc(r["tax_type"] or "GST"),
                money(r["revenue"]),
            ]
            for r in lines
        ]
        if invoice:
            actions = f"""
            <div class="form-actions">
              <a class="button primary" href="/admin/invoices/{esc(invoice["id"])}">View Invoice</a>
              <a class="button secondary" href="/admin/invoices/{esc(invoice["id"])}">Print Invoice</a>
            </div>
            """
        else:
            actions = f"""
            <form method="post" action="/admin/sales/{esc(order_id)}/issue-invoice" class="form-actions">
              <button class="button primary" type="submit">Issue Invoice</button>
            </form>
            """
        body = f"""
        <section class="section-head"><h1>Sales Order #{esc(order["id"])}</h1><p>Customer order details and invoice issue action.</p></section>
        {notice}
        <section class="panel">
          <div class="invoice-meta">
            <dl>
              <div><dt>Order date</dt><dd>{esc(display_date(order["order_date"]))}</dd></div>
              <div><dt>Status</dt><dd>{esc(order["status"])}</dd></div>
              <div><dt>Customer</dt><dd>{esc(order["business_name"])}</dd></div>
              <div><dt>Invoice</dt><dd>{esc(invoice["invoice_number"] if invoice else "Not issued")}</dd></div>
            </dl>
          </div>
          {actions}
        </section>
        {table(["Code", "Description", "UoM", "Qty", "Unit ex GST", "Tax", "Subtotal"], line_rows)}
        <section class="panel">
          <h2>Addresses copied to invoice</h2>
          <div class="invoice-addresses">
            <div><h2>Bill to</h2>{invoice_address_html(order["business_name"], order["billing_address"] or order["suburb"] or "")}</div>
            <div><h2>Ship to</h2>{invoice_address_html(order["business_name"], order["shipping_address"] or order["billing_address"] or order["suburb"] or "")}</div>
          </div>
        </section>
        """
        self.respond(layout(f"Sales Order {order_id}", body, True, noindex=True))

    def admin_sales_issue_invoice(self, order_id):
        if not self.require_admin():
            return
        if self.command != "POST":
            return self.redirect(f"/admin/sales/{esc(order_id)}")
        try:
            order_id = int(order_id)
        except ValueError:
            return self.respond("Not found", 404, content_type="text/plain")
        with db() as conn:
            invoice_id, created = create_invoice_from_sales_order(conn, order_id)
            if not invoice_id:
                return self.respond("Not found", 404, content_type="text/plain")
            conn.commit()
        if created:
            return self.redirect(f"/admin/invoices/{invoice_id}?notice=invoice_issued")
        return self.redirect(f"/admin/invoices/{invoice_id}?notice=invoice_exists")

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
        self.respond(layout("Quote Requests", body, True, noindex=True))

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
