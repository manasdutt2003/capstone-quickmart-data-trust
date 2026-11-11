-- Q91: orders above city p95 delivery_days; city vs global flags
-- Delivery managers use the city bar (local reality), not the global one.

WITH dated AS (
    SELECT
        order_id,
        city_std,
        delivery_days::numeric AS days
    FROM trusted_enriched
    WHERE delivery_days ~ '^\d+(\.\d+)?$'
),
thresholds AS (
    SELECT
        d.order_id,
        d.city_std,
        d.days,
        c.city_p95,
        g.global_p95
    FROM dated AS d
    JOIN (
        SELECT
            city_std,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY days)
                AS city_p95
        FROM dated
        GROUP BY city_std
    ) AS c ON d.city_std = c.city_std
    CROSS JOIN (
        SELECT
            percentile_cont(0.95) WITHIN GROUP (ORDER BY days)
                AS global_p95
        FROM dated
    ) AS g
)
SELECT
    order_id,
    city_std,
    days,
    ROUND(city_p95::numeric, 2) AS city_p95,
    ROUND(global_p95::numeric, 2) AS global_p95,
    (days > city_p95) AS flag_city,
    (days > global_p95) AS flag_global
FROM thresholds
WHERE days > city_p95
ORDER BY order_id;
