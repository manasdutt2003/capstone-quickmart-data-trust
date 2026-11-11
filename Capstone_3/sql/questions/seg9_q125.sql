-- Q125: top-3 cities + top category + share (4 CTEs, window, LATERAL,
-- GROUPING SETS, anti-join). At 10x rows the per-city sort spills first.

WITH rejected_ids AS (
    SELECT DISTINCT order_id
    FROM rule_failure_log
    WHERE result = 'FAIL'
),
completed AS (
    SELECT city_std, category_std, line_value
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
        AND NOT EXISTS (
            SELECT 1
            FROM rejected_ids AS r
            WHERE r.order_id = trusted_enriched.order_id
        )
),
city_cat AS (
    SELECT city_std, category_std, SUM(line_value) AS value
    FROM completed
    GROUP BY GROUPING SETS ((city_std, category_std), (city_std))
),
ranked_cities AS (
    SELECT
        city_std,
        SUM(value) AS city_value,
        DENSE_RANK() OVER (ORDER BY SUM(value) DESC) AS rnk
    FROM city_cat
    WHERE category_std IS NOT NULL
    GROUP BY city_std
),
top3 AS (
    SELECT city_std, city_value
    FROM ranked_cities
    WHERE rnk <= 3
),
grand AS (
    SELECT SUM(line_value) AS g FROM completed
)
SELECT
    t.city_std,
    ROUND(t.city_value, 2) AS city_value,
    top.top_category,
    ROUND(top.cat_value / t.city_value * 100, 2) AS cat_share_pct,
    ROUND(
        t.city_value / (SELECT g FROM grand) * 100,
        2
    ) AS city_share_of_grand_pct
FROM top3 AS t
CROSS JOIN LATERAL (
    SELECT category_std AS top_category, value AS cat_value
    FROM city_cat
    WHERE
        city_cat.city_std = t.city_std
        AND city_cat.category_std IS NOT NULL
    ORDER BY value DESC, category_std COLLATE "C"
    LIMIT 1
) AS top
ORDER BY t.city_value DESC;
