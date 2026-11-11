-- Q94: Herfindahl index of category shares per city (two-level agg)
-- Per-city HHI is independent of other cities: dropping the smallest city
-- changes no other city's index (only removes its row).

WITH cat_v AS (
    SELECT city_std, category_std, SUM(line_value) AS v
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
    GROUP BY city_std, category_std
),
shares AS (
    SELECT
        city_std,
        v / SUM(v) OVER (PARTITION BY city_std) AS share
    FROM cat_v
)
SELECT
    city_std,
    ROUND(SUM(share * share)::numeric, 4) AS hhi,
    CASE
        WHEN city_std = (
            SELECT city_std
            FROM cat_v
            GROUP BY city_std
            ORDER BY SUM(v)
            LIMIT 1
        ) THEN 'smallest_city'
        ELSE ''
    END AS note
FROM shares
GROUP BY city_std
ORDER BY city_std;
