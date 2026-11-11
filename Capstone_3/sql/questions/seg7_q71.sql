-- Q71: 95th percentile of completed order value per city/month
-- Exact vs approximate percentile, relative error

-- NOTE: PostgreSQL 16 has no APPROX_PERCENTILE builtin. The honest
-- analogue below computes the "approximate" value as percentile_cont
-- over a deterministic every-10th-row subsample (ORDER BY order_id),
-- labelled as such. Both sides (SQL and Python) use the same subsample.

WITH monthly_city AS (
    SELECT order_month, city_std, line_value, order_id
    FROM trusted_enriched
    WHERE status_std = 'Delivered' AND line_value IS NOT NULL
),
numbered AS (
    SELECT
        order_month,
        city_std,
        line_value,
        ROW_NUMBER() OVER (PARTITION BY order_month, city_std ORDER BY order_id COLLATE "C") AS rn
    FROM monthly_city
),
exact_calc AS (
    SELECT
        order_month,
        city_std,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY line_value) AS p95_exact,
        COUNT(*) AS n
    FROM monthly_city
    GROUP BY order_month, city_std
),
approx_calc AS (
    SELECT
        order_month,
        city_std,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY line_value) AS p95_approx
    FROM numbered
    WHERE (rn % 10) = 1
    GROUP BY order_month, city_std
)
SELECT
    e.order_month,
    e.city_std,
    e.n,
    ROUND(CAST(e.p95_exact AS NUMERIC), 2) AS p95_exact,
    ROUND(CAST(a.p95_approx AS NUMERIC), 2) AS p95_approx,
    ROUND(CAST(ABS(e.p95_exact - a.p95_approx) / NULLIF(e.p95_exact, 0) * 100 AS NUMERIC), 2) AS rel_error_pct
FROM exact_calc e
JOIN approx_calc a ON e.order_month = a.order_month AND e.city_std = a.city_std
ORDER BY rel_error_pct DESC;

-- Approximation acceptability:
-- For board reports (high stakes): rel_error > 5 pct unacceptable, need exact
-- For operational dashboards: rel_error < 10 pct often acceptable
-- For exploratory analysis: rel_error < 20 pct acceptable
-- Threshold depends on decision criticality:
--   - Commission payouts: exact only
--   - Trend monitoring: approx acceptable
--   - Anomaly detection: approx often sufficient