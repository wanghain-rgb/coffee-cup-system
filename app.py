from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from http.cookies import SimpleCookie
from datetime import date, timedelta
import os
import sys
import traceback

from db import DB_PATH, DATABASE_URL, db, init_db
from routes_admin import AdminRoutesMixin
from routes_customers import CustomerRoutesMixin
from routes_invoices import InvoiceRoutesMixin
from routes_products import ProductRoutesMixin
from routes_public import PublicRoutesMixin
from utils import *

class App(PublicRoutesMixin, AdminRoutesMixin, ProductRoutesMixin, CustomerRoutesMixin, InvoiceRoutesMixin, BaseHTTPRequestHandler):
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
            if len(parts) == 4 and parts[3] == "confirm":
                return self.admin_sales_confirm(parts[2])
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

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

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
        if saved == "created":
            message = '<p class="notice">Draft sales order saved successfully.</p>'
        elif saved == "confirmed":
            message = '<p class="notice">Sales order confirmed and inventory deducted.</p>'
        elif saved == "locked":
            message = '<p class="alert">Only Draft sales orders can be confirmed. Inventory was not deducted again.</p>'
        elif saved == "stock":
            message = '<p class="alert">Not enough stock to confirm this sales order.</p>'
        elif saved == "no_lines":
            message = '<p class="alert">Please add at least one sales order line.</p>'
        elif saved == "invoice_exists":
            message = '<p class="notice">Invoice already exists for this sales order.</p>'
        elif saved == "invoice_issued":
            message = '<p class="notice">Invoice issued from sales order.</p>'
        elif saved == "invoice_blocked":
            message = '<p class="alert">Please confirm the sales order before issuing an invoice.</p>'
        if self.command == "POST":
            f = self.form()
            with db() as conn:
                selected_lines, revenue_total = parse_sales_lines(conn, f)
                if not selected_lines:
                    return self.redirect("/admin/sales?saved=no_lines")
                if not f.get("customer_id"):
                    return self.redirect("/admin/sales?saved=no_lines")
                cur = conn.execute(
                    "INSERT INTO sales_orders (customer_id, order_date, status, notes) VALUES (?, ?, 'Draft', ?)",
                    (int(f.get("customer_id")), f.get("order_date") or date.today().isoformat(), f.get("notes")),
                )
                insert_sales_lines(conn, cur.lastrowid, selected_lines)
                conn.commit()
                return self.redirect(f"/admin/sales/{cur.lastrowid}?saved=created")
        with db() as conn:
            customer_opts = customer_options(conn)
            line_rows = sales_line_form_rows(conn, max_lines=8)
            rows = conn.execute(
                """
                SELECT o.id, o.order_date, o.status, c.business_name,
                       COUNT(l.id) AS line_count,
                       COALESCE(SUM(l.revenue), 0) AS revenue,
                       COALESCE(SUM(l.cost), 0) AS cost,
                       COALESCE(SUM(l.gross_profit), 0) AS gross_profit
                FROM sales_orders o
                JOIN customers c ON c.id = o.customer_id
                LEFT JOIN sales_lines l ON l.order_id = o.id
                GROUP BY o.id, o.order_date, o.status, c.business_name
                ORDER BY o.order_date DESC, o.id DESC
                """
            ).fetchall()
        sales_rows = [
            [
                esc(display_date(r["order_date"])),
                esc(r["status"]),
                esc(r["business_name"]),
                esc(r["line_count"]),
                money(r["revenue"]),
                money(r["cost"]),
                money(r["gross_profit"]),
                f'<a class="mini-quote" href="/admin/sales/{esc(r["id"])}">Details</a>',
            ]
            for r in rows
        ]
        body = f"""
        <section class="section-head"><h1>Sales Order Entry</h1><p>Create draft sales orders, then confirm once to deduct FIFO inventory.</p></section>
        {message}
        {table(["Date", "Status", "Customer", "Lines", "Revenue", "Cost", "Gross profit", "Action"], sales_rows)}
        <section class="panel">
          <h2>Add sales order</h2>
          <form method="post" class="form invoice-form">
            <div class="quote-detail-grid">
              <label>Customer<select name="customer_id" required>{customer_opts}</select></label>
              <label>Date<input name="order_date" type="date" value="{date.today().isoformat()}" required></label>
            </div>
            <div class="sales-line-list">{line_rows}</div>
            <div class="invoice-live-total"><span>Estimated revenue excluding GST</span><strong data-sales-live-total>$0.00</strong></div>
            <label>Notes<textarea name="notes" rows="3"></textarea></label>
            <button class="button primary" type="submit">Save Draft Order</button>
          </form>
          {SALES_FORM_SCRIPT}
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
        if saved == "created":
            notice = '<p class="notice">Draft sales order saved successfully.</p>'
        elif saved == "confirmed":
            notice = '<p class="notice">Sales order confirmed and inventory deducted.</p>'
        elif saved == "locked":
            notice = '<p class="alert">Only Draft sales orders can be confirmed. Inventory was not deducted again.</p>'
        elif saved == "stock":
            notice = '<p class="alert">Not enough stock to confirm this sales order. Please check inventory before confirming.</p>'
        elif saved == "no_lines":
            notice = '<p class="alert">Please add at least one sales order line.</p>'
        elif saved == "invoice_blocked":
            notice = '<p class="alert">Please confirm the sales order before issuing an invoice.</p>'
        elif saved == "invoice_exists":
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
                money(r["cost_price"]),
                money(r["revenue"]),
                money(r["cost"]),
                money(r["gross_profit"]),
            ]
            for r in lines
        ]
        total_revenue = sum(float(r["revenue"] or 0) for r in lines)
        total_cost = sum(float(r["cost"] or 0) for r in lines)
        total_gp = sum(float(r["gross_profit"] or 0) for r in lines)
        if invoice:
            actions = f"""
            <div class="form-actions">
              <a class="button primary" href="/admin/invoices/{esc(invoice["id"])}">View Invoice</a>
              <a class="button secondary" href="/admin/invoices/{esc(invoice["id"])}">Print Invoice</a>
            </div>
            """
        elif order["status"] == "Draft":
            actions = f"""
            <div class="form-actions">
              <form method="post" action="/admin/sales/{esc(order_id)}/confirm" onsubmit="return confirm('Confirm this sales order and deduct inventory? This can only be done once.')">
                <button class="button primary" type="submit">Confirm Order</button>
              </form>
              <p class="help-text">Inventory is not deducted until the order is confirmed.</p>
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
              <div><dt>Revenue</dt><dd>{money(total_revenue)}</dd></div>
              <div><dt>Cost</dt><dd>{money(total_cost)}</dd></div>
              <div><dt>Gross profit</dt><dd>{money(total_gp)}</dd></div>
            </dl>
          </div>
          {actions}
        </section>
        {table(["Code", "Description", "UoM", "Qty", "Sell/carton", "Cost/carton", "Revenue", "Cost", "Gross profit"], line_rows)}
        <section class="panel">
          <h2>Addresses copied to invoice</h2>
          <div class="invoice-addresses">
            <div><h2>Bill to</h2>{invoice_address_html(order["business_name"], order["billing_address"] or order["suburb"] or "")}</div>
            <div><h2>Ship to</h2>{invoice_address_html(order["business_name"], order["shipping_address"] or order["billing_address"] or order["suburb"] or "")}</div>
          </div>
        </section>
        """
        self.respond(layout(f"Sales Order {order_id}", body, True, noindex=True))

    def admin_sales_confirm(self, order_id):
        if not self.require_admin():
            return
        if self.command != "POST":
            return self.redirect(f"/admin/sales/{esc(order_id)}")
        try:
            order_id = int(order_id)
        except ValueError:
            return self.respond("Not found", 404, content_type="text/plain")
        with db() as conn:
            order = conn.execute("SELECT status FROM sales_orders WHERE id = ?", (order_id,)).fetchone()
            if not order:
                return self.respond("Not found", 404, content_type="text/plain")
            if order["status"] != "Draft":
                return self.redirect(f"/admin/sales/{order_id}?saved=locked")
            lines = conn.execute("SELECT * FROM sales_lines WHERE order_id = ? ORDER BY id", (order_id,)).fetchall()
            if not lines:
                return self.redirect(f"/admin/sales/{order_id}?saved=no_lines")
            shortages = sales_stock_shortages(conn, lines)
            if shortages:
                return self.redirect(f"/admin/sales/{order_id}?saved=stock")
            locked = conn.execute(
                "UPDATE sales_orders SET status = 'Confirmed', confirmed_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'Draft'",
                (order_id,),
            )
            if locked.rowcount != 1:
                return self.redirect(f"/admin/sales/{order_id}?saved=locked")
            touched_products = set()
            try:
                for line in lines:
                    qty = int(line["qty_cartons"] or 0)
                    if qty <= 0:
                        conn.rollback()
                        return self.redirect(f"/admin/sales/{order_id}?saved=no_lines")
                    cost_total = self.allocate_fifo(conn, line["product_id"], qty)
                    revenue = qty * float(line["sell_price"] or 0)
                    conn.execute(
                        """
                        UPDATE sales_lines
                        SET cost_price = ?, revenue = ?, cost = ?, gross_profit = ?
                        WHERE id = ?
                        """,
                        (cost_total / qty, revenue, cost_total, revenue - cost_total, line["id"]),
                    )
                    touched_products.add(line["product_id"])
                for product_id in touched_products:
                    refresh_product_inventory_from_batches(conn, product_id)
                conn.commit()
            except ValueError:
                conn.rollback()
                return self.redirect(f"/admin/sales/{order_id}?saved=stock")
        return self.redirect(f"/admin/sales/{order_id}?saved=confirmed")

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
                return self.redirect(f"/admin/sales/{order_id}?saved=invoice_blocked")
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
if __name__ == "__main__":
    main()
