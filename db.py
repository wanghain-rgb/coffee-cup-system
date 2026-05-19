import os
import sqlite3
import sys

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None

# Render's normal/free filesystem is ephemeral. If this SQLite file is stored
# there, business data can be lost on redeploy/restart/spin-down. Use
# PostgreSQL or a Render persistent disk for production data.
DB_PATH = os.path.join(os.path.dirname(__file__), "cupflow.sqlite3")
DATABASE_URL = os.environ.get("DATABASE_URL")
class DbCursor:
    def __init__(self, cursor, lastrowid=None):
        self.cursor = cursor
        self.lastrowid = lastrowid if lastrowid is not None else getattr(cursor, "lastrowid", None)
        self.rowcount = getattr(cursor, "rowcount", -1)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()


class DbConnection:
    RETURNING_TABLES = {"quote_requests", "purchase_batches", "purchase_orders", "sales_orders", "invoices"}

    def __init__(self):
        self.is_postgres = bool(DATABASE_URL)
        if self.is_postgres:
            if psycopg2 is None:
                raise RuntimeError("DATABASE_URL is set but psycopg2 is not installed.")
            self.conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
        else:
            self.conn = sqlite3.connect(DB_PATH)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.conn.close()

    def _sql(self, sql):
        return sql.replace("?", "%s") if self.is_postgres else sql

    def _insert_returning_sql(self, sql):
        if not self.is_postgres or "RETURNING" in sql.upper():
            return sql
        cleaned = sql.strip()
        upper = cleaned.upper()
        if not upper.startswith("INSERT INTO "):
            return sql
        table = cleaned.split()[2].strip('"')
        if table in self.RETURNING_TABLES:
            return f"{sql.rstrip()} RETURNING id"
        return sql

    def execute(self, sql, params=()):
        cursor = self.conn.cursor()
        sql = self._insert_returning_sql(self._sql(sql))
        cursor.execute(sql, params)
        lastrowid = None
        if self.is_postgres and "RETURNING id" in sql:
            row = cursor.fetchone()
            lastrowid = row["id"] if row else None
        return DbCursor(cursor, lastrowid)

    def executemany(self, sql, seq):
        cursor = self.conn.cursor()
        cursor.executemany(self._sql(sql), seq)
        return DbCursor(cursor)

    def executescript(self, script):
        if not self.is_postgres:
            return self.conn.executescript(script)
        cursor = self.conn.cursor()
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
        return cursor

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()


def db():
    return DbConnection()


