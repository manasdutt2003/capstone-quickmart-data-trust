-- Q116: Gini of completed value across customers per city (windowed)
-- G = 2*sum(i*x)/(n*sum) - (n+1)/n on ascending values; assumes
-- non-negative values, one row per customer. Near 1 = total concentration.

WITH cust_v AS (
    SELECT city_std, customer_id, SUM(line_value) AS v
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
    GROUP BY city_std, customer_id
),
ordered AS (
    SELECT
        city_std,
        v,
        customer_id,
        ROW_NUMBER() OVER (
            PARTITION BY city_std ORDER BY v, customer_id COLLATE "C"
        ) AS rn,
        COUNT(*) OVER (PARTITION BY city_std) AS n,
        SUM(v) OVER (PARTITION BY city_std) AS tot
    FROM cust_v
)
SELECT
    city_std,
    COUNT(*) AS n_customers,
    ROUND(
        (
            2 * SUM(rn * v) - (MAX(n) + 1) * SUM(v)
        ) / (MAX(n) * SUM(v)),
        4
    ) AS gini
FROM ordered
GROUP BY city_std
ORDER BY city_std;
