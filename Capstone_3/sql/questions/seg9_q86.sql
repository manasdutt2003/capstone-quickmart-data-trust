-- Q86: each customer's 3 most recent completed orders as one array
-- LATERAL ... ORDER BY order_date DESC, order_id DESC LIMIT 3.
-- Same-date ties resolve by order_id; without it the third slot varies.

SELECT
    c.customer_id,
    CARDINALITY(arr.latest_three) AS n,
    '{' || array_to_string(arr.latest_three, ',') || '}' AS latest_three
FROM (
    SELECT DISTINCT customer_id FROM trusted_enriched
) AS c
CROSS JOIN LATERAL (
    SELECT array_agg(t.order_id) AS latest_three
    FROM (
        SELECT order_id
        FROM trusted_enriched
        WHERE
            customer_id = c.customer_id
            AND status_std = 'Delivered'
            AND line_value IS NOT NULL
        ORDER BY order_date DESC, order_id COLLATE "C" DESC
        LIMIT 3
    ) AS t
) AS arr
WHERE arr.latest_three IS NOT NULL
ORDER BY c.customer_id;
