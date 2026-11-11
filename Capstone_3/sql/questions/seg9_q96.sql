-- Q96: orders paid >10% above catalogue via correlated scalar subquery
-- One price per order; a plain join would double-count if products held
-- duplicate product_id rows (none do; guarded by dedup note in docs).

SELECT
    t.order_id,
    t.product_id,
    ROUND(t.unit_price_paid::numeric, 2) AS paid,
    ROUND((
        SELECT p.unit_price::numeric
        FROM products_clean AS p
        WHERE p.product_id = t.product_id
        LIMIT 1
    ), 2) AS catalogue
FROM trusted_enriched AS t
WHERE
    t.status_std = 'Delivered'
    AND t.line_value IS NOT NULL
    AND t.unit_price_paid ~ '^\d+(\.\d+)?$'
    AND EXISTS (
        SELECT 1
        FROM products_clean AS p
        WHERE
            p.product_id = t.product_id
            AND p.unit_price ~ '^\d+(\.\d+)?$'
            AND p.unit_price::numeric > 0
            AND t.unit_price_paid::numeric > p.unit_price::numeric * 1.10
    )
ORDER BY t.order_id;
