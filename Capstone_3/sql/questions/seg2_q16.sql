-- Q16: Never-empty columns vs columns above 10% missing
-- Requires: customers_loaded, products_clean, orders_loaded (staging).
-- Per-column missing counts (empty or placeholder, raw extract text) with
-- the missing share per table. Expected reading: identifiers and
-- product_name are never empty; five columns sit above 10% missing
-- (stock_qty 40.00%, notes 37.11%, phone 20.96%, discount 18.47%,
-- order_status 10.31%) and each limits one specific analysis.

WITH tokens (token) AS (
    VALUES ('NA'), ('N/A'), ('na'), ('n/a'), ('-'), ('--'), ('unknown'),
           ('UNKNOWN'), ('Unknown'), ('null'), ('NULL'), ('None'),
           ('none'), ('?'), ('MISSING'), ('missing')
),

cells (tbl_ord, table_name, col_ord, column_name, value) AS (
    SELECT 1, 'customers', 1, 'customer_id', raw_customer_id FROM customers_loaded
    UNION ALL SELECT 1, 'customers', 2, 'customer_name', raw_customer_name FROM customers_loaded
    UNION ALL SELECT 1, 'customers', 3, 'email', raw_email FROM customers_loaded
    UNION ALL SELECT 1, 'customers', 4, 'city', raw_city FROM customers_loaded
    UNION ALL SELECT 1, 'customers', 5, 'phone', raw_phone FROM customers_loaded
    UNION ALL SELECT 1, 'customers', 6, 'signup_date', raw_signup_date FROM customers_loaded
    UNION ALL SELECT 2, 'products', 1, 'product_id', raw_product_id FROM products_clean
    UNION ALL SELECT 2, 'products', 2, 'product_name', raw_product_name FROM products_clean
    UNION ALL SELECT 2, 'products', 3, 'category', raw_category FROM products_clean
    UNION ALL SELECT 2, 'products', 4, 'unit_price', raw_unit_price FROM products_clean
    UNION ALL SELECT 2, 'products', 5, 'stock_qty', raw_stock_qty FROM products_clean
    UNION ALL SELECT 3, 'orders', 1, 'order_id', raw_order_id FROM orders_loaded
    UNION ALL SELECT 3, 'orders', 2, 'customer_id', raw_customer_id FROM orders_loaded
    UNION ALL SELECT 3, 'orders', 3, 'product_id', raw_product_id FROM orders_loaded
    UNION ALL SELECT 3, 'orders', 4, 'order_date', raw_order_date FROM orders_loaded
    UNION ALL SELECT 3, 'orders', 5, 'quantity', raw_quantity FROM orders_loaded
    UNION ALL SELECT 3, 'orders', 6, 'unit_price_paid', raw_unit_price_paid FROM orders_loaded
    UNION ALL SELECT 3, 'orders', 7, 'discount', raw_discount FROM orders_loaded
    UNION ALL SELECT 3, 'orders', 8, 'payment_mode', raw_payment_mode FROM orders_loaded
    UNION ALL SELECT 3, 'orders', 9, 'order_status', raw_order_status FROM orders_loaded
    UNION ALL SELECT 3, 'orders', 10, 'delivery_days', raw_delivery_days FROM orders_loaded
    UNION ALL SELECT 3, 'orders', 11, 'notes', raw_notes FROM orders_loaded
),

totals (tbl_ord, total_rows) AS (
    SELECT 1, COUNT(*) FROM customers_loaded
    UNION ALL SELECT 2, COUNT(*) FROM products_clean
    UNION ALL SELECT 3, COUNT(*) FROM orders_loaded
),

stats AS (
    SELECT
        tbl_ord,
        table_name,
        col_ord,
        column_name,
        COUNT(*) FILTER (
            WHERE COALESCE(TRIM(value), '') = ''
               OR TRIM(value) IN (SELECT token FROM tokens)
        ) AS missing_rows
    FROM cells
    GROUP BY tbl_ord, table_name, col_ord, column_name
)

SELECT
    s.table_name,
    s.column_name,
    t.total_rows,
    s.missing_rows,
    ROUND(100.0 * s.missing_rows / t.total_rows, 2) AS missing_pct,
    CASE
        WHEN s.missing_rows = 0 THEN 'never empty'
        WHEN 100 * s.missing_rows > 10 * t.total_rows THEN 'above 10%'
        ELSE '-'
    END AS note
FROM stats AS s
JOIN totals AS t USING (tbl_ord)
ORDER BY s.tbl_ord, s.col_ord;
