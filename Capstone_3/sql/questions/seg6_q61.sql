-- Q61: Customers with orders in at least 2 categories, no order in most recent full month
-- EXISTS vs NOT EXISTS

WITH recent_month AS (
    SELECT MAX(order_month) AS max_month
    FROM trusted_enriched
    WHERE order_month IS NOT NULL
),
multi_category_customers AS (
    SELECT DISTINCT customer_id
    FROM trusted_enriched
    WHERE status_std = 'Delivered'
    GROUP BY customer_id
    HAVING COUNT(DISTINCT category_std) >= 2
),
recent_orders AS (
    SELECT DISTINCT customer_id
    FROM trusted_enriched
    WHERE order_month = (SELECT max_month FROM recent_month)
      AND status_std = 'Delivered'
)
SELECT mcc.customer_id
FROM multi_category_customers mcc
WHERE NOT EXISTS (
    SELECT 1 FROM recent_orders ro WHERE ro.customer_id = mcc.customer_id
)
ORDER BY mcc.customer_id;

-- Why EXISTS safer than IN with nulls:
-- IN returns UNKNOWN (not TRUE) if the subquery returns any NULL
-- This means rows with NULL customer_id in recent_orders would cause
-- the IN check to fail unexpectedly (return no rows or wrong rows).
-- EXISTS only cares whether a row EXISTS, ignores NULLs in the subquery.

-- Case where IN differs:
-- If recent_orders has a row with customer_id = NULL,
-- "customer_id IN (SELECT customer_id FROM recent_orders)" returns UNKNOWN for all customers,
-- returning empty result.
-- EXISTS correctly ignores the NULL row and returns correct results.