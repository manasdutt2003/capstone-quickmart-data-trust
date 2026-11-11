-- Q77: float money sums in ascending vs descending order_id order
-- SUM(float8 ORDER BY ...) forces accumulation order per city; diff at
-- cent level proves order-dependence. Fix: NUMERIC, pre-sort, or fsum.

WITH completed AS (
    SELECT
        city_std,
        line_value::float8 AS v,
        order_id
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
)
SELECT
    city_std,
    ROUND(SUM(v ORDER BY order_id COLLATE "C")::numeric, 2) AS sum_asc,
    ROUND(SUM(v ORDER BY order_id COLLATE "C" DESC)::numeric, 2)
        AS sum_desc,
    ROUND(
        (
            SUM(v ORDER BY order_id COLLATE "C")
            - SUM(v ORDER BY order_id COLLATE "C" DESC)
        )::numeric,
        2
    ) AS diff,
    (
        ABS(
            SUM(v ORDER BY order_id COLLATE "C")
            - SUM(v ORDER BY order_id COLLATE "C" DESC)
        ) >= 0.01
    ) AS differs_at_cent
FROM completed
GROUP BY city_std
ORDER BY city_std;
