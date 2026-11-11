-- Q49: Three things the data cannot tell Neha
-- These are documented findings, not computed queries

-- 1. True stock availability at order time
-- Responsible: stock_qty (point-in-time snapshot, no history)
SELECT
    (
        SELECT COUNT(*)
        FROM products AS p
        WHERE
            TRIM(p.stock_qty) = ''
            OR TRIM(p.stock_qty) !~ '^\d+(\.\d+)?$'
    ) AS bad_stock_products,
    COUNT(*) FILTER (
        WHERE TRIM(o.product_id) IN (
            SELECT TRIM(p.product_id)
            FROM products AS p
            WHERE
                TRIM(p.stock_qty) = ''
                OR TRIM(p.stock_qty) !~ '^\d+(\.\d+)?$'
        )
    ) AS affected_order_rows
FROM orders AS o;

-- 2. Actual delivery performance where days are missing
SELECT COUNT(*) AS missing_delivery_days
FROM orders AS o
WHERE TRIM(o.delivery_days) = '';

-- 3. True identity behind unmatched customer ids
WITH norm_cust AS (
    SELECT
        UPPER(
            REPLACE(REPLACE(TRIM(customer_id), ' ', ''), '-', '')
        ) AS norm_id
    FROM customers
    WHERE TRIM(customer_id) <> ''
)

SELECT COUNT(*) AS unmatched_order_rows
FROM orders AS o
WHERE
    UPPER(REPLACE(REPLACE(TRIM(o.customer_id), ' ', ''), '-', '')) NOT IN (
        SELECT norm_cust.norm_id FROM norm_cust
    )
    AND TRIM(o.customer_id) <> '';
