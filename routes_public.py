import json
from datetime import date
from urllib.parse import parse_qs, urlparse

from db import db
from email_utils import send_quotation_emails
from utils import *


def range_icon_svg(name):
    icons = {
        "Paper cups": '<path d="M18 15h28l-4 40H22z"/><path d="M16 15h32"/><path d="M22 26h20"/>',
        "Soup & salad bowls": '<path d="M14 27h36"/><path d="M18 28c2 13 8 20 14 20s12-7 14-20"/><path d="M21 22c7-4 19-4 26 0"/>',
        "Take-out boxes": '<path d="M18 25l8-8h20l8 8-5 28H23z"/><path d="M26 17l6 10h14l-8-10"/><path d="M23 25h26"/>',
        "Food trays": '<path d="M15 37l9-14h28l-6 24H20z"/><path d="M23 29h20"/><path d="M28 25l-2 13"/>',
        "Plastic containers": '<path d="M18 25h32l-3 24H21z"/><path d="M14 21h40v6H14z"/><path d="M24 31h20"/>',
        "Sugarcane tableware": '<circle cx="34" cy="34" r="18"/><circle cx="34" cy="34" r="10"/>',
        "Cutlery": '<path d="M20 14v40"/><path d="M16 14v14M20 14v14M24 14v14"/><path d="M34 14v40"/><path d="M44 14c7 7 7 17 0 24v16"/>',
        "Eco straws": '<path d="M24 54l14-40"/><path d="M38 54l14-40"/><path d="M44 14h10"/><path d="M30 14h10"/>',
        "Paper bags": '<path d="M20 25h28v29H20z"/><path d="M26 25c0-8 16-8 16 0"/><path d="M42 54l6-7"/>',
        "Cup carriers": '<path d="M16 28h36l-6 18H22z"/><circle cx="27" cy="34" r="5"/><circle cx="41" cy="34" r="5"/><path d="M22 46v8M46 46v8"/>',
        "Napkins": '<path d="M20 22h25v25H20z"/><path d="M24 18h25v25"/><path d="M28 14h25v25"/>',
        "Sushi boxes": '<rect x="17" y="18" width="34" height="32" rx="4"/><circle cx="27" cy="29" r="4"/><circle cx="40" cy="29" r="4"/><circle cx="27" cy="41" r="4"/><circle cx="40" cy="41" r="4"/>',
        "Labels & stickers": '<path d="M18 18h24v32H18z"/><path d="M42 30h10v20H42z"/><circle cx="30" cy="31" r="6"/>',
        "Kitchen wipes": '<path d="M18 27c9-9 22 9 32 0v24c-10 9-23-9-32 0z"/><path d="M25 36l18 5"/>',
        "Flat bags": '<path d="M21 16h24v38H21z"/><path d="M29 20h24v38H29z"/>',
        "Wraps": '<path d="M15 38c0-8 8-14 18-14s18 6 18 14-8 14-18 14-18-6-18-14z"/><path d="M33 24v28"/><path d="M51 38h8"/>',
        "PET cold cups": '<path d="M22 22h24l-4 32H26z"/><path d="M18 20h32"/><path d="M28 14h12l4 6"/><path d="M34 14v-6"/>',
    }
    icon = icons.get(name, '<path d="M18 20h32v30H18z"/><path d="M24 28h20"/>')
    return f'<span class="range-icon" aria-hidden="true"><svg viewBox="0 0 68 68" focusable="false">{icon}</svg></span>'


def category_lookup(slug):
    for category in PRODUCT_CATEGORIES:
        if category["slug"] == slug:
            return category
    return None


def category_cards():
    cards = ""
    for category in PRODUCT_CATEGORIES:
        cards += f"""
        <a class="category-card" href="{esc(category["href"])}" aria-label="Explore {esc(category["title"])}">
          <span class="category-card__media">
            <img src="{esc(category["image"])}" alt="{esc(category["title"])} packaging category" loading="lazy" onerror="this.hidden=true; this.closest('.category-card__media').classList.add('is-missing-image');">
          </span>
          <strong>{esc(category["title"])}</strong>
        </a>
        """
    return cards


