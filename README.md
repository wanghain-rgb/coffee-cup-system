# CupFlow MVP

A simple B2B coffee cup catalogue and inventory CRM for a small Australian supplier.

## Features

- Public product catalogue
- Public quote request form
- Admin login
- Product master
- Customer master
- Purchase batch management with freight allocation
- Inventory balance by SKU
- Sales order entry
- FIFO batch costing and gross profit calculation

## Technology

- Python standard library web server
- SQLite database
- Plain HTML/CSS forms
- No package install required

## Run

```powershell
python app.py
```

Open:

```text
http://127.0.0.1:8000
```

Admin login:

```text
Username: admin
Password: admin123
```

For real use, set environment variables before starting:

```powershell
$env:ADMIN_PASSWORD="choose-a-strong-password"
$env:CUPFLOW_SECRET="choose-a-long-random-secret"
python app.py
```

## Notes

The app creates `cupflow.sqlite3` on first run and seeds a few demo products and one demo customer.

Important production note: SQLite stored on Render's normal/free filesystem is not persistent across redeploys, restarts, or spin-downs. For production business data, use PostgreSQL or attach a Render persistent disk and point the application database path there.

This is intentionally an MVP. Logical next steps would be product/customer editing, multi-line orders, invoice PDF export, quote-to-customer conversion, and role-based users.
