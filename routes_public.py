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
        # Build product showcase cards from PUBLIC_PRODUCTS
        showcase_cards = ""
        for product in PUBLIC_PRODUCTS:
            showcase_cards += f"""
            <article class="pub-product-card">
              <div class="pub-product-img-wrap">
                <img src="{esc(product["image"])}" alt="{esc(product["name"])} {esc(product["size"])}">
              </div>
              <div class="pub-product-body">
                <p class="pub-product-type">{esc(product["type"])}</p>
                <h3 class="pub-product-name">{esc(product["name"])}</h3>
                <div class="pub-product-specs">
                  <span><strong>{esc(product["size"])}</strong></span>
                  <span>{esc(product["carton"])}</span>
                  <span>{esc(product["lid"])}</span>
                </div>
                <div class="pub-product-price">
                  <span class="pub-price-from">From</span>
                  <strong class="pub-price-value">{money(product["quote_price"])}</strong>
                  <span class="pub-price-unit">/ box</span>
                </div>
              </div>
              <a class="button primary pub-product-cta" href="#quick-order">Add to Order</a>
            </article>
            """
        body = f"""
        <section class="hero">
          <div class="hero-copy">
            <p class="eyebrow">AUREA Packaging Supply Pty Ltd &mdash; Melbourne</p>
            <h1>Premium Coffee Cups &amp; Packaging for Cafes</h1>
            <p>Fast delivery across Melbourne. Best pricing based on quantity.</p>
            <ul class="hero-trust">
              <li><span>&#10003;</span>Bulk pricing for cafes &amp; takeaway shops</li>
              <li><span>&#10003;</span>Fast delivery across Melbourne</li>
              <li><span>&#10003;</span>Kraft cups, lids and packaging in stock</li>
            </ul>
            <div class="hero-actions">
              <a class="button primary" href="#quick-order">Get Best Price Now</a>
              <a class="button ghost" href="#contact">Contact Us</a>
            </div>
          </div>
        </section>

        <section class="why-section">
          <article>
            <span class="feature-icon">&#128666;</span>
            <strong>Fast Delivery</strong>
            <span>Melbourne supply for cafes and takeaway businesses with short lead times.</span>
          </article>
          <article>
            <span class="feature-icon">&#128176;</span>
            <strong>Bulk Pricing</strong>
            <span>Best pricing based on carton quantity. The more you order, the better the rate.</span>
          </article>
          <article>
            <span class="feature-icon">&#128230;</span>
            <strong>Reliable Supply</strong>
            <span>Consistent kraft cups and lids always in stock for busy takeaway shops.</span>
          </article>
          <article>
            <span class="feature-icon">&#127807;</span>
            <strong>Eco-friendly</strong>
            <span>Natural kraft paper packaging options with a clean, sustainable look.</span>
          </article>
        </section>

        <section id="products" class="pub-products-section">
          <div class="section-head">
            <p class="eyebrow">Our Products</p>
            <h2>Cafe Packaging Range</h2>
            <p>Single wall and double wall kraft cups, universal 90mm lids — everything your cafe needs, ordered in bulk at trade prices.</p>
          </div>
          <div class="pub-products-grid">
            {showcase_cards}
          </div>
        </section>

        <section id="quick-order" class="qo-section">
          <div class="section-head">
            <p class="eyebrow">Quick Order</p>
            <h2>Select Products &amp; Quantities</h2>
            <p>Enter box quantities for what you need, then submit one enquiry. We confirm your best price within one business day.</p>
          </div>
          <form class="quick-order-form" action="/quote" method="get">
            <input type="hidden" name="items" id="quick_order_items">
            <div class="qo-grid">
              {quick_rows}
            </div>
            <p class="quick-warning" id="quick_order_warning" role="alert">Please add a quantity to at least one product before requesting a price.</p>
            <div class="qo-footer">
              <span>No payment or checkout &mdash; we confirm final price with you directly.</span>
              <button class="button primary qo-submit" type="submit">Request Best Price &rarr;</button>
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

        <section id="contact" class="contact-section">
          <div>
            <p class="eyebrow">Contact</p>
            <h2>Talk to AUREA</h2>
            <p>Send a quick order enquiry or contact us directly for cafe packaging supply in Melbourne.</p>
          </div>
          <div class="contact-card">
            <strong>Stone Wang</strong>
            <a href="tel:0497278099">0497 278 099</a>
            <a href="mailto:info@aureapackaging.com.au">info@aureapackaging.com.au</a>
            <span>Melbourne, Australia</span>
          </div>
        </section>

        <section class="final-cta">
          <div>
            <p class="eyebrow">Ready to Order?</p>
            <h2>Ready to stock up your cafe?</h2>
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
        <div class="pub-quote-steps">
          <div class="pub-quote-step pub-quote-step--done">
            <span>1</span><strong>Select Products</strong>
          </div>
          <div class="pub-quote-step pub-quote-step--active">
            <span>2</span><strong>Your Details</strong>
          </div>
          <div class="pub-quote-step">
            <span>3</span><strong>Get Quote</strong>
          </div>
        </div>
        <section class="panel narrow quote-panel">
          <div class="document-brand quote-brand">
            <img src="/static/aurea-logo-light.png" alt="AUREA Packaging Supply Pty Ltd">
          </div>
          <h1>Quick Order Enquiry</h1>
          <div class="quote-summary">
            <h2>Your selected products</h2>
            {summary_table}
            <p class="final-price-note">&#9432;&nbsp; Final price confirmed based on quantity, delivery suburb and availability.</p>
          </div>
          <form method="post" class="form quote-form">
            {self.csrf_input()}
            <input type="hidden" name="items" value="{esc(items_value)}">
            <textarea hidden name="product_interest">{esc(summary_text)}</textarea>
            <textarea hidden name="order_summary">{esc(summary_text)}</textarea>
            <input type="hidden" name="monthly_volume" value="{esc(f'{total_boxes} boxes requested' if total_boxes else '')}">
            <p class="pub-form-lead">Tell us who you are so we can send your personalised quotation.</p>
            <div class="quote-detail-grid">
              <label>Business name<input name="business_name" required {disabled} placeholder="Your cafe or business name"></label>
              <label>Contact person<input name="contact_name" required {disabled} placeholder="Your full name"></label>
              <label>Phone<input name="phone" required {disabled} placeholder="e.g. 0400 000 000"></label>
              <label>Email<input name="email" type="email" required {disabled} placeholder="your@email.com"></label>
              <label>Delivery suburb / postcode<input name="delivery_suburb" required {disabled} placeholder="e.g. Fitzroy 3065"></label>
            </div>
            <label>Message / special request<textarea name="message" rows="3" placeholder="Delivery timing, payment terms, custom print, or any other requirements" {disabled}></textarea></label>
            <button class="button primary pub-quote-submit" type="submit" {disabled}>Submit Enquiry &rarr;</button>
          </form>
        </section>
        """
        self.respond(layout("Request Quote", body, self.is_authed()))

