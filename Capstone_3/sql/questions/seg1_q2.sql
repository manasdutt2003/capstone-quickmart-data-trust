-- Q2: Source column names kept verbatim at load
-- Requires: orders_loaded, customers_loaded, products_clean (staging).
-- The loaded columns at ordinal positions 1..n must equal the expected
-- header spec (src/data_loader.py::EXPECTED_HEADERS, mirrored in
-- data/raw_manifest.json); a rename or reorder shows up as a mismatch.

WITH expected (tbl, ord, name) AS (
    VALUES
        ('customers', 1, 'customer_id'),
        ('customers', 2, 'customer_name'),
        ('customers', 3, 'email'),
        ('customers', 4, 'city'),
        ('customers', 5, 'phone'),
        ('customers', 6, 'signup_date'),
        ('products', 1, 'product_id'),
        ('products', 2, 'product_name'),
        ('products', 3, 'category'),
        ('products', 4, 'unit_price'),
        ('products', 5, 'stock_qty'),
        ('orders', 1, 'order_id'),
        ('orders', 2, 'customer_id'),
        ('orders', 3, 'product_id'),
        ('orders', 4, 'order_date'),
        ('orders', 5, 'quantity'),
        ('orders', 6, 'unit_price_paid'),
        ('orders', 7, 'discount'),
        ('orders', 8, 'payment_mode'),
        ('orders', 9, 'order_status'),
        ('orders', 10, 'delivery_days'),
        ('orders', 11, 'notes')
),

loaded AS (
    SELECT
        CASE table_name
            WHEN 'customers_loaded' THEN 'customers'
            WHEN 'products_clean' THEN 'products'
            WHEN 'orders_loaded' THEN 'orders'
        END AS tbl,
        ordinal_position AS ord,
        column_name AS name
    FROM information_schema.columns
    WHERE table_name IN ('customers_loaded', 'products_clean',
                         'orders_loaded')
)

SELECT
    e.tbl,
    COUNT(*) AS header_columns,
    COUNT(l.name) AS matched,
    COUNT(*) - COUNT(l.name) AS mismatched
FROM expected AS e
LEFT JOIN loaded AS l
    ON l.tbl = e.tbl AND l.ord = e.ord AND l.name = e.name
GROUP BY e.tbl
ORDER BY MIN(CASE e.tbl
                 WHEN 'customers' THEN 1
                 WHEN 'products' THEN 2
                 ELSE 3
             END);
