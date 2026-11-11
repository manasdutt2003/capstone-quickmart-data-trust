-- Q98: latest order of a product used a new payment_mode (tie: date)
-- Latest row per pair via ROW_NUMBER, anti-join any earlier row with the
-- same payment. Ties break by (order_date, order_id).

WITH ranked AS (
    SELECT
        customer_id,
        product_id,
        payment_std,
        order_date,
        order_id,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id, product_id
            ORDER BY order_date DESC, order_id COLLATE "C" DESC
        ) AS rn
    FROM trusted_enriched
    WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
),
latest AS (
    SELECT * FROM ranked WHERE rn = 1
)
SELECT l.customer_id, l.product_id
FROM latest AS l
WHERE NOT EXISTS (
    SELECT 1
    FROM ranked AS e
    WHERE
        e.customer_id = l.customer_id
        AND e.product_id = l.product_id
        AND e.rn > 1
        AND e.payment_std = l.payment_std
)
ORDER BY l.customer_id, l.product_id;
