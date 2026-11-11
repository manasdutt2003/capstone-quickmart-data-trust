-- Q115: months with fewer distinct completed cities than the prior month
-- COUNT(DISTINCT) cannot sit in a window frame portably: distinct count is
-- a subquery, LAG runs over its months.

WITH per_month AS (
    SELECT order_month, COUNT(DISTINCT city_std) AS n_cities
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
    GROUP BY order_month
),
lagged AS (
    SELECT
        order_month,
        n_cities,
        LAG(n_cities) OVER (ORDER BY order_month) AS prev_n
    FROM per_month
)
SELECT order_month, n_cities, prev_n
FROM lagged
WHERE n_cities < prev_n
ORDER BY order_month;
