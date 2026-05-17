import os
import sqlite3
import sys

import psycopg2
import psycopg2.extras

import app


TABLES = [
    "company_master",
    "products",
    "customers",
    "suppliers",
    "quote_requests",
    "purchase_batches",
    "purchase_lines",
    "purchase_orders",
    "purchase_order_lines",
    "sales_orders",
    "sales_lines",
    "invoices",
    "invoice_lines",
]


def sqlite_columns(conn, table):
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def postgres_columns(conn, table):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
            """,
            (table,),
        )
        return [row["column_name"] for row in cur.fetchall()]


def migrate_table(sqlite_conn, pg_conn, table):
    sqlite_cols = sqlite_columns(sqlite_conn, table)
    pg_cols = postgres_columns(pg_conn, table)
    cols = [col for col in sqlite_cols if col in pg_cols]
    if not cols:
        print(f"Skipping {table}: no matching columns")
        return

    rows = sqlite_conn.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()
    if not rows:
        print(f"{table}: no rows")
        return

    quoted_cols = ", ".join(f'"{col}"' for col in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    sql = f"INSERT INTO {table} ({quoted_cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    values = [[row[col] for col in cols] for row in rows]
    with pg_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, values, page_size=100)
        if "id" in cols:
            cur.execute("SELECT pg_get_serial_sequence(%s, 'id') AS seq", (table,))
            seq = cur.fetchone()["seq"]
            if seq:
                cur.execute(
                    f"SELECT setval(%s, COALESCE((SELECT MAX(id) FROM {table}), 1), true)",
                    (seq,),
                )
    pg_conn.commit()
    print(f"{table}: migrated {len(rows)} rows")


def main():
    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else app.DB_PATH
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required for migration.")
    if not os.path.exists(sqlite_path):
        raise SystemExit(f"SQLite database not found: {sqlite_path}")

    print("Creating PostgreSQL schema if needed...")
    app.init_db()

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.DictCursor)
    try:
        for table in TABLES:
            migrate_table(sqlite_conn, pg_conn, table)
    finally:
        sqlite_conn.close()
        pg_conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    main()
