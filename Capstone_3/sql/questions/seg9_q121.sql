-- Q121: city x category combos with no completed orders
-- CROSS JOIN grid left-joined to sales; missing cells are zero, not absent.
-- Structural vs data gap: a combo present in all-status orders but absent
-- in completed is a fulfilment gap; absent everywhere is structural.

WITH completed AS (
    SELECT city_std, category_std, line_value
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
),
cities AS (
    SELECT DISTINCT city_std FROM completed
),
cats AS (
    SELECT DISTINCT category_std FROM completed
),
grid AS (
    SELECT city_std, category_std FROM cities CROSS JOIN cats
),
sales AS (
    SELECT city_std, category_std, SUM(line_value) AS value
    FROM completed
    GROUP BY city_std, category_std
)
SELECT g.city_std, g.category_std
FROM grid AS g
LEFT JOIN sales AS s
    ON g.city_std = s.city_std AND g.category_std = s.category_std
WHERE s.value IS NULL
ORDER BY g.city_std, g.category_std;
