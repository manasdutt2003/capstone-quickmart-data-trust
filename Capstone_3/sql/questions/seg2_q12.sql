-- Q12: Most-empty orders column and whether notes-emptiness is status-driven
-- Requires: orders_loaded (staging).
-- Two views in one table: missing share per orders column (scope 'column',
-- shares to 2dp of all 6,103 rows) and empty notes within each cleaned
-- order_status (scope 'status', shares to 1dp within the status; the
-- cleaned 'MISSING' token stands for a blank status). Expected reading:
-- notes is the most-empty column but its emptiness is uniform across
-- statuses, so KPI scope excludes missing cells and reports coverage.

WITH tokens (token) AS (
    VALUES ('NA'), ('N/A'), ('na'), ('n/a'), ('-'), ('--'), ('unknown'),
           ('UNKNOWN'), ('Unknown'), ('null'), ('NULL'), ('None'),
           ('none'), ('?'), ('MISSING'), ('missing')
),

cells (col_ord, column_name, value) AS (
    SELECT 1, 'order_id', raw_order_id FROM orders_loaded
    UNION ALL SELECT 2, 'customer_id', raw_customer_id FROM orders_loaded
    UNION ALL SELECT 3, 'product_id', raw_product_id FROM orders_loaded
    UNION ALL SELECT 4, 'order_date', raw_order_date FROM orders_loaded
    UNION ALL SELECT 5, 'quantity', raw_quantity FROM orders_loaded
    UNION ALL SELECT 6, 'unit_price_paid', raw_unit_price_paid FROM orders_loaded
    UNION ALL SELECT 7, 'discount', raw_discount FROM orders_loaded
    UNION ALL SELECT 8, 'payment_mode', raw_payment_mode FROM orders_loaded
    UNION ALL SELECT 9, 'order_status', raw_order_status FROM orders_loaded
    UNION ALL SELECT 10, 'delivery_days', raw_delivery_days FROM orders_loaded
    UNION ALL SELECT 11, 'notes', raw_notes FROM orders_loaded
),

per_col AS (
    SELECT
        col_ord,
        column_name,
        COUNT(*) FILTER (
            WHERE COALESCE(TRIM(value), '') = ''
               OR TRIM(value) IN (SELECT token FROM tokens)
        ) AS missing_rows
    FROM cells
    GROUP BY col_ord, column_name
),

total AS (SELECT COUNT(*) AS n FROM orders_loaded),

by_status AS (
    SELECT
        CASE WHEN TRIM(order_status) IN ('', 'MISSING') THEN '(blank)'
             ELSE TRIM(order_status) END AS status,
        COUNT(*) AS total_rows,
        COUNT(*) FILTER (
            WHERE COALESCE(TRIM(raw_notes), '') = ''
               OR TRIM(raw_notes) IN (SELECT token FROM tokens)
        ) AS missing_notes
    FROM orders_loaded
    GROUP BY 1
)

SELECT scope, name, missing_rows, total_rows, share_pct
FROM (
    SELECT
        'column' AS scope,
        column_name AS name,
        missing_rows,
        (SELECT n FROM total) AS total_rows,
        ROUND(100.0 * missing_rows / (SELECT n FROM total), 2) AS share_pct,
        -missing_rows AS sort_key
    FROM per_col
    UNION ALL
    SELECT
        'status',
        status,
        missing_notes,
        total_rows,
        ROUND(100.0 * missing_notes / total_rows, 1),
        CASE status
            WHEN 'Delivered' THEN 1
            WHEN 'Cancelled' THEN 2
            WHEN 'In Transit' THEN 3
            WHEN 'Pending' THEN 4
            WHEN 'Returned' THEN 5
            ELSE 6
        END
    FROM by_status
) AS t
ORDER BY CASE scope WHEN 'column' THEN 1 ELSE 2 END, sort_key;