def ensure_column(conn, table, column, ddl):
    if conn.is_postgres:
        existing = {
            row["column_name"]
            for row in conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = ?
                """,
                (table,),
            ).fetchall()
        }
    else:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    size TEXT NOT NULL,
    qty_per_carton INTEGER NOT NULL DEFAULT 1000,
    sell_price REAL NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_name TEXT NOT NULL,
    contact_name TEXT,
    email TEXT,
    phone TEXT,
    suburb TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_code TEXT UNIQUE NOT NULL,
    supplier_name TEXT NOT NULL,
    abn TEXT,
    contact_person TEXT,
    email TEXT,
    phone TEXT,
    address_line_1 TEXT,
    address_line_2 TEXT,
    suburb TEXT,
    state TEXT,
    postcode TEXT,
    country TEXT,
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS quote_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_name TEXT NOT NULL,
    contact_name TEXT,
    email TEXT NOT NULL,
    phone TEXT,
    product_interest TEXT,
    monthly_volume TEXT,
    message TEXT,
    status TEXT NOT NULL DEFAULT 'New',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchase_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier TEXT NOT NULL,
    invoice_no TEXT,
    freight_cost REAL NOT NULL DEFAULT 0,
    batch_date TEXT NOT NULL DEFAULT CURRENT_DATE,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS purchase_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES purchase_batches(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty_cartons INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    freight_alloc REAL NOT NULL DEFAULT 0,
    remaining_cartons INTEGER NOT NULL,
    landed_unit_cost REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    order_date TEXT NOT NULL DEFAULT CURRENT_DATE,
    status TEXT NOT NULL DEFAULT 'Draft',
    subtotal_ex_gst REAL NOT NULL DEFAULT 0,
    gst_amount REAL NOT NULL DEFAULT 0,
    total_inc_gst REAL NOT NULL DEFAULT 0,
    notes TEXT,
    confirmed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchase_order_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_order_id INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    product_code TEXT,
    description TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 0,
    unit_price_ex_gst REAL NOT NULL DEFAULT 0,
    gst_amount REAL NOT NULL DEFAULT 0,
    subtotal_ex_gst REAL NOT NULL DEFAULT 0,
    total_inc_gst REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sales_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    order_date TEXT NOT NULL DEFAULT CURRENT_DATE,
    status TEXT NOT NULL DEFAULT 'Draft',
    notes TEXT,
    confirmed_at TEXT
);

CREATE TABLE IF NOT EXISTS sales_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty_cartons INTEGER NOT NULL,
    sell_price REAL NOT NULL,
    cost_price REAL NOT NULL,
    revenue REAL NOT NULL,
    cost REAL NOT NULL,
    gross_profit REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS company_master (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    company_name TEXT NOT NULL DEFAULT 'AUREA Packaging Supply Pty Ltd',
    abn TEXT,
    address TEXT,
    phone TEXT,
    email TEXT,
    website TEXT,
    bank_name TEXT,
    account_name TEXT,
    bsb TEXT,
    account_number TEXT,
    payment_instructions TEXT
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    sales_order_id INTEGER REFERENCES sales_orders(id),
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    customer_business_name TEXT,
    customer_abn TEXT,
    billing_address TEXT,
    shipping_address TEXT,
    issue_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Draft',
    subtotal_ex_gst REAL NOT NULL DEFAULT 0,
    gst_amount REAL NOT NULL DEFAULT 0,
    total_inc_gst REAL NOT NULL DEFAULT 0,
    total_paid REAL NOT NULL DEFAULT 0,
    balance_due REAL NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoice_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id),
    product_code TEXT,
    description TEXT NOT NULL,
    size TEXT,
    product_type TEXT,
    carton_quantity INTEGER,
    quantity REAL NOT NULL DEFAULT 0,
    unit_price_ex_gst REAL NOT NULL DEFAULT 0,
    tax_type TEXT NOT NULL DEFAULT 'GST',
    subtotal_ex_gst REAL NOT NULL DEFAULT 0,
    gst_amount REAL NOT NULL DEFAULT 0,
    total_inc_gst REAL NOT NULL DEFAULT 0
);
"""

POSTGRES_SCHEMA = SQLITE_SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")


def init_db():
    with db() as conn:
        conn.executescript(POSTGRES_SCHEMA if conn.is_postgres else SQLITE_SCHEMA)
        ensure_column(conn, "customers", "abn", "abn TEXT")
        ensure_column(conn, "customers", "billing_address", "billing_address TEXT")
        ensure_column(conn, "customers", "shipping_address", "shipping_address TEXT")
        ensure_column(conn, "products", "product_type", "product_type TEXT")
        ensure_column(conn, "products", "tax_type", "tax_type TEXT NOT NULL DEFAULT 'GST'")
        ensure_column(conn, "products", "barcode", "barcode TEXT")
        ensure_column(conn, "products", "stock_qty", "stock_qty REAL NOT NULL DEFAULT 0")
        ensure_column(conn, "products", "avg_cost", "avg_cost REAL NOT NULL DEFAULT 0")
        ensure_column(conn, "sales_orders", "confirmed_at", "confirmed_at TEXT")
        ensure_column(conn, "invoices", "sales_order_id", "sales_order_id INTEGER REFERENCES sales_orders(id)")
        ensure_column(conn, "invoices", "customer_business_name", "customer_business_name TEXT")
        ensure_column(conn, "invoices", "customer_abn", "customer_abn TEXT")
        ensure_column(conn, "invoices", "billing_address", "billing_address TEXT")
        ensure_column(conn, "invoices", "shipping_address", "shipping_address TEXT")

        if conn.is_postgres:
            conn.execute(
                """
                INSERT INTO company_master
                (id, company_name, phone, email, website, address, payment_instructions)
                VALUES (1, 'AUREA Packaging Supply Pty Ltd', '0497278099',
                        'info@aureapackaging.com.au', 'https://aureapackaging.com.au',
                        'Melbourne, Australia', 'Payment terms: To be confirmed.')
                ON CONFLICT (id) DO NOTHING
                """
            )
        else:
            conn.execute(
                """
                INSERT OR IGNORE INTO company_master
                (id, company_name, phone, email, website, address, payment_instructions)
                VALUES (1, 'AUREA Packaging Supply Pty Ltd', '0497278099',
                        'info@aureapackaging.com.au', 'https://aureapackaging.com.au',
                        'Melbourne, Australia', 'Payment terms: To be confirmed.')
                """
            )

        product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if product_count == 0:
            conn.executemany(
                """
                INSERT INTO products (sku, name, size, qty_per_carton, sell_price)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    ("CUP-8DW", "8oz Double Wall Coffee Cup", "8oz", 500, 72.00),
                    ("CUP-12SW", "12oz Single Wall Coffee Cup", "12oz", 1000, 89.00),
                    ("LID-80W", "White Sip Lid 80mm", "80mm", 1000, 42.00),
                ],
            )
        customer_count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        if customer_count == 0:
            conn.execute(
                """
                INSERT INTO customers (business_name, contact_name, email, phone, suburb, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "Sample Cafe",
                    "Alex Chen",
                    "orders@samplecafe.example",
                    "0400 000 000",
                    "Surry Hills",
                    "Demo customer for first sales order.",
                ),
            )


