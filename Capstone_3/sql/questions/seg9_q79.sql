-- Q79: median days between consecutive orders per customer
-- Single-order customers carry NULL (never 0): no gap exists.

WITH ordered_orders AS (
    SELECT
        customer_id,
        order_date::date AS d
    FROM trusted_enriched
    WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
),
gaps AS (
    SELECT
        customer_id,
        (d - LAG(d) OVER (
            PARTITION BY customer_id ORDER BY d, order_id
        )) AS gap_days
    FROM (
        SELECT customer_id, order_date::date AS d, order_id
        FROM trusted_enriched
        WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
    ) dated
),
customer_orders AS (
    SELECT customer_id, COUNT(*) AS n_orders
    FROM ordered_orders
    GROUP BY customer_id
),
medians AS (
    SELECT
        customer_id,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY gap_days) AS median_gap
    FROM gaps
    WHERE gap_days IS NOT NULL
    GROUP BY customer_id
)
SELECT
    c.customer_id,
    c.n_orders,
    ROUND(m.median_gap::numeric, 2) AS median_gap_days
FROM customer_orders AS c
LEFT JOIN medians AS m ON c.customer_id = m.customer_id
ORDER BY c.customer_id;
