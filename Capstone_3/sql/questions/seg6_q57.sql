-- Q57: Recursive CTE for month-by-category calendar
-- Left-join completed sales, report zero-filled cells

WITH RECURSIVE min_max AS (
    SELECT
        MIN(order_month) AS min_month,
        MAX(order_month) AS max_month
    FROM trusted_enriched
    WHERE order_month ~ '^\d{4}-\d{2}$'
),
categories AS (
    SELECT DISTINCT category_std
    FROM trusted_enriched
    WHERE category_std IS NOT NULL
),
months AS (
    SELECT min_month AS month FROM min_max
    UNION ALL
    SELECT TO_CHAR((month || '-01')::date + INTERVAL '1 month', 'YYYY-MM')
    FROM months, min_max
    WHERE (month || '-01')::date < (max_month || '-01')::date
),
calendar AS (
    SELECT m.month, c.category_std
    FROM months m
    CROSS JOIN categories c
),
sales AS (
    SELECT
        order_month,
        category_std,
        SUM(line_value) AS value,
        COUNT(*) AS orders
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
    GROUP BY order_month, category_std
)
SELECT
    cal.month,
    cal.category_std,
    COALESCE(s.value, 0) AS value,
    COALESCE(s.orders, 0) AS orders,
    CASE WHEN s.value IS NULL THEN 'ZERO_FILLED' ELSE 'HAS_DATA' END AS cell_type
FROM calendar cal
LEFT JOIN sales s
    ON cal.month = s.order_month
    AND cal.category_std = s.category_std
ORDER BY cal.month, cal.category_std;

-- Zero-filled cells count:
-- SELECT COUNT(*) FROM calendar cal LEFT JOIN sales s ... WHERE s.value IS NULL;
-- Leaving them out would mislead because:
-- 1. Gaps would look like "no data" rather than "zero sales"
-- 2. Moving averages and trends would skip months incorrectly
-- 3. Category comparisons would have different time bases