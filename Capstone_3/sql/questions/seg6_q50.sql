-- Q50: Running total crossing 10,000 per customer
-- Window function: running total of completed-order value by order date
-- First date where running total crosses 10,000
-- Ties on same date: ordered by order_id to ensure determinism

WITH completed_orders AS (
    SELECT
        customer_id,
        order_id,
        order_date,
        line_value
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
),
running_totals AS (
    SELECT
        customer_id,
        order_date,
        order_id,
        SUM(line_value) OVER (
            PARTITION BY customer_id
            ORDER BY order_date, order_id COLLATE "C"
            ROWS UNBOUNDED PRECEDING
        ) AS running_total
    FROM completed_orders
),
first_cross AS (
    SELECT
        customer_id,
        MIN(order_date) AS cross_date
    FROM running_totals
    WHERE running_total >= 10000
    GROUP BY customer_id
)
SELECT
    customer_id,
    cross_date
FROM first_cross
ORDER BY customer_id;

-- Customers who never cross 10,000:
-- SELECT COUNT(*) FROM (
--     SELECT customer_id, MAX(running_total) AS max_total
--     FROM running_totals
--     GROUP BY customer_id
-- ) t WHERE max_total < 10000;