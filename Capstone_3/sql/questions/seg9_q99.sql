-- Q99: top two DENSE_RANKs per city, ties included
-- Tied ranks return more than two customers per city.

WITH cust_v AS (
    SELECT city_std, customer_id, SUM(line_value) AS total_value
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
    GROUP BY city_std, customer_id
),
ranked AS (
    SELECT
        city_std,
        customer_id,
        total_value,
        DENSE_RANK() OVER (
            PARTITION BY city_std ORDER BY total_value DESC
        ) AS rnk
    FROM cust_v
)
SELECT city_std, customer_id, ROUND(total_value, 2) AS total_value, rnk
FROM ranked
WHERE rnk <= 2
ORDER BY city_std, rnk, customer_id;