CERTIFICATION_LOGOS = [
    {
        "name": "BRCGS Certified",
        "detail": "Packaging materials and food safety standards",
        "image": "/static/images/certifications/brcgs.webp",
    },
    {
        "name": "FSC Certified",
        "detail": "Responsible fibre sourcing",
        "image": "/static/images/certifications/fsc.webp",
    },
    {
        "name": "ISO 9001",
        "detail": "Quality management systems",
        "image": "/static/images/certifications/iso-9001.webp",
    },
    {
        "name": "amfori BSCI",
        "detail": "Social compliance support",
        "image": "/static/images/certifications/amfori-bsci.webp",
    },
    {
        "name": "Sedex / SMETA",
        "detail": "Ethical trade audit support",
        "image": "/static/images/certifications/sedex-smeta.webp",
    },
    {
        "name": "BPI Compostable",
        "detail": "Certified compostable materials",
        "image": "/static/images/certifications/bpi-compostable.webp",
    },
    {
        "name": "USDA BioPreferred",
        "detail": "Bio-based product programme",
        "image": "/static/images/certifications/usda-biopreferred.webp",
    },
    {
        "name": "FDA Compliant",
        "detail": "Food contact safety",
        "image": "/static/images/certifications/fda-compliant.webp",
    },
    {
        "name": "GRS / rPET",
        "detail": "Global recycled material standard",
        "image": "/static/images/certifications/grs-rpet.webp",
    },
    {
        "name": "OK Compost HOME",
        "detail": "Home compost certification support",
        "image": "/static/images/certifications/ok-compost-home.webp",
    },
]


def certification_logo_cards():
    cards = ""
    for cert in CERTIFICATION_LOGOS:
        cards += f"""
        <article class="cert-logo-card">
          <span class="cert-logo-card__media" data-label="{esc(cert["name"])}">
            <img src="{esc(cert["image"])}" alt="{esc(cert["name"])} logo" loading="lazy" onerror="this.remove(); this.closest('.cert-logo-card').classList.add('is-missing-logo');">
          </span>
          <strong>{esc(cert["name"])}</strong>
        </article>
        """
    return cards


def cup_accessories_cards(csrf_html=""):
    cards = ""
    sorted_products = sorted(PUBLIC_PRODUCTS, key=lambda product: 1 if "lid" in product["name"].lower() else 0)
    for product in sorted_products:
        product_id = esc(product["id"])
        display_name = quote_product_name(product)
        carton_text = quote_carton_text(product)
        lid_text = quote_lid_text(product)
        cards += f"""
        <article class="category-product-card">
          <a class="category-product-card__image" href="/products/cups-cup-accessories" aria-label="Quote {esc(display_name)} {esc(product["size"])}">
            <img src="{esc(product["image"])}" alt="{esc(product["name"])} {esc(product["size"])}" loading="lazy" decoding="async">
          </a>
          <div class="category-product-card__body">
            <span class="category-product-card__tag">{esc(product["type"])}</span>
            <h3>{esc(display_name)}</h3>
            <p class="category-product-card__size">{esc(product["size"])}</p>
            <p>{esc(carton_text)} &middot; {esc(lid_text)}</p>
            <form class="category-product-card__cart" method="post" data-quote-add-form>
              {csrf_html}
              <input type="hidden" name="action" value="add_to_quote">
              <input type="hidden" name="product_id" value="{product_id}">
              <label for="category_qty_{product_id}">Qty of Cartons</label>
              <div>
                <input id="category_qty_{product_id}" name="quantity" type="number" min="1" step="1" inputmode="numeric" value="1" aria-label="Quantity of cartons for {esc(display_name)} {esc(product["size"])}">
                <button type="submit">Add to Quote</button>
              </div>
              <span class="quote-add-status" data-quote-add-status aria-live="polite"></span>
            </form>
          </div>
        </article>
        """
    return cards


