-- Q11: Placeholders in orders, per column, and their clustering in time
-- Requires: orders_loaded (staging).
-- Mirrors src/quality_checks.py placeholders on the raw extract text. For
-- the clustering, missing rows are bucketed by the month of the usable
-- order_date (rows without a usable date fall in a '(no date)' bucket);
-- order_date itself has no usable month when it is the missing column.
-- Expected reading: placeholders exist in only three columns; missingness
-- is spread across the whole timeline, so there is no process-fault window.

WITH tokens (token) AS (
    VALUES ('NA'), ('N/A'), ('na'), ('n/a'), ('-'), ('--'), ('unknown'),
           ('UNKNOWN'), ('Unknown'), ('null'), ('NULL'), ('None'),
           ('none'), ('?'), ('MISSING'), ('missing')
),

cells (col_ord, column_name, value, order_date) AS (
    SELECT 1, 'order_id', raw_order_id, order_date FROM orders_loaded
    UNION ALL SELECT 2, 'customer_id', raw_customer_id, order_date FROM orders_loaded
    UNION ALL SELECT 3, 'product_id', raw_product_id, order_date FROM orders_loaded
    UNION ALL SELECT 4, 'order_date', raw_order_date, order_date FROM orders_loaded
    UNION ALL SELECT 5, 'quantity', raw_quantity, order_date FROM orders_loaded
    UNION ALL SELECT 6, 'unit_price_paid', raw_unit_price_paid, order_date FROM orders_loaded
    UNION ALL SELECT 7, 'discount', raw_discount, order_date FROM orders_loaded
    UNION ALL SELECT 8, 'payment_mode', raw_payment_mode, order_date FROM orders_loaded
    UNION ALL SELECT 9, 'order_status', raw_order_status, order_date FROM orders_loaded
    UNION ALL SELECT 10, 'delivery_days', raw_delivery_days, order_date FROM orders_loaded
    UNION ALL SELECT 11, 'notes', raw_notes, order_date FROM orders_loaded
),

flagged AS (
    SELECT
        col_ord,
        column_name,
        TRIM(value) AS v,
        TRIM(order_date) AS d,
        COALESCE(TRIM(value), '') = ''
            OR TRIM(value) IN (SELECT token FROM tokens) AS is_missing
    FROM cells
),

per_col AS (
    SELECT
        col_ord,
        column_name,
        COUNT(*) FILTER (WHERE COALESCE(v, '') = '') AS empty_rows,
        COUNT(*) FILTER (WHERE v IN (SELECT token FROM tokens))
            AS placeholder_rows,
        COUNT(*) FILTER (WHERE is_missing) AS missing_rows
    FROM flagged
    GROUP BY col_ord, column_name
),

bucketed AS (
    SELECT
        column_name,
        COALESCE(LEFT(d, 7), '(no date)') AS month,
        COALESCE(LEFT(d, 7), '9999-99') AS sort_month,
        COUNT(*) AS n
    FROM flagged
    WHERE is_missing
      AND (d ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' OR column_name <> 'order_date')
    GROUP BY column_name, COALESCE(LEFT(d, 7), '(no date)'),
             COALESCE(LEFT(d, 7), '9999-99')
),

cluster AS (
    SELECT
        column_name,
        COUNT(*) AS months_with_missing,
        MAX(n) AS worst_month_rows,
        (ARRAY_AGG(month ORDER BY n DESC, sort_month))[1] AS worst_month
    FROM bucketed
    GROUP BY column_name
)

SELECT
    p.column_name,
    p.empty_rows,
    p.placeholder_rows,
    p.missing_rows,
    COALESCE(c.months_with_missing, 0) AS months_with_missing,
    c.worst_month,
    COALESCE(c.worst_month_rows, 0) AS worst_month_rows,
    ROUND(100.0 * c.worst_month_rows / NULLIF(p.missing_rows, 0), 1)
        AS worst_share_pct
FROM per_col AS p
LEFT JOIN cluster AS c USING (column_name)
ORDER BY p.col_ord;
