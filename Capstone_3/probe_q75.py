"""Scratch probe: q75 per-dimension SQL vs Python (deleted after)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))

import pandas as pd
from test_sql_executes import _db, apply_sql_file
from src.pg import fetch_df

conn = _db()
try:
    for name in ("00_staging.sql", "v_line_value.sql", "08_rule_views.sql",
                 "07_trusted_populations.sql"):
        apply_sql_file(conn, name)
    q = """
    SELECT 'cust_comp' AS k,
        (1 - (
            (SELECT COUNT(*) FROM customers WHERE TRIM(customer_id) = '')
            + (SELECT COUNT(*) FROM customers WHERE TRIM(customer_name) = '')
            + (SELECT COUNT(*) FROM customers WHERE TRIM(email) = '')
            + (SELECT COUNT(*) FROM customers WHERE TRIM(city) = '')
            + (SELECT COUNT(*) FROM customers WHERE TRIM(phone) = '')
            + (SELECT COUNT(*) FROM customers WHERE TRIM(signup_date) = '')
        )::numeric / (SELECT COUNT(*) * 6 FROM customers)) * 100 AS v
    UNION ALL SELECT 'cust_uniq',
        (1 - (SELECT COUNT(*) - COUNT(DISTINCT TRIM(customer_id)) FROM customers)::numeric / NULLIF((SELECT COUNT(*) FROM customers), 0)) * 100
    UNION ALL SELECT 'cust_ri',
        (1 - (SELECT COUNT(DISTINCT TRIM(o.customer_id)) FROM orders o LEFT JOIN customers c ON TRIM(o.customer_id) = TRIM(c.customer_id) WHERE c.customer_id IS NULL AND TRIM(o.customer_id) <> '')::numeric / NULLIF((SELECT COUNT(DISTINCT TRIM(customer_id)) FROM orders WHERE TRIM(customer_id) <> ''), 0)) * 100
    UNION ALL SELECT 'cust_conf',
        (1 - (SELECT COUNT(*) FROM customers WHERE TRIM(email) NOT LIKE '%@%.%' OR TRIM(phone) !~ '^\\d{10}$' OR TRIM(signup_date) !~ '^\\d{4}-\\d{2}-\\d{2}$')::numeric / (SELECT COUNT(*) FROM customers)) * 100
    UNION ALL SELECT 'ord_comp',
        (1 - (
            (SELECT COUNT(*) FROM orders WHERE TRIM(order_id) = '')
            + (SELECT COUNT(*) FROM orders WHERE TRIM(customer_id) = '')
            + (SELECT COUNT(*) FROM orders WHERE TRIM(product_id) = '')
            + (SELECT COUNT(*) FROM orders WHERE TRIM(order_date) = '')
            + (SELECT COUNT(*) FROM orders WHERE TRIM(quantity) = '')
            + (SELECT COUNT(*) FROM orders WHERE TRIM(unit_price_paid) = '')
            + (SELECT COUNT(*) FROM orders WHERE TRIM(discount) = '')
            + (SELECT COUNT(*) FROM orders WHERE TRIM(payment_mode) = '')
            + (SELECT COUNT(*) FROM orders WHERE TRIM(order_status) = '')
            + (SELECT COUNT(*) FROM orders WHERE TRIM(delivery_days) = '')
        )::numeric / (SELECT COUNT(*) * 10 FROM orders)) * 100
    UNION ALL SELECT 'ord_conf',
        (1 - (SELECT COUNT(*) FROM orders WHERE TRIM(quantity) !~ '^\\d+$' OR TRIM(unit_price_paid) !~ '^\\d+(\\.\\d+)?$' OR TRIM(discount) !~ '^(\\d+(\\.\\d+)?%?|\\d*\\.\\d+|0)$' OR TRIM(payment_mode) NOT IN ('COD', 'Credit Card', 'Debit Card', 'NetBanking', 'UPI') OR TRIM(order_status) NOT IN ('Delivered', 'Cancelled', 'Returned', 'Pending', 'In Transit') OR (TRIM(delivery_days) <> '' AND TRIM(delivery_days) !~ '^\\d+$'))::numeric / (SELECT COUNT(*) FROM orders)) * 100
    """
    print(fetch_df(conn, q).to_string())
finally:
    conn.close()
