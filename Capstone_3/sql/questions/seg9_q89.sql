-- Q89: rolling 90-day distinct customers per city (RANGE + exact)
-- RANGE frames the day span but COUNT(*) counts rows; DISTINCT is exact
-- via the deduped set. ROWS would count fixed row offsets on sparse dates.

WITH cust_days AS (
    SELECT DISTINCT
        city_std,
        customer_id,
        order_date::date AS d
    FROM trusted_enriched
    WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
),
days AS (
    SELECT DISTINCT city_std, d FROM cust_days
),
exact_counts AS (
    SELECT
        cd.city_std,
        cd.d,
        (
            SELECT COUNT(DISTINCT c2.customer_id)
            FROM cust_days AS c2
            WHERE
                c2.city_std = cd.city_std
                AND c2.d BETWEEN cd.d - 89 AND cd.d
        ) AS distinct_customers
    FROM days AS cd
),
range_counts AS (
    SELECT
        city_std,
        d,
        COUNT(*) OVER (
            PARTITION BY city_std
            ORDER BY d
            RANGE BETWEEN INTERVAL '89 days' PRECEDING AND CURRENT ROW
        ) AS range_row_count
    FROM cust_days
)
SELECT
    e.city_std,
    e.d AS date,
    e.distinct_customers,
    MAX(r.range_row_count) AS range_row_count
FROM exact_counts AS e
JOIN range_counts AS r
    ON r.city_std = e.city_std AND r.d = e.d
GROUP BY e.city_std, e.d, e.distinct_customers
ORDER BY e.city_std, e.d;
