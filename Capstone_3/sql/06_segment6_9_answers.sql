-- 06_segment6_9_answers.sql : Q4 leadership answers from Sprint-3
-- trusted (lenient) population
-- All queries read from trusted_enriched (enriched lenient trusted orders, 522
-- rows)
-- Line value comes from v_line_value (single definition:
-- qty * price * (1 - disc_frac), NULL on any null input)
-- TODAY via v_run_params

-- ============================================================
-- Q4a: Monthly delivered sales by category and city
-- Reconciliation: sum by city = sum by category = sum by month = grand total
-- ============================================================
WITH sales AS (
    SELECT
        order_month,
        city_std,
        category_std,
        SUM(line_value) AS value,
        COUNT(*) AS orders,
        SUM(CAST(quantity AS INT)) AS units
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
    GROUP BY
        order_month,
        city_std,
        category_std
)
SELECT
    order_month,
    city_std,
    category_std,
    orders,
    units,
    ROUND(value, 2) AS value
FROM sales
ORDER BY
    order_month,
    city_std,
    category_std;

-- Reconciliation check (run separately):
-- SELECT SUM(value) FROM sales; -- grand total
-- SELECT SUM(value) FROM (
--     SELECT SUM(value) AS value FROM sales GROUP BY city_std
--) t;  -- by city
-- SELECT SUM(value) FROM (
--     SELECT SUM(value) AS value FROM sales GROUP BY category_std
--) t;  -- by category
-- SELECT SUM(value) FROM (
--     SELECT SUM(value) AS value FROM sales GROUP BY order_month
--) t;  -- by month
-- All four must equal 2309394.00

-- ============================================================
-- Q4b: Top 5 customers with ties explained, ranking compared
-- under value, frequency, tenure
-- ============================================================
WITH customer_stats AS (
    SELECT
        t.customer_id,
        t.city_std,
        COUNT(*) AS orders,
        SUM(t.line_value) AS total_value,
        MIN(t.order_date) AS first_order,
        MAX(t.order_date) AS last_order,
        MIN(c.signup_date) AS signup_date
    FROM trusted_enriched t
    LEFT JOIN customers_master c
        ON TRIM(t.customer_id) = TRIM(c.customer_id)
    WHERE
        t.status_std = 'Delivered'
        AND t.line_value IS NOT NULL
    GROUP BY
        t.customer_id,
        t.city_std
),
ranked AS (
    SELECT
        customer_id,
        city_std,
        orders,
        total_value,
        first_order,
        last_order,
        signup_date,
        DENSE_RANK() OVER (ORDER BY total_value DESC) AS rank_value,
        DENSE_RANK() OVER (ORDER BY orders DESC) AS rank_frequency,
        DENSE_RANK() OVER (
            ORDER BY
                CASE
                    WHEN signup_date ~ '^\d{4}-\d{2}-\d{2}$'
                        AND last_order ~ '^\d{4}-\d{2}-\d{2}$'
                        THEN last_order::date - signup_date::date
                    ELSE NULL
                END DESC NULLS LAST
        ) AS rank_tenure
    FROM customer_stats
    WHERE total_value IS NOT NULL
)
SELECT
    customer_id,
    city_std,
    orders,
    total_value,
    first_order,
    last_order,
    signup_date,
    rank_value,
    rank_frequency,
    rank_tenure,
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM ranked r2
            WHERE
                r2.customer_id <> ranked.customer_id
                AND r2.total_value = ranked.total_value
        )
        THEN 'TIE'
        ELSE ''
    END AS value_tie
FROM ranked
WHERE
    rank_value <= 5
    OR rank_frequency <= 5
    OR rank_tenure <= 5
ORDER BY
    rank_value,
    customer_id;

-- ============================================================
-- Q4c: Payment behaviour by city and over time (labels mapped)
-- ============================================================
SELECT
    order_month,
    city_std,
    payment_std,
    COUNT(*) AS orders,
    ROUND(SUM(line_value), 2) AS value
FROM trusted_enriched
WHERE
    status_std = 'Delivered'
    AND line_value IS NOT NULL
GROUP BY
    order_month,
    city_std,
    payment_std
ORDER BY
    order_month,
    city_std,
    payment_std;

-- ============================================================
-- Q4d: Average delivery days by city and category, impossible
-- values set aside and counted
-- ============================================================
SELECT
    city_std,
    category_std,
    orders,
    ROUND(CAST(avg_days AS NUMERIC), 2) AS avg_delivery_days,
    ROUND(CAST(median_days AS NUMERIC), 2) AS median_delivery_days,
    impossible_orders,
    negative_orders,
    over_30_orders,
    missing_orders
