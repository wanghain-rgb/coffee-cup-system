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


APP_NAME = "CupFlow"
DB_PATH = os.path.join(os.path.dirname(__file__), "cupflow.sqlite3")
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


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def money(value):
    return f"${float(value or 0):,.2f}"


def esc(value):
    return html.escape("" if value is None else str(value))


def ensure_column(conn, table, column, ddl):
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


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
                customer_id INTEGER NOT NULL REFERENCES customers(id),
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
        )
        ensure_column(conn, "customers", "abn", "abn TEXT")
        ensure_column(conn, "customers", "billing_address", "billing_address TEXT")
        ensure_column(conn, "customers", "shipping_address", "shipping_address TEXT")
        ensure_column(conn, "products", "product_type", "product_type TEXT")
        ensure_column(conn, "products", "tax_type", "tax_type TEXT NOT NULL DEFAULT 'GST'")

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
        <a href="/admin/company">Company</a>
        <a href="/admin/invoices">Invoices</a>
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


def customer_options(conn):
    rows = conn.execute("SELECT id, business_name FROM customers ORDER BY business_name").fetchall()
    return "".join(f'<option value="{r["id"]}">{esc(r["business_name"])}</option>' for r in rows)


def invoice_product_options(conn):
    rows = conn.execute(
        """
        SELECT id, sku, name, size, qty_per_carton, sell_price, product_type, tax_type
        FROM products
        WHERE active = 1
        ORDER BY sku
        """
    ).fetchall()
    opts = ['<option value="">Select product</option>']
    for r in rows:
        description = f"{r['name']} {r['size']}".strip()
        opts.append(
            f'<option value="{esc(r["id"])}" '
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
            return self.admin_invoice_print(path.rsplit("/", 1)[-1])
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
            "/admin/company": self.admin_company,
            "/admin/invoices": self.admin_invoices,
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
        if self.command == "POST":
            f = self.form()
            with db() as conn:
                conn.execute(
                    """
                    INSERT INTO products (sku, name, size, product_type, qty_per_carton, sell_price, tax_type, active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f.get("sku"),
                        f.get("name"),
                        f.get("size"),
                        f.get("product_type"),
                        int(f.get("qty_per_carton") or 0),
                        float(f.get("sell_price") or 0),
                        f.get("tax_type") or "GST",
                        1 if f.get("active") == "on" else 0,
                    ),
                )
            return self.redirect("/admin/products")
        with db() as conn:
            rows = conn.execute("SELECT * FROM products ORDER BY sku").fetchall()
        product_rows = [
            [
                esc(r["sku"]),
                esc(r["name"]),
                esc(r["size"]),
                esc(r["product_type"] or ""),
                esc(r["qty_per_carton"]),
                money(r["sell_price"]),
                esc(r["tax_type"] or "GST"),
                "Yes" if r["active"] else "No",
            ]
            for r in rows
        ]
        body = f"""
        <section class="section-head"><h1>Product Master</h1><p>Maintain cup and lid SKUs, carton sizes and default sell prices.</p></section>
        {table(["Code", "Name", "Size", "Type", "Carton qty", "Unit price ex GST", "Tax", "Active"], product_rows)}
        <section class="panel">
          <h2>Add product</h2>
          <form method="post" class="form grid-form">
            <label>Product code<input name="sku" required></label>
            <label>Name<input name="name" required></label>
            <label>Size<input name="size" required></label>
            <label>Product type<input name="product_type" placeholder="Coffee cups, lids, bags"></label>
            <label>Carton quantity<input name="qty_per_carton" type="number" required></label>
            <label>Default unit price ex GST<input name="sell_price" type="number" step="0.01" required></label>
            <label>Tax type<select name="tax_type"><option value="GST">GST</option><option value="GST Free">GST Free</option></select></label>
            <label class="check"><input name="active" type="checkbox" checked> Active</label>
            <button class="button primary" type="submit">Add product</button>
          </form>
        </section>
        """
        self.respond(layout("Product Master", body, True, noindex=True))

    def admin_customers(self):
        if not self.require_admin():
            return
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
            return self.redirect("/admin/customers")
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

    def admin_company(self):
        if not self.require_admin():
            return
        if self.command == "POST":
            f = self.form()
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
            return self.redirect("/admin/company")
        with db() as conn:
            c = company_master(conn)
        body = f"""
        <section class="section-head"><h1>Company Master</h1><p>Company and payment details used on printable invoices.</p></section>
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
        if self.command == "POST":
            f = self.form()
            issue_date = f.get("issue_date") or date.today().isoformat()
            due_date = f.get("due_date") or (date.fromisoformat(issue_date) + timedelta(days=7)).isoformat()
            selected_lines = []
            subtotal_total = 0.0
            gst_total = 0.0
            with db() as conn:
                for i in range(1, 6):
                    product_id = f.get(f"line_product_{i}")
                    qty = float(f.get(f"line_qty_{i}") or 0)
                    unit_price = float(f.get(f"line_price_{i}") or 0)
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
                            "description": f"{product['name']} {product['size']}".strip(),
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
                if not selected_lines:
                    return self.redirect("/admin/invoices")
                total_inc_gst = subtotal_total + gst_total
                total_paid = float(f.get("total_paid") or 0)
                invoice_number = next_invoice_number(conn, issue_date)
                cur = conn.execute(
                    """
                    INSERT INTO invoices
                    (invoice_number, customer_id, issue_date, due_date, status, subtotal_ex_gst,
                     gst_amount, total_inc_gst, total_paid, balance_due, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        invoice_number,
                        int(f.get("customer_id")),
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
            return self.redirect(f"/admin/invoices/{invoice_id}")

        today = date.today()
        due = today + timedelta(days=7)
        with db() as conn:
            customer_opts = customer_options(conn)
            product_opts = invoice_product_options(conn)
            rows = conn.execute(
                """
                SELECT i.id, i.invoice_number, i.issue_date, i.due_date, i.total_inc_gst,
                       i.balance_due, i.status, c.business_name
                FROM invoices i
                JOIN customers c ON c.id = i.customer_id
                ORDER BY i.issue_date DESC, i.id DESC
                """
            ).fetchall()
        invoice_rows = [
            [
                esc(r["invoice_number"]),
                esc(r["business_name"]),
                esc(r["issue_date"]),
                esc(r["due_date"]),
                money(r["total_inc_gst"]),
                money(r["balance_due"]),
                esc(r["status"]),
                f'<a class="mini-quote" href="/admin/invoices/{esc(r["id"])}">View / Print</a>',
            ]
            for r in rows
        ]
        line_rows = ""
        for i in range(1, 6):
            line_rows += f"""
            <div class="invoice-line-entry">
              <label>Product<select name="line_product_{i}" data-invoice-product>{product_opts}</select></label>
              <label>Code<input name="line_code_{i}" data-line-code readonly></label>
              <label>Description<input name="line_description_{i}" data-line-description readonly></label>
              <label>Carton qty<input name="line_carton_{i}" data-line-carton readonly></label>
              <label>Tax<input name="line_tax_{i}" data-line-tax readonly></label>
              <label>Quantity<input name="line_qty_{i}" type="number" min="0" step="1" data-line-qty></label>
              <label>Unit price ex GST<input name="line_price_{i}" type="number" min="0" step="0.01" data-line-price></label>
              <label>Total inc GST<input data-line-total readonly></label>
            </div>
            """
        body = f"""
        <section class="section-head"><h1>Invoices</h1><p>Create invoices from customer and product master data.</p></section>
        {table(["Invoice", "Customer", "Issue date", "Due date", "Total", "Balance", "Status", "Action"], invoice_rows)}
        <section class="panel">
          <h2>Create invoice</h2>
          <form method="post" class="form invoice-form">
            <div class="quote-detail-grid">
              <label>Customer<select name="customer_id" required>{customer_opts}</select></label>
              <label>Issue date<input name="issue_date" type="date" value="{today.isoformat()}" required></label>
              <label>Due date<input name="due_date" type="date" value="{due.isoformat()}" required></label>
              <label>Status<select name="status"><option>Draft</option><option>Sent</option><option>Paid</option></select></label>
              <label>Total paid<input name="total_paid" type="number" min="0" step="0.01" value="0"></label>
            </div>
            <div class="invoice-line-list">{line_rows}</div>
            <div class="invoice-live-total"><span>Estimated total including GST</span><strong data-invoice-total>$0.00</strong></div>
            <label>Notes<textarea name="notes" rows="3"></textarea></label>
            <button class="button primary" type="submit">Create Draft Invoice</button>
          </form>
          <script>
            const moneyFormat = new Intl.NumberFormat("en-AU", {{ style: "currency", currency: "AUD" }});
            const updateInvoiceTotal = () => {{
              let total = 0;
              document.querySelectorAll(".invoice-line-entry").forEach((row) => {{
                const qty = Number.parseFloat(row.querySelector("[data-line-qty]").value || "0");
                const price = Number.parseFloat(row.querySelector("[data-line-price]").value || "0");
                const tax = row.querySelector("[data-line-tax]").value || "GST";
                const subtotal = qty * price;
                const lineTotal = subtotal + (tax === "GST" ? subtotal * 0.1 : 0);
                row.querySelector("[data-line-total]").value = lineTotal ? moneyFormat.format(lineTotal) : "";
                total += lineTotal;
              }});
              document.querySelector("[data-invoice-total]").textContent = moneyFormat.format(total);
            }};
            document.querySelectorAll("[data-invoice-product]").forEach((select) => {{
              select.addEventListener("change", () => {{
                const row = select.closest(".invoice-line-entry");
                const option = select.selectedOptions[0];
                row.querySelector("[data-line-code]").value = option.dataset.code || "";
                row.querySelector("[data-line-description]").value = option.dataset.description || "";
                row.querySelector("[data-line-carton]").value = option.dataset.carton || "";
                row.querySelector("[data-line-tax]").value = option.dataset.tax || "GST";
                row.querySelector("[data-line-price]").value = option.dataset.price || "";
                updateInvoiceTotal();
              }});
            }});
            document.querySelectorAll("[data-line-qty], [data-line-price]").forEach((input) => {{
              input.addEventListener("input", updateInvoiceTotal);
            }});
          </script>
        </section>
        """
        self.respond(layout("Invoices", body, True, noindex=True))

    def admin_invoice_print(self, invoice_id):
        if not self.require_admin():
            return
        try:
            invoice_id = int(invoice_id)
        except ValueError:
            return self.respond("Not found", 404, content_type="text/plain")
        with db() as conn:
            company = company_master(conn)
            invoice = conn.execute(
                """
                SELECT i.*, c.business_name, c.abn, c.contact_name, c.email, c.phone,
                       c.billing_address, c.shipping_address, c.suburb
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
              <td>{esc(line["description"])}</td>
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
        bill_to = invoice["billing_address"] or invoice["suburb"] or ""
        ship_to = invoice["shipping_address"] or bill_to
        body = f"""
        <section class="invoice-page">
          <div class="quotation-actions no-print">
            <button class="button primary" type="button" onclick="window.print()">Print / Save as PDF</button>
            <a class="button ghost" href="/admin/invoices">Back to Invoices</a>
          </div>
          <div class="invoice-document">
            <header class="invoice-header">
              <div>
                <img class="invoice-logo" src="/static/aurea-logo.png" alt="AUREA Packaging Supply Pty Ltd">
                <h1>Tax Invoice</h1>
              </div>
              <div class="invoice-company">
                <strong>{esc(company["company_name"])}</strong>
                <span>ABN: {esc(company["abn"])}</span>
                <span>{esc(company["address"])}</span>
                <span>{esc(company["phone"])} &middot; {esc(company["email"])}</span>
                <span>{esc(company["website"])}</span>
              </div>
            </header>
            <section class="invoice-meta">
              <dl>
                <div><dt>Invoice number</dt><dd>{esc(invoice["invoice_number"])}</dd></div>
                <div><dt>Issue date</dt><dd>{esc(invoice["issue_date"])}</dd></div>
                <div><dt>Due date</dt><dd>{esc(invoice["due_date"])}</dd></div>
                <div><dt>Status</dt><dd>{esc(invoice["status"])}</dd></div>
              </dl>
            </section>
            <section class="invoice-addresses">
              <div><h2>Bill to</h2><strong>{esc(invoice["business_name"])}</strong><p>{esc(bill_to)}</p><p>ABN: {esc(invoice["abn"])}</p><p>{esc(invoice["contact_name"])} &middot; {esc(invoice["email"])} &middot; {esc(invoice["phone"])}</p></div>
              <div><h2>Ship to</h2><strong>{esc(invoice["business_name"])}</strong><p>{esc(ship_to)}</p></div>
            </section>
            <div class="quotation-table invoice-table">
              <table>
                <thead><tr><th>Code</th><th>Description</th><th>Carton qty</th><th>Qty</th><th>Unit ex GST</th><th>Tax</th><th>Subtotal</th><th>GST</th><th>Total</th></tr></thead>
                <tbody>{line_rows}</tbody>
              </table>
            </div>
            <section class="invoice-totals">
              <div><span>Subtotal excluding GST</span><strong>{money(invoice["subtotal_ex_gst"])}</strong></div>
              <div><span>GST</span><strong>{money(invoice["gst_amount"])}</strong></div>
              <div><span>Total including GST</span><strong>{money(invoice["total_inc_gst"])}</strong></div>
              <div><span>Total paid</span><strong>{money(invoice["total_paid"])}</strong></div>
              <div class="balance"><span>Balance due</span><strong>{money(invoice["balance_due"])}</strong></div>
            </section>
            <section class="invoice-payment">
              <h2>Payment Details</h2>
              <p><strong>{esc(company["bank_name"])}</strong></p>
              <p>Account name: {esc(company["account_name"])}</p>
              <p>BSB: {esc(company["bsb"])} &middot; Account: {esc(company["account_number"])}</p>
              <p>{esc(company["payment_instructions"])}</p>
            </section>
          </div>
        </section>
        """
        self.respond(layout(f"Invoice {invoice['invoice_number']}", body, True, noindex=True))

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
        self.respond(layout("Purchase Batches", body, True, noindex=True))

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
        self.respond(layout("Inventory Balance", body, True, noindex=True))

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
        self.respond(layout("Sales Orders", body, True, noindex=True))

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
