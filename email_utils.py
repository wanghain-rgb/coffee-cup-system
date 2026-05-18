from email.message import EmailMessage
import os
import smtplib

from utils import esc, money

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