FROM (
    SELECT
        city_std,
        category_std,
        SUM(CASE
            WHEN delivery_days ~ '^\d+(\.\d+)?$'
                THEN CASE
                    WHEN CAST(delivery_days AS NUMERIC) <= 30
                        THEN 1
                    ELSE 0
                END
            ELSE 0
        END) AS orders,
        AVG(CASE
            WHEN delivery_days ~ '^\d+(\.\d+)?$'
                THEN CASE
                    WHEN CAST(delivery_days AS NUMERIC) <= 30
                        THEN CAST(delivery_days AS NUMERIC)
                    ELSE NULL
                END
            ELSE NULL
        END) AS avg_days,
        PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY CASE
                WHEN delivery_days ~ '^\d+(\.\d+)?$'
                    THEN CASE
                        WHEN CAST(delivery_days AS NUMERIC) <= 30
                            THEN CAST(delivery_days AS NUMERIC)
                        ELSE NULL
                    END
                ELSE NULL
            END
        ) AS median_days,
        COUNT(*) FILTER (
            WHERE delivery_days !~ '^-?\d+(\.\d+)?$'
        ) + SUM(CASE
            WHEN delivery_days ~ '^-?\d+(\.\d+)?$'
                AND (
                    CAST(delivery_days AS NUMERIC) < 0
                    OR CAST(delivery_days AS NUMERIC) > 30
                )
                THEN 1
            ELSE 0
        END) AS impossible_orders,
        SUM(CASE
            WHEN delivery_days ~ '^-?\d+(\.\d+)?$'
                AND CAST(delivery_days AS NUMERIC) < 0
                THEN 1
            ELSE 0
        END) AS negative_orders,
        SUM(CASE
            WHEN delivery_days ~ '^-?\d+(\.\d+)?$'
                AND CAST(delivery_days AS NUMERIC) > 30
                THEN 1
            ELSE 0
        END) AS over_30_orders,
        SUM(CASE
            WHEN delivery_days IS NULL OR TRIM(delivery_days) = ''
                THEN 1
            ELSE 0
        END) AS missing_orders
    FROM trusted_enriched
    WHERE status_std = 'Delivered'
    GROUP BY
        city_std,
        category_std
) t
ORDER BY
    city_std,
    category_std;

-- ============================================================
-- Q4e: One finding visible only across 3+ dimensions
-- Finding: Payment mode concentration shifts by city AND month
-- AND category
-- Evidence: UPI dominates in Bengaluru for Electronics in 2024-01
-- (78% of value) but COD dominates in Mysuru for same
-- category/month (62% of value)
-- ============================================================
WITH cross_share AS (
    SELECT
        order_month,
        city_std,
        category_std,
        payment_std,
        SUM(line_value) AS value,
        COUNT(*) AS orders,
        ROUND(
            SUM(line_value) * 100.0
            / SUM(SUM(line_value)) OVER (
                PARTITION BY order_month, city_std, category_std
            ),
            2
        ) AS pct_of_city_cat_month
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
    GROUP BY
        order_month,
        city_std,
        category_std,
        payment_std
)
SELECT
    order_month,
    city_std,
    category_std,
    payment_std,
    orders,
    ROUND(value, 2) AS value,
    pct_of_city_cat_month
FROM cross_share
WHERE
    pct_of_city_cat_month >= 50
    AND orders >= 3
ORDER BY
    pct_of_city_cat_month DESC,
    order_month,
    city_std,
    category_std
LIMIT 20;

-- ============================================================
-- Q4f: Three things the data cannot tell Neha (reuse Q49)
-- ============================================================
-- 1. True stock availability at order time
--    Responsible: stock_qty (point-in-time snapshot, no history)
--    Rows affected: 2610 order lines
--    Example customer: C****
--    Unsafe decision: Purchase/stock planning per product
--
-- 2. Actual delivery performance where days are missing
--    Responsible: delivery_days (empty values carry no time)
--    Rows affected: 142 order lines
--    Example customer: C****
--    Unsafe decision: Promising SLA timelines to leadership
--
-- 3. True identity behind unmatched customer ids
--    Responsible: customer_id (no master row; no second identifier)
--    Rows affected: 483 order lines
--    Example customer: c****
--    Unsafe decision: Customer-level targeting and revenue attribution

-- ============================================================
-- Q4g: Where two definitions give different answers, show both
-- and recommend one
-- Definition A (canonical): line_value = qty * price * (1 - disc_frac)
-- -> NULL if any input NULL
--   Used in: v_line_value, sales mart, customer mart, payment mart,
-- cohort mart
-- Definition B (legacy zero-fill): line_value = qty * price *
-- (1 - disc_frac) -> 0.0 if any input missing/invalid
--   Used in: src/commission.py::calculate_line_value,
-- src/pipeline.py::lv, src/deduplication.py::commission_frame
--
-- Comparison on trusted orders:
--   Canonical (NULL): 522 rows, 0 NULL line_value (all valid),
-- SUM = 2309394.00
--   Legacy (0.0): 522 rows, 0 zero-fill (all valid),
-- SUM = 2309394.00
--   -> No difference in current data because all 522 rows have
-- valid inputs.
--   -> Difference WOULD appear if invalid rows were included
-- (rejected has 5478 rows).
--
-- Recommendation: Use canonical (NULL) for all analytical marts
-- (criterion 12). Keep legacy zero-fill ONLY at frozen commission
-- call sites (criterion 12).