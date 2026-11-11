"""PostgreSQL execution path for parity runs (Sprint 3).

The database lives inside the write root (.pgdata); nothing is created
elsewhere. Staging tables are TEXT-only (see sql/00_staging.sql): no
implicit casts at load, all parsing happens inside rule views through
regex-guarded casts. COPY runs over STDIN so no server-side file paths
are needed.

Connection order (CI-safe): DATABASE_URL first; else a local
.pgsql/.pgdata instance if present; else callers must skip parity
tests with the returned reason. If CI=true and DATABASE_URL is set
but unreachable, connecting raises and the tests FAIL (no skip).
"""

import os

import pandas as pd
import psycopg

HOST = "localhost"
PORT = 5433
USER = "postgres"
DBNAME = "quickmart"

ORDERS_COLUMNS = (
    "order_id", "customer_id", "product_id", "order_date", "quantity",
    "unit_price_paid", "discount", "payment_mode", "order_status",
    "delivery_days", "notes",
    "raw_order_id", "raw_customer_id", "raw_product_id", "raw_order_date",
    "raw_quantity", "raw_unit_price_paid", "raw_discount", "raw_payment_mode",
    "raw_order_status", "raw_delivery_days", "raw_notes",
    "_source_row", "source_file", "source_row_number", "dedup_rule_applied",
    "rules_passed", "rules_failed",
)

CUSTOMERS_COLUMNS = (
    "customer_id", "customer_name", "email", "city", "phone", "signup_date",
    "raw_customer_id", "raw_customer_name", "raw_email", "raw_city",
    "raw_phone", "raw_signup_date",
    "_source_row", "source_file", "source_row_number", "dedup_rule_applied",
    "rules_passed", "rules_failed",
)

PRODUCTS_COLUMNS = (
    "product_id", "product_name", "category", "unit_price", "stock_qty",
    "raw_product_id", "raw_product_name", "raw_category", "raw_unit_price",
    "raw_stock_qty",
    "_source_row", "source_file", "source_row_number", "dedup_rule_applied",
    "rules_passed", "rules_failed",
)


def _local_present() -> bool:
    """True when a local write-root postgres instance exists."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    return (root / ".pgdata" / "PG_VERSION").exists() or (root / ".pgsql").exists()


def resolve_backend() -> tuple[str, str]:
    """Return (backend, detail) in priority order.

    "database_url" first when DATABASE_URL is set (even in CI);
    else "local" when a write-root .pgsql/.pgdata instance is present;
    else "none" with a human-readable skip reason.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return ("database_url", "DATABASE_URL is set")
    if _local_present():
        return ("local", "local .pgsql/.pgdata instance present")
    return ("none", "no DATABASE_URL and no local .pgsql/.pgdata instance")


def should_fail_fast() -> bool:
    """True when CI=true and DATABASE_URL is set: unreachable DB must FAIL."""
    return os.environ.get("CI", "").strip().lower() == "true" and bool(
        os.environ.get("DATABASE_URL", "").strip()
    )


def connect(url: str | None = None, timeout: int = 5):
    """Connect (autocommit). DATABASE_URL wins; else the local instance.

    timeout bounds every attempt so an unreachable database fails fast
    instead of hanging the suite.
    """
    if url is None:
        url = os.environ.get("DATABASE_URL", "").strip() or None
    if url:
        return psycopg.connect(url, autocommit=True, connect_timeout=timeout)
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=DBNAME,
                           autocommit=True, connect_timeout=timeout)


def _sql_path(name):
    from pathlib import Path
    return Path(__file__).resolve().parents[1] / "sql" / name


def apply_sql_file(conn, name):
    """Execute one sql/ file (DDL or views)."""
    conn.execute(_sql_path(name).read_text(encoding="utf-8"))


def load_frame(conn, table, df, columns):
    """TRUNCATE + COPY a text frame into staging (exact column order)."""
    cols = ", ".join(columns)
    conn.execute(f"TRUNCATE {table}")
    text = df[list(columns)].to_csv(index=False, encoding="utf-8",
                                    lineterminator="\n")
    with conn.cursor().copy(
            f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv, HEADER true)") as cp:
        cp.write(text)


def fetch_df(conn, query):
    """Run a query and return a DataFrame (psycopg native types)."""
    with conn.cursor() as cur:
        cur.execute(query)
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
