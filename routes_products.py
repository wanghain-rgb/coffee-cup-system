from urllib.parse import parse_qs, urlparse

from db import db
from utils import *

class ProductRoutesMixin:
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

