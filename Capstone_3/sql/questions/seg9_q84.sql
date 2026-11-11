-- Q84: second-highest completed order value per city (no LIMIT OFFSET)
-- DENSE_RANK shares rank 2 across duplicates; ROW_NUMBER would pick one row.

WITH ranked AS (
    SELECT
        city_std,
        line_value,
        DENSE_RANK() OVER (
            PARTITION BY city_std ORDER BY line_value DESC
        ) AS rnk
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
)
SELECT
    city_std,
    ROUND(MAX(line_value), 2) AS second_highest_value,
    COUNT(*) AS orders_at_value
FROM ranked
WHERE rnk = 2
GROUP BY city_std
ORDER BY city_std;
