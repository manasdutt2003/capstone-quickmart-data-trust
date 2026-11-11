-- Q78: monthly completed value per city + month-over-month change
-- NULL (not 0) where the prior month has no row; first month is NULL.

WITH monthly AS (
    SELECT
        city_std,
        order_month,
        SUM(line_value) AS value
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
    GROUP BY city_std, order_month
)
SELECT
    city_std,
    order_month,
    ROUND(value, 2) AS value,
    ROUND(
        LAG(value) OVER (
            PARTITION BY city_std ORDER BY order_month
        ),
        2
    ) AS prev_value,
    ROUND(
        value - LAG(value) OVER (
            PARTITION BY city_std ORDER BY order_month
        ),
        2
    ) AS mom_change
FROM monthly
ORDER BY city_std, order_month;
