from datetime import date
from urllib.parse import parse_qs, urlparse

from db import db
from email_utils import send_quotation_emails
from utils import *

class PublicRoutesMixin:
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

