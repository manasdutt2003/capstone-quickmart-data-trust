-- Q80: three most recent orders all non-Delivered (tie: order_id)
-- ROW_NUMBER over (order_date DESC, order_id DESC).

WITH ranked AS (
    SELECT
        customer_id,
        status_std,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY order_date DESC, order_id COLLATE "C" DESC
        ) AS rn
    FROM trusted_enriched
    WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
),
top3 AS (
    SELECT * FROM ranked WHERE rn <= 3
)
SELECT customer_id, 3 AS n_recent
FROM top3
GROUP BY customer_id
HAVING
    COUNT(*) = 3
    AND SUM(CASE WHEN status_std = 'Delivered' THEN 1 ELSE 0 END) = 0
ORDER BY customer_id;
