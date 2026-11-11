-- Q51: Products with average unit_price_paid > 20% above catalogue price
-- Two versions: correlated subquery and join-based

-- Version 1: Correlated subquery
SELECT
    p.product_id,
    p.category,
    ROUND(AVG(o.unit_price_paid::numeric), 2) AS avg_paid,
    p.unit_price::numeric AS catalogue_price,
    ROUND((AVG(o.unit_price_paid::numeric) - p.unit_price::numeric) / p.unit_price::numeric * 100, 2) AS pct_above
FROM orders o
JOIN products p ON TRIM(o.product_id) = TRIM(p.product_id)
WHERE
    TRIM(o.product_id) <> ''
    AND TRIM(p.product_id) <> ''
    AND o.unit_price_paid ~ '^\d+(\.\d+)?$'
    AND p.unit_price ~ '^\d+(\.\d+)?$'
    AND p.unit_price::numeric > 0
GROUP BY p.product_id, p.category, p.unit_price
HAVING AVG(o.unit_price_paid::numeric) > p.unit_price::numeric * 1.20
ORDER BY pct_above DESC;

-- Version 2: Join-based (equivalent logic)
WITH avg_paid AS (
    SELECT
        TRIM(product_id) AS product_id,
        AVG(unit_price_paid::numeric) AS avg_paid
    FROM orders
    WHERE
        TRIM(product_id) <> ''
        AND unit_price_paid ~ '^\d+(\.\d+)?$'
    GROUP BY TRIM(product_id)
),
valid_products AS (
    SELECT
        TRIM(product_id) AS product_id,
        category,
        unit_price::numeric AS catalogue_price
    FROM products
    WHERE
        TRIM(product_id) <> ''
        AND unit_price ~ '^\d+(\.\d+)?$'
        AND unit_price::numeric > 0
)
SELECT
    p.product_id,
    p.category,
    ROUND(a.avg_paid, 2) AS avg_paid,
    p.catalogue_price,
    ROUND((a.avg_paid - p.catalogue_price) / p.catalogue_price * 100, 2) AS pct_above
FROM avg_paid a
JOIN valid_products p ON a.product_id = p.product_id
WHERE a.avg_paid > p.catalogue_price * 1.20
ORDER BY pct_above DESC;

-- The two versions agree because:
-- 1. Both filter on valid numeric prices
-- 2. Both group by product_id after TRIM
-- 3. Both apply the same 20% threshold
-- 4. Join-based is more efficient (single scan of orders vs correlated subquery per product)