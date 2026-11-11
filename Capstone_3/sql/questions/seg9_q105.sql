-- Q105: most expensive product per customer (LATERAL vs FIRST_VALUE)
-- Agree iff price ties break identically (product_id ASC here).

WITH lateral_pick AS (
    SELECT c.customer_id, t.product_id, t.unit_price_paid::numeric AS price
    FROM (SELECT DISTINCT customer_id FROM trusted_enriched) AS c
    CROSS JOIN LATERAL (
        SELECT product_id, unit_price_paid
        FROM trusted_enriched
        WHERE
            customer_id = c.customer_id
            AND status_std = 'Delivered'
            AND line_value IS NOT NULL
            AND unit_price_paid ~ '^\d+(\.\d+)?$'
        ORDER BY unit_price_paid::numeric DESC, product_id COLLATE "C"
        LIMIT 1
    ) AS t
),
window_pick AS (
    SELECT DISTINCT
        customer_id,
        FIRST_VALUE(product_id) OVER (
            PARTITION BY customer_id
            ORDER BY unit_price_paid::numeric DESC,
                product_id COLLATE "C"
        ) AS fw_product,
        FIRST_VALUE(unit_price_paid::numeric) OVER (
            PARTITION BY customer_id
            ORDER BY unit_price_paid::numeric DESC,
                product_id COLLATE "C"
        ) AS fw_price
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
        AND unit_price_paid ~ '^\d+(\.\d+)?$'
)
SELECT
    l.customer_id,
    l.product_id,
    ROUND(l.price, 2) AS price,
    (l.product_id = w.fw_product) AS agrees_with_first_value
FROM lateral_pick AS l
JOIN window_pick AS w ON l.customer_id = w.customer_id
WHERE l.product_id IS NOT NULL
ORDER BY l.customer_id;