def cups_filter_panel():
    filter_groups = [
        "Product Type",
        "Cup Size",
        "Wall Type",
        "Lid Compatibility",
        "Material",
        "Carton Quantity",
        "Custom Print",
    ]
    groups = "".join(
        f'<button class="category-filter-row" type="button"><span>{esc(group)}</span><span aria-hidden="true">+</span></button>'
        for group in filter_groups
    )
    return f"""
    <aside class="category-filters" aria-label="Product filters">
      <div class="category-filters__head">
        <span aria-hidden="true">Filter</span>
        <a href="/products/cups-cup-accessories">Reset all</a>
      </div>
      <div class="category-filter-help">
        <strong>I want to</strong>
        <p>Review cup sizes, wall types and lid compatibility before requesting a quote.</p>
        <a href="/quote-cart">Quote Cart</a>
      </div>
      {groups}
    </aside>
    """


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
        product_category_cards = category_cards()
        certification_cards = certification_logo_cards()
        body = f"""
        <section class="hero hero-carousel" aria-label="AUREA packaging highlights">
          <div class="hero-slide is-active" data-hero-slide data-hero-image="/static/hero-warehouse-supply.webp" style="--hero-image: url('/static/hero-warehouse-supply.webp')">
            <div class="hero-copy">
              <p class="eyebrow">Manufacturer + Direct Sales</p>
              <h1>Full product range from both factories</h1>
              <p>Paper cups, bowls, take-out boxes, bags, labels and sustainable packaging for every business.</p>
              <div class="hero-actions">
                <a class="button primary" href="/products/cups-cup-accessories">Start Quote Cart</a>
                <a class="button ghost" href="#product-categories">View Categories</a>
              </div>
            </div>
          </div>
          <div class="hero-slide" data-hero-slide data-hero-image="/static/hero-logistics-delivery.webp">
            <div class="hero-copy">
              <p class="eyebrow">AU Local Warehouse</p>
              <h1>Local stock. Same-week dispatch.</h1>
              <p>Factory-direct pricing with Australian warehouse speed and replenishment planning support.</p>
              <div class="hero-actions">
                <a class="button primary" href="/products/cups-cup-accessories">Plan Supply</a>
                <a class="button ghost" href="#contact">Delivery Enquiry</a>
              </div>
            </div>
          </div>
          <div class="hero-slide" data-hero-slide data-hero-image="/static/hero-cafe-cups.webp">
            <div class="hero-copy">
              <p class="eyebrow">Paper Cups</p>
              <h1>Paper cups, lids and cup carriers</h1>
              <p>Single, double and ripple wall options with PLA or PE materials and custom branding support.</p>
              <div class="hero-actions">
                <a class="button primary" href="/products/cups-cup-accessories">Quote Cafe SKUs</a>
                <a class="button ghost" href="#contact">Ask for Samples</a>
              </div>
            </div>
          </div>
          <div class="hero-slide" data-hero-slide data-hero-image="/static/hero-restaurant-takeaway.webp">
            <div class="hero-copy">
              <p class="eyebrow">Take-out Packaging</p>
              <h1>Bowls, take-out boxes and paper bags</h1>
              <p>Soup and salad bowls, folded kraft boxes, sugarcane tableware and food-grade bag options.</p>
              <div class="hero-actions">
                <a class="button primary" href="#product-categories">Explore Categories</a>
                <a class="button ghost" href="#contact">Ask About Supply</a>
              </div>
            </div>
          </div>
          <div class="hero-slide" data-hero-slide data-hero-image="/static/hero-design-stickers.webp">
            <div class="hero-copy">
              <p class="eyebrow">Free Brand Design</p>
              <h1>Custom printed cups, labels and sushi boxes</h1>
              <p>Logo printing, sticker labels, branded napkins and premium packaging artwork support.</p>
              <div class="hero-actions">
                <a class="button primary" href="#contact">Start Custom Design</a>
                <a class="button ghost" href="#product-categories">View Packaging Range</a>
              </div>
            </div>
          </div>
          <div class="hero-dots" aria-label="Carousel controls">
            <button type="button" class="is-active" data-hero-dot aria-label="Show packaging range slide"></button>
            <button type="button" data-hero-dot aria-label="Show logistics delivery slide"></button>
            <button type="button" data-hero-dot aria-label="Show coffee cups slide"></button>
            <button type="button" data-hero-dot aria-label="Show takeaway packaging slide"></button>
            <button type="button" data-hero-dot aria-label="Show custom design and sticker printing slide"></button>
          </div>
        </section>

        <section id="product-categories" class="category-section">
          <div class="section-head">
            <h2>Shop by Product Category</h2>
          </div>
          <div class="category-grid">{product_category_cards}</div>
        </section>

        <section id="about" class="why-choose-section">
          <div class="partnership-banner">
            <div class="partnership-copy">
              <p class="eyebrow">Packaging Partnership</p>
              <h2>Helping foodservice businesses grow with reliable packaging solutions.</h2>
              <p>Supporting cafés, restaurants, takeaway operators and wholesale partners with dependable packaging supply.</p>
              <a class="button primary" href="/products/cups-cup-accessories">Add Products to Quote</a>
            </div>
          </div>
        </section>

        <script>
          (() => {{
            const slides = Array.from(document.querySelectorAll("[data-hero-slide]"));
            const dots = Array.from(document.querySelectorAll("[data-hero-dot]"));
            if (!slides.length || !dots.length) return;
            let active = 0;
            const show = (index) => {{
              active = (index + slides.length) % slides.length;
              const nextSlide = slides[active];
              const heroImage = nextSlide.dataset.heroImage;
              if (heroImage && !nextSlide.style.getPropertyValue("--hero-image")) {{
                nextSlide.style.setProperty("--hero-image", `url('${{heroImage}}')`);
              }}
              slides.forEach((slide, slideIndex) => slide.classList.toggle("is-active", slideIndex === active));
              dots.forEach((dot, dotIndex) => dot.classList.toggle("is-active", dotIndex === active));
            }};
            dots.forEach((dot, index) => dot.addEventListener("click", () => show(index)));
            window.setInterval(() => show(active + 1), 4000);
          }})();
        </script>

        <section id="certifications" class="cert-logo-section">
          <div class="cert-logo-intro">
            <h2>Verified Certifications</h2>
            <p>Food-safe packaging from trusted manufacturing partners.</p>
          </div>
          <div class="cert-logo-grid">{certification_cards}</div>
        </section>

        <section id="contact" class="contact-section">
          <div>
            <p class="eyebrow">Contact</p>
            <h2>Talk to AUREA</h2>
            <p>Send a quick order enquiry or contact us directly for sustainable packaging, custom print, samples and stock availability.</p>
          </div>
          <div class="contact-card">
            <strong>AUREA Packaging Supply Pty Ltd</strong>
            <a href="tel:{PUBLIC_PHONE_TEL}">{PUBLIC_PHONE_DISPLAY}</a>
            <a href="mailto:{PUBLIC_EMAIL}">{PUBLIC_EMAIL}</a>
            <a href="https://{PUBLIC_WEBSITE}">{PUBLIC_WEBSITE}</a>
            <span>{PUBLIC_LOCATION}</span>
          </div>
        </section>

        """
        self.respond(layout("Product Catalogue", body, self.is_authed(), quote_cart_count=self.quote_cart_count()))

    def product_category_page(self, slug):
        category = category_lookup(slug)
        if not category:
            return self.redirect("/#product-categories")
        if slug == "cups-cup-accessories":
            if self.command == "POST":
                f = self.form()
                if f.get("action") == "add_to_quote":
                    wants_json = self.headers.get("X-Requested-With") == "XMLHttpRequest"
                    products = product_by_id()
                    product_id = f.get("product_id")
                    try:
                        qty = safe_int(f.get("quantity"), default=1)
                    except ValueError:
                        qty = 0
                    if product_id not in products or qty < 1:
                        if wants_json:
                            return self.respond(
                                json.dumps({"ok": False, "message": "Please enter a carton quantity of at least 1."}),
                                status=400,
                                content_type="application/json",
                            )
                        return self.redirect("/products/cups-cup-accessories?error=quantity")
                    cart = self.quote_cart_data()
                    cart[product_id] = int(cart.get(product_id, 0)) + qty
                    cookie = self.quote_cart_cookie(cart)
                    if wants_json:
                        return self.respond(
                            json.dumps({
                                "ok": True,
                                "message": "Added to Quote Cart.",
                                "quoteCartCount": quote_cart_count(cart),
                            }),
                            content_type="application/json",
                            cookies=[cookie],
                        )
                    return self.redirect(
                        "/products/cups-cup-accessories?added=1",
                        cookies=[cookie],
                    )
            notice = ""
            query = parse_qs(urlparse(self.path).query)
            if query.get("added", [""])[0]:
                notice = '<p class="notice">Added to Quote Cart.</p>'
            elif query.get("error", [""])[0] == "quantity":
                notice = '<p class="alert">Please enter a carton quantity of at least 1.</p>'
            product_cards = cup_accessories_cards(self.csrf_input())
            filters = cups_filter_panel()
            body = f"""
            <section class="category-hero category-hero--cups">
              <div>
                <p class="eyebrow">Product Category</p>
                <h1>Cups &amp; Cup Accessories</h1>
              </div>
            </section>
            <section class="category-intro">
              <p>Browse AUREA coffee cups, matching lids and cafe-ready carton options. Add products to your Quote Cart and send one B2B enquiry.</p>
            </section>
            {notice}
            <section class="category-shop-layout">
              {filters}
              <div class="category-results">
                <div class="category-results__bar">
                  <span>{len(PUBLIC_PRODUCTS)} products</span>
                  <label>
                    Sort by
                    <select aria-label="Sort products">
                      <option>Best Match</option>
                      <option>Size</option>
                      <option>Wall Type</option>
                    </select>
                  </label>
                </div>
                <div class="category-sale-strip">
                  <strong>Cafe supply made simple</strong>
                  <span>Carton pricing confirmed after quote request</span>
                </div>
                <div class="category-product-grid">
                  {product_cards}
                </div>
              </div>
            </section>
            <script>
              (() => {{
                const forms = Array.from(document.querySelectorAll("[data-quote-add-form]"));
                const cartLink = document.querySelector("[data-quote-cart-link]");
                if (!forms.length || !window.fetch || !window.FormData) return;
                forms.forEach((form) => {{
                  form.addEventListener("submit", async (event) => {{
                    event.preventDefault();
                    const button = form.querySelector("button[type='submit']");
                    const status = form.querySelector("[data-quote-add-status]");
                    if (button) button.disabled = true;
                    if (status) status.textContent = "";
                    try {{
                      const response = await fetch(window.location.pathname, {{
                        method: "POST",
                        body: new URLSearchParams(new FormData(form)),
                        headers: {{
                          "Content-Type": "application/x-www-form-urlencoded",
                          "X-Requested-With": "XMLHttpRequest"
                        }},
                        credentials: "same-origin"
                      }});
                      const contentType = response.headers.get("content-type") || "";
                      const result = contentType.includes("application/json")
                        ? await response.json()
                        : {{ok: false, message: await response.text()}};
                      if (!response.ok || !result.ok) throw new Error(result.message || "Unable to add product.");
                      if (cartLink && Number.isInteger(result.quoteCartCount)) {{
                        cartLink.textContent = `Quote Cart (${{result.quoteCartCount}})`;
                      }}
                      if (status) status.textContent = result.message || "Added to Quote Cart.";
                    }} catch (error) {{
                      if (status) status.textContent = error.message || "Unable to add product.";
                    }} finally {{
                      if (button) button.disabled = false;
                    }}
                  }});
                }});
              }})();
            </script>
            """
            return self.respond(layout("Cups & Cup Accessories", body, self.is_authed(), quote_cart_count=self.quote_cart_count()))
        if category["href"] == "/#products":
            return self.redirect("/products/cups-cup-accessories")
        body = f"""
        <section class="category-placeholder-page">
          <div class="category-placeholder__image">
            <img src="{esc(category["image"])}" alt="{esc(category["title"])} packaging category" loading="lazy" onerror="this.hidden=true; this.closest('.category-placeholder__image').classList.add('is-missing-image');">
          </div>
          <div class="category-placeholder__copy">
            <p class="eyebrow">Product Category</p>
            <h1>{esc(category["title"])}</h1>
            <strong>Coming Soon</strong>
            <p>{esc(category["description"])} Product details, pack sizes and image galleries will be added here as the range is finalised.</p>
            <div class="hero-actions">
              <a class="button primary" href="/#contact">Contact Us</a>
              <a class="button ghost" href="/quote-cart">Quote Cart</a>
            </div>
          </div>
        </section>
        """
        self.respond(layout(category["title"], body, self.is_authed(), quote_cart_count=self.quote_cart_count()))

    def quote_cart(self):
        notice = ""
        query = parse_qs(urlparse(self.path).query)
        if query.get("submitted", [""])[0]:
            body = f"""
            <section class="section-head"><h1>Quote Request Sent</h1><p>Thank you. AUREA will review your selected products and contact you shortly.</p></section>
            <section class="panel quote-cart-success">
              <strong>Quote request submitted successfully.</strong>
              <p>Your Quote Cart has been cleared for the next request.</p>
              <div class="form-actions">
                <a class="button primary" href="/products/cups-cup-accessories">Start Another Quote Cart</a>
                <a class="button secondary" href="/">Back to Home</a>
              </div>
            </section>
            """
            return self.respond(layout("Quote Request Sent", body, self.is_authed(), quote_cart_count=self.quote_cart_count()))
        elif query.get("updated", [""])[0]:
            notice = '<p class="notice">Quote Cart updated.</p>'
        elif query.get("removed", [""])[0]:
            notice = '<p class="notice">Quote Cart line removed.</p>'
        elif query.get("error", [""])[0] == "details":
            notice = '<p class="alert">Please enter business name, contact name, email and phone before submitting.</p>'
        elif query.get("error", [""])[0] == "empty":
            notice = '<p class="alert">Please add at least one product before submitting a quote request.</p>'

        cart = self.quote_cart_data()
        products = product_by_id()

        if self.command == "POST":
            f = self.form()
            action = f.get("action")
            product_id = f.get("product_id")
            if action == "update":
                updated = {}
                for key, value in f.items():
                    if not key.startswith("qty_"):
                        continue
                    item_id = key.removeprefix("qty_")
                    if item_id not in products:
                        continue
                    try:
                        qty = int(value or 0)
                    except ValueError:
                        qty = 0
                    if qty > 0:
                        updated[item_id] = qty
                return self.redirect("/quote-cart?updated=1", cookies=[self.quote_cart_cookie(updated)])
            if action == "remove":
                if product_id in cart:
                    cart.pop(product_id)
                return self.redirect("/quote-cart?removed=1", cookies=[self.quote_cart_cookie(cart)])
            if action == "submit":
                if not cart:
                    cart = parse_quote_cart(verify(f.get("cart_snapshot"), max_age=3600) or "")
                items = quote_cart_items(cart)
                if not items:
                    return self.redirect("/quote-cart?error=empty")
                required = ["business_name", "contact_name", "email", "phone"]
                if any(not (f.get(field) or "").strip() for field in required):
                    return self.redirect("/quote-cart?error=details")
                line_text = quote_cart_lines_text(cart)
                customer_notes = f.get("notes") or ""
                message = line_text
                if customer_notes:
                    message = f"{message}\n\nCustomer notes: {customer_notes}"
                item_count = quote_cart_count(cart)
                total_cartons = quote_cart_total_cartons(cart)
                with db() as conn:
                    conn.execute(
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
                            f"{item_count} quote-cart items",
                            f"Total {total_cartons} cartons",
                            message,
                        ),
                    )
                return self.redirect("/quote-cart?submitted=1", cookies=[self.quote_cart_cookie({}, max_age=0)])

        items = quote_cart_items(cart)
        if items:
            rows = ""
            for item in items:
                product = item["product"]
                product_id = esc(product["id"])
                rows += f"""
                <tr>
                  <td>{product_id}</td>
                  <td>{esc(quote_product_name(product))}</td>
                  <td>{esc(product["size"])}</td>
                  <td><input form="quote-cart-update-form" name="qty_{product_id}" type="number" min="0" step="1" value="{esc(item["qty"])}" aria-label="Cartons for {esc(quote_product_name(product))}"></td>
                  <td>
                    <form method="post" class="inline-form">
                      {self.csrf_input()}
                      <input type="hidden" name="action" value="remove">
                      <input type="hidden" name="product_id" value="{product_id}">
                      <button class="link-button" type="submit">Remove</button>
                    </form>
                  </td>
                </tr>
                """
            cart_table = f"""
            <form id="quote-cart-update-form" method="post" class="quote-cart-update">
              {self.csrf_input()}
              <input type="hidden" name="action" value="update">
            </form>
            <div class="table-wrap quote-cart-table">
              <table>
                <thead><tr><th>Code</th><th>Product</th><th>Size</th><th>Cartons</th><th>Action</th></tr></thead>
                <tbody>{rows}</tbody>
              </table>
            </div>
            <div class="form-actions">
              <button form="quote-cart-update-form" class="button secondary" type="submit">Update Quantities</button>
              <a class="button secondary" href="/products/cups-cup-accessories">Add More Products</a>
            </div>
            """
            submit_disabled = ""
        else:
            cart_table = """
            <section class="panel">
              <div class="quote-empty">
                <strong>Your Quote Cart is empty.</strong>
                <p>Add products from Cups & Cup Accessories to build a quote request.</p>
                <a class="button primary" href="/products/cups-cup-accessories">Add Products to Quote</a>
              </div>
            </section>
            """
            submit_disabled = "disabled"

        total_cartons = quote_cart_total_cartons(cart)
        body = f"""
        <section class="section-head"><h1>Quote Cart</h1><p>Review carton quantities and send one B2B quote request to AUREA.</p></section>
        {notice}
        <section class="panel quote-cart-summary">
          <strong>{esc(quote_cart_count(cart))} items</strong>
          <span>Total {esc(total_cartons)} cartons</span>
        </section>
        {cart_table}
        <section class="panel">
          <h2>Submit Quote Request</h2>
          <form method="post" class="form grid-form">
            {self.csrf_input()}
            <input type="hidden" name="action" value="submit">
            <input type="hidden" name="cart_snapshot" value="{esc(sign(quote_cart_value(cart)))}">
            <label>Business name<input name="business_name" required {submit_disabled}></label>
            <label>Contact person<input name="contact_name" required {submit_disabled}></label>
            <label>Email<input name="email" type="email" required {submit_disabled}></label>
            <label>Phone<input name="phone" required {submit_disabled}></label>
            <label>Notes<textarea name="notes" rows="3" {submit_disabled}></textarea></label>
            <button class="button primary" type="submit" {submit_disabled}>Submit Quote Request</button>
          </form>
        </section>
        """
        self.respond(layout("Quote Cart", body, self.is_authed(), quote_cart_count=self.quote_cart_count()))

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
                    <a class="button primary" href="/products/cups-cup-accessories">Choose Products</a>
                  </div>
                </section>
                """
                return self.respond(layout("Request Quote", body, self.is_authed(), quote_cart_count=self.quote_cart_count()))
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
            return self.respond(layout("Quotation Draft", body, self.is_authed(), quote_cart_count=self.quote_cart_count()))
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
            <img src="/static/aurea-logo-light.webp" alt="AUREA Packaging Supply Pty Ltd" loading="lazy" decoding="async">
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
        self.respond(layout("Request Quote", body, self.is_authed(), quote_cart_count=self.quote_cart_count()))

