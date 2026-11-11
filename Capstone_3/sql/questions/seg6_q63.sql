-- Q63: Spike detection - customer order count exceeds 3x trailing average
-- Window frame: ROWS BETWEEN 6 PRECEDING AND CURRENT ROW

WITH customer_daily AS (
    SELECT
        customer_id,
        order_date,
        COUNT(*) AS daily_orders
    FROM trusted_enriched
    WHERE status_std = 'Delivered'
    GROUP BY customer_id, order_date
),
trailing_avg AS (
    SELECT
        customer_id,
        order_date,
        daily_orders,
        AVG(daily_orders) OVER (
            PARTITION BY customer_id
            ORDER BY order_date
            ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
        ) AS trailing_avg_7d
    FROM customer_daily
),
spikes AS (
    SELECT
        customer_id,
        order_date,
        daily_orders,
        ROUND(trailing_avg_7d, 2) AS trailing_avg_7d,
        CASE
            WHEN trailing_avg_7d IS NOT NULL
                 AND daily_orders > 3 * trailing_avg_7d
            THEN 'SPIKE'
            ELSE 'NORMAL'
        END AS spike_flag
    FROM trailing_avg
)
SELECT
    customer_id,
    COUNT(*) FILTER (WHERE spike_flag = 'SPIKE') AS spike_days,
    MAX(daily_orders) AS max_daily_orders,
    ROUND(MAX(trailing_avg_7d), 2) AS max_trailing_avg
FROM spikes
WHERE spike_flag = 'SPIKE'
GROUP BY customer_id
ORDER BY spike_days DESC, customer_id;

-- Customers with at least one spike:
-- SELECT COUNT(DISTINCT customer_id) FROM spikes WHERE spike_flag = 'SPIKE';

-- Separating genuine surge from duplicate burst:
-- 1. Check if spike orders have identical order_id (exact duplicates) -> D01
-- 2. Check if spike orders share same customer_id, product_id, order_date -> D02
-- 3. Check if spike orders have identical notes -> likely duplicate entry
-- 4. Genuine surge: diverse products, different times, varied quantities
-- 5. Duplicate burst: identical or near-identical rows