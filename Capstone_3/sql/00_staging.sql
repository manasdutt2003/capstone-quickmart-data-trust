-- 00_staging.sql : TEXT-only staging tables for parity runs.
-- Every column is TEXT: no implicit casts at load (COPY ... CSV HEADER).
-- All parsing happens inside rule views through regex-guarded casts.
-- Grain: one row per cleaned extract row, file order preserved by COPY.
CREATE TABLE IF NOT EXISTS orders_clean (
    order_id TEXT,
    customer_id TEXT,
    product_id TEXT,
    order_date TEXT,
    quantity TEXT,
    unit_price_paid TEXT,
    discount TEXT,
    payment_mode TEXT,
    order_status TEXT,
    delivery_days TEXT,
    notes TEXT,
    raw_order_id TEXT,
    raw_customer_id TEXT,
    raw_product_id TEXT,
    raw_order_date TEXT,
    raw_quantity TEXT,
    raw_unit_price_paid TEXT,
    raw_discount TEXT,
    raw_payment_mode TEXT,
    raw_order_status TEXT,
    raw_delivery_days TEXT,
    raw_notes TEXT,
    _source_row TEXT,
    source_file TEXT,
    source_row_number TEXT,
    dedup_rule_applied TEXT,
    rules_passed TEXT,
    rules_failed TEXT
);

CREATE TABLE IF NOT EXISTS customers_master (
    customer_id TEXT,
    customer_name TEXT,
    email TEXT,
    city TEXT,
    phone TEXT,
    signup_date TEXT,
    raw_customer_id TEXT,
    raw_customer_name TEXT,
    raw_email TEXT,
    raw_city TEXT,
    raw_phone TEXT,
    raw_signup_date TEXT,
    _source_row TEXT,
    source_file TEXT,
    source_row_number TEXT,
    dedup_rule_applied TEXT,
    rules_passed TEXT,
    rules_failed TEXT
);

CREATE TABLE IF NOT EXISTS products_clean (
    product_id TEXT,
    product_name TEXT,
    category TEXT,
    unit_price TEXT,
    stock_qty TEXT,
    raw_product_id TEXT,
    raw_product_name TEXT,
    raw_category TEXT,
    raw_unit_price TEXT,
    raw_stock_qty TEXT,
    _source_row TEXT,
    source_file TEXT,
    source_row_number TEXT,
    dedup_rule_applied TEXT,
    rules_passed TEXT,
    rules_failed TEXT
);

CREATE TABLE IF NOT EXISTS rule_failure_log (
    source_row_number TEXT,
    order_id TEXT,
    rule_id TEXT,
    result TEXT,
    failing_detail TEXT
);

-- Load-level text layers for the segment 1-3 question files: every loaded
-- row, before the dedup/merge decisions. orders_loaded <- data/orders_clean.csv
-- (6,103 rows: includes the 103 repeated order ids); customers_loaded <-
-- data/customers_clean.csv (520 rows: before the D03 merges).
CREATE TABLE IF NOT EXISTS orders_loaded (
    order_id TEXT,
    customer_id TEXT,
    product_id TEXT,
    order_date TEXT,
    quantity TEXT,
    unit_price_paid TEXT,
    discount TEXT,
    payment_mode TEXT,
    order_status TEXT,
    delivery_days TEXT,
    notes TEXT,
    raw_order_id TEXT,
    raw_customer_id TEXT,
    raw_product_id TEXT,
    raw_order_date TEXT,
    raw_quantity TEXT,
    raw_unit_price_paid TEXT,
    raw_discount TEXT,
    raw_payment_mode TEXT,
    raw_order_status TEXT,
    raw_delivery_days TEXT,
    raw_notes TEXT,
    _source_row TEXT,
    source_file TEXT,
    source_row_number TEXT,
    dedup_rule_applied TEXT,
    rules_passed TEXT,
    rules_failed TEXT
);

CREATE TABLE IF NOT EXISTS customers_loaded (
    customer_id TEXT,
    customer_name TEXT,
    email TEXT,
    city TEXT,
    phone TEXT,
    signup_date TEXT,
    raw_customer_id TEXT,
    raw_customer_name TEXT,
    raw_email TEXT,
    raw_city TEXT,
    raw_phone TEXT,
    raw_signup_date TEXT,
    _source_row TEXT,
    source_file TEXT,
    source_row_number TEXT,
    dedup_rule_applied TEXT,
    rules_passed TEXT,
    rules_failed TEXT
);

-- Single SQL home of the reference date (mirrors config/settings.json
-- "today" and src/validation_rules.Context.today, same value).
-- Every date-bound view reads v_run_params instead of a literal.
CREATE OR REPLACE VIEW v_run_params AS
SELECT DATE '2026-10-11' AS today;
