from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

from db import db
from utils import *

class InvoiceRoutesMixin:
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
        payment_terms = f"Due by {display_date(invoice['due_date'])}"
        payment_instructions = payment_instruction_lines(company["payment_instructions"])
        payment_instructions_html = (
            f'<p class="invoice-payment-instructions">{esc(payment_instructions)}</p>'
            if payment_instructions
            else ""
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
              {payment_instructions_html}
            </section>
            <footer class="invoice-print-footer">Invoice {esc(invoice["invoice_number"])} &middot; Due {esc(display_date(invoice["due_date"]))} &middot; Balance {money(invoice["balance_due"])}</footer>
          </div>
        </section>
        """
        self.respond(layout(f"Invoice {invoice['invoice_number']}", body, True, noindex=True))

