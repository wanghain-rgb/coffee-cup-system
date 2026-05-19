from datetime import date, timedelta
import html
import hmac
import os

APP_NAME = "CupFlow"
# Render's normal/free filesystem is ephemeral. If this SQLite file is stored
# there, business data can be lost on redeploy/restart/spin-down. Use
# PostgreSQL or a Render persistent disk for production data.
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
    if order["status"] not in ("Confirmed", "Entered", "Invoiced"):
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


def sales_product_options(conn, selected_id=None):
    rows = conn.execute(
        """
        SELECT id, sku, name, size, sell_price
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
            f'data-price="{esc(r["sell_price"])}">'
            f'{esc(r["sku"])} - {esc(description)}</option>'
        )
    return "".join(opts)


def sales_line_form_rows(conn, existing_lines=None, max_lines=8):
    existing_lines = list(existing_lines or [])
    rows = ""
    for i in range(1, max_lines + 1):
        line = existing_lines[i - 1] if i <= len(existing_lines) else None
        product_opts = sales_product_options(conn, line["product_id"] if line else None)
        rows += f"""
        <div class="sales-line-entry">
          <label>Product<select name="sales_product_{i}" data-sales-product>{product_opts}</select></label>
          <label>Code<input data-sales-code readonly value="{esc(line["product_code"] if line else "")}"></label>
          <label>Description<input data-sales-description readonly value="{esc(line["description"] if line else "")}"></label>
          <label>Qty cartons<input name="sales_qty_{i}" type="number" min="0" step="1" data-sales-qty value="{esc(line["qty_cartons"] if line else "")}"></label>
          <label>Sell/carton<input name="sales_price_{i}" type="number" min="0" step="0.01" data-sales-price value="{esc(line["sell_price"] if line else "")}"></label>
          <label>Revenue<input data-sales-revenue readonly value="{money(line["revenue"]) if line else ""}"></label>
        </div>
        """
    return rows


SALES_FORM_SCRIPT = """
          <script>
            const salesMoneyFormat = new Intl.NumberFormat("en-AU", { style: "currency", currency: "AUD" });
            const updateSalesTotal = () => {
              let total = 0;
              document.querySelectorAll(".sales-line-entry").forEach((row) => {
                const qty = Number.parseFloat(row.querySelector("[data-sales-qty]").value || "0");
                const price = Number.parseFloat(row.querySelector("[data-sales-price]").value || "0");
                const revenue = qty * price;
                row.querySelector("[data-sales-revenue]").value = revenue ? salesMoneyFormat.format(revenue) : "";
                total += revenue;
              });
              const totalEl = document.querySelector("[data-sales-live-total]");
              if (totalEl) totalEl.textContent = salesMoneyFormat.format(total);
            };
            document.querySelectorAll("[data-sales-product]").forEach((select) => {
              select.addEventListener("change", () => {
                const row = select.closest(".sales-line-entry");
                const option = select.selectedOptions[0];
                row.querySelector("[data-sales-code]").value = option.dataset.code || "";
                row.querySelector("[data-sales-description]").value = option.dataset.description || "";
                row.querySelector("[data-sales-price]").value = option.dataset.price || "";
                updateSalesTotal();
              });
            });
            document.querySelectorAll("[data-sales-qty], [data-sales-price]").forEach((input) => {
              input.addEventListener("input", updateSalesTotal);
            });
            updateSalesTotal();
          </script>
"""


def parse_sales_lines(conn, form_data, max_lines=8):
    selected_lines = []
    revenue_total = 0.0
    for i in range(1, max_lines + 1):
        product_id = form_data.get(f"sales_product_{i}")
        qty = int(float(form_data.get(f"sales_qty_{i}") or 0))
        sell_price = float(form_data.get(f"sales_price_{i}") or 0)
        if not product_id or qty <= 0:
            continue
        product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not product:
            continue
        revenue = qty * sell_price
        selected_lines.append(
            {
                "product_id": int(product_id),
                "product_code": product["sku"],
                "description": invoice_description(product["name"], product["size"]),
                "qty_cartons": qty,
                "sell_price": sell_price,
                "cost_price": 0.0,
                "revenue": revenue,
                "cost": 0.0,
                "gross_profit": revenue,
            }
        )
        revenue_total += revenue
    return selected_lines, revenue_total


def insert_sales_lines(conn, order_id, selected_lines):
    for line in selected_lines:
        conn.execute(
            """
            INSERT INTO sales_lines
            (order_id, product_id, qty_cartons, sell_price, cost_price, revenue, cost, gross_profit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                line["product_id"],
                line["qty_cartons"],
                line["sell_price"],
                line["cost_price"],
                line["revenue"],
                line["cost"],
                line["gross_profit"],
            ),
        )


def sales_stock_shortages(conn, sales_lines):
    required = {}
    for line in sales_lines:
        required[line["product_id"]] = required.get(line["product_id"], 0) + int(line["qty_cartons"] or 0)
    shortages = []
    for product_id, qty in required.items():
        row = conn.execute(
            """
            SELECT p.sku, p.name, COALESCE(SUM(l.remaining_cartons), 0) AS available
            FROM products p
            LEFT JOIN purchase_lines l ON l.product_id = p.id
            WHERE p.id = ?
            GROUP BY p.id, p.sku, p.name
            """,
            (product_id,),
        ).fetchone()
        available = float(row["available"] or 0) if row else 0.0
        if qty > available:
            label = f'{row["sku"]} - {row["name"]}' if row else f"Product {product_id}"
            shortages.append(f"{label}: need {qty:g}, available {available:g}")
    return shortages


def refresh_product_inventory_from_batches(conn, product_id):
    row = conn.execute(
        """
        SELECT COALESCE(SUM(remaining_cartons), 0) AS qty,
               COALESCE(SUM(remaining_cartons * landed_unit_cost), 0) AS value
        FROM purchase_lines
        WHERE product_id = ?
        """,
        (product_id,),
    ).fetchone()
    stock_qty = float(row["qty"] or 0)
    avg_cost = (float(row["value"] or 0) / stock_qty) if stock_qty else 0.0
    conn.execute("UPDATE products SET stock_qty = ?, avg_cost = ? WHERE id = ?", (stock_qty, avg_cost, product_id))
    return stock_qty, avg_cost


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


