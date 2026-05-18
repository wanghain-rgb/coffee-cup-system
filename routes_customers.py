from urllib.parse import parse_qs, urlparse

from db import db
from utils import *

class CustomerRoutesMixin:
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

