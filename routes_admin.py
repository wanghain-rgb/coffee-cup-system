from datetime import date
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse
import mimetypes
import os
import sys
import traceback

from db import db
from utils import *

class AdminRoutesMixin:
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

