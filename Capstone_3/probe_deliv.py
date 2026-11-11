"""Scratch probe: compare SQL vs Python delivered sets (deleted after)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))

import pandas as pd
from test_sql_executes import _db, _read_text_csv, ROOT, MAP_FILES, _mapping_pairs
from src.pg import (
    CUSTOMERS_COLUMNS,
    ORDERS_COLUMNS,
    PRODUCTS_COLUMNS,
    apply_sql_file,
    fetch_df,
    load_frame,
)

conn = _db()
conn.execute("DROP VIEW IF EXISTS trusted_enriched CASCADE")
for view in ("v_trusted_lenient", "v_trusted_strict", "v_rejected_orders",
             "v_line_value", "v_r01_customer_exists",
             "v_r03_signup_before_order", "v_r06_valid_price",
             "v_r06_valid_price_tol05", "v_run_params",
             "orders", "customers", "products"):
    conn.execute(f"DROP VIEW IF EXISTS {view} CASCADE")
for table in ("orders_clean", "customers_master", "products_clean",
              "rule_failure_log"):
    conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
for table in ("city_map", "category_map", "status_map", "pay_map",
              "payment_mapping"):
    conn.execute(f"DROP TABLE IF EXISTS {table}")
apply_sql_file(conn, "00_staging.sql")
orders = _read_text_csv(ROOT / "data" / "clean_orders.csv")
customers = _read_text_csv(ROOT / "data" / "customer_master.csv")
products = _read_text_csv(ROOT / "data" / "products_clean.csv")
failures = _read_text_csv(ROOT / "outputs" / "rule_failure_log.csv")
load_frame(conn, "orders_clean", orders, ORDERS_COLUMNS)
load_frame(conn, "customers_master", customers, CUSTOMERS_COLUMNS)
load_frame(conn, "products_clean", products, PRODUCTS_COLUMNS)
conn.execute("TRUNCATE rule_failure_log")
text = failures[["source_row_number", "order_id", "rule_id",
                 "result", "failing_detail"]].to_csv(
    index=False, encoding="utf-8", lineterminator="\n")
with conn.cursor().copy(
        "COPY rule_failure_log (source_row_number, order_id, "
        "rule_id, result, failing_detail) "
        "FROM STDIN WITH (FORMAT csv, HEADER true)") as cp:
    cp.write(text)
for table, filename in MAP_FILES.items():
    pairs = _mapping_pairs(filename)
    conn.execute(f"CREATE TABLE {table} "
                 f"(raw_value TEXT, standard_value TEXT)")
    text = pd.DataFrame(
        pairs, columns=["raw_value", "standard_value"]).to_csv(
        index=False, encoding="utf-8", lineterminator="\n")
    with conn.cursor().copy(
            f"COPY {table} (raw_value, standard_value) "
            f"FROM STDIN WITH (FORMAT csv, HEADER true)") as cp:
        cp.write(text)
conn.execute("CREATE OR REPLACE VIEW orders AS SELECT * FROM orders_clean")
conn.execute("CREATE OR REPLACE VIEW customers AS SELECT * FROM customers_master")
conn.execute("CREATE OR REPLACE VIEW products AS SELECT * FROM products_clean")
apply_sql_file(conn, "v_line_value.sql")
apply_sql_file(conn, "08_rule_views.sql")
apply_sql_file(conn, "07_trusted_populations.sql")

print("lenient rows:", len(fetch_df(conn, "SELECT * FROM v_trusted_lenient")))
print("enriched rows:", len(fetch_df(conn, "SELECT * FROM trusted_enriched")))
d = fetch_df(conn, "SELECT customer_id, status_std, order_month, line_value FROM trusted_enriched WHERE status_std='Delivered'")
print("sql delivered rows:", len(d), "customers:", d["customer_id"].nunique())
print("sql status:", fetch_df(conn, "SELECT status_std, COUNT(*) FROM trusted_enriched GROUP BY 1 ORDER BY 1").to_string())
print("sql months sample:", sorted(d["order_month"].unique())[:5])
print("sql null line:", int(d["line_value"].isna().sum()))
conn.close()
