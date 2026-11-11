-- Q114: units per product per month via SUM(quantity), no expansion
-- Recursive unit-row expansion is O(units) memory for an identical total.

SELECT
    product_id,
    SUBSTRING(order_date, 1, 7) AS order_month,
    SUM(
        CASE
            WHEN quantity ~ '^\d+$' THEN quantity::int
            ELSE 0
        END
    ) AS units
FROM trusted_enriched
WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
GROUP BY product_id, SUBSTRING(order_date, 1, 7)
ORDER BY product_id, order_month;
