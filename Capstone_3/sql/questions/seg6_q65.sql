-- Q65: Customer-by-month activity grid with CROSS JOIN
-- Longest unbroken run of active months per customer

WITH RECURSIVE min_max AS (
    SELECT
        MIN(order_month) AS min_month,
        MAX(order_month) AS max_month
    FROM trusted_enriched
    WHERE order_month ~ '^\d{4}-\d{2}$'
),
months AS (
    SELECT min_month AS month FROM min_max
    UNION ALL
    SELECT TO_CHAR((month || '-01')::date + INTERVAL '1 month', 'YYYY-MM')
    FROM months, min_max
    WHERE (month || '-01')::date < (max_month || '-01')::date
),
customers AS (
    SELECT DISTINCT customer_id FROM trusted_enriched WHERE customer_id IS NOT NULL
),
activity_grid AS (
    SELECT
        c.customer_id,
        m.month,
        CASE WHEN EXISTS (
            SELECT 1 FROM trusted_enriched t
            WHERE t.customer_id = c.customer_id
              AND t.order_month = m.month
              AND t.status_std = 'Delivered'
        ) THEN 1 ELSE 0 END AS active
    FROM customers c
    CROSS JOIN months m
),
runs AS (
    SELECT
        customer_id,
        month,
        active,
        CASE WHEN active = 1 AND LAG(active, 1, 0) OVER (PARTITION BY customer_id ORDER BY month) = 0
             THEN 1 ELSE 0 END AS run_start,
        CASE WHEN active = 1 AND LEAD(active, 1, 0) OVER (PARTITION BY customer_id ORDER BY month) = 0
             THEN 1 ELSE 0 END AS run_end
    FROM activity_grid
),
run_groups AS (
    SELECT
        customer_id,
        month,
        active,
        SUM(run_start) OVER (PARTITION BY customer_id ORDER BY month ROWS UNBOUNDED PRECEDING) AS run_group
    FROM runs
    WHERE active = 1
),
run_lengths AS (
    SELECT
        customer_id,
        run_group,
        COUNT(*) AS run_length,
        MIN(month) AS start_month,
        MAX(month) AS end_month
    FROM run_groups
    GROUP BY customer_id, run_group
)
SELECT
    customer_id,
    run_length,
    start_month,
    end_month
FROM run_lengths
WHERE run_length = (SELECT MAX(run_length) FROM run_lengths rl WHERE rl.customer_id = run_lengths.customer_id)
  -- Tie rule: longest runs tie often (length 1); earliest start wins.
  AND start_month = (SELECT MIN(start_month) FROM run_lengths rl WHERE rl.customer_id = run_lengths.customer_id AND rl.run_length = run_lengths.run_length)
ORDER BY customer_id, start_month;

-- Active definition: customer has at least one delivered order in the month.
-- First/last months: If customer's first month is active, run starts at data start.
-- If customer's last month is active, run extends to data end (right-censored).