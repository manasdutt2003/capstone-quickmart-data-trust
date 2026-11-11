-- Q59: Each customer's share of their city's total completed value
-- Derived table in scalar subquery for city denominator

WITH customer_value AS (
    SELECT
        customer_id,
        city_std,
        SUM(line_value) AS customer_value
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
    GROUP BY customer_id, city_std
),
city_total AS (
    SELECT
        city_std,
        SUM(customer_value) AS city_total_value
    FROM customer_value
    GROUP BY city_std
)
SELECT
    cv.customer_id,
    cv.city_std,
    cv.customer_value,
    ct.city_total_value,
    ROUND(cv.customer_value / ct.city_total_value * 100, 2) AS pct_of_city
FROM customer_value cv
JOIN city_total ct ON cv.city_std = ct.city_std
WHERE cv.customer_value / ct.city_total_value > 0.25
ORDER BY cv.city_std, cv.customer_value DESC;

-- Why city denominator must be computed before grouping:
-- The city total is the sum of ALL customers' values in that city.
-- If we computed it after filtering to >25%, the denominator would be wrong
-- (only summing the large customers, not the full city).