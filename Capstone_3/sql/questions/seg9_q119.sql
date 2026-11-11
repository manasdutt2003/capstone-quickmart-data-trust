-- Q119: signup-month cohort with shortest median signup->first-order lag
-- Negative lags (first order before signup) excluded from medians, counted.

WITH first_orders AS (
    SELECT customer_id, MIN(order_date) AS first_order
    FROM orders_clean
    WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
    GROUP BY customer_id
),
lags AS (
    SELECT
        SUBSTRING(c.signup_date, 1, 7) AS signup_month,
        (f.first_order::date - c.signup_date::date) AS lag_days
    FROM customers_master AS c
    JOIN first_orders AS f ON c.customer_id = f.customer_id
    WHERE
        c.signup_date ~ '^\d{4}-\d{2}-\d{2}$'
        AND f.first_order ~ '^\d{4}-\d{2}-\d{2}$'
)
SELECT
    signup_month,
    ROUND(
        percentile_cont(0.5) WITHIN GROUP (ORDER BY lag_days)::numeric, 2
    ) AS median_lag_days,
    COUNT(*) AS n_customers
FROM lags
WHERE lag_days >= 0
GROUP BY signup_month
ORDER BY median_lag_days, signup_month;
