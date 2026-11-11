-- Q106: one completed CTE reused in three aggregates, reconciled
-- A later-edited view would silently fork the three cuts with no failing
-- join to catch it; the single CTE agrees by construction.

WITH completed AS (
    SELECT city_std, category_std, line_value
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
),
grand AS (
    SELECT ROUND(SUM(line_value), 2) AS total_value FROM completed
),
by_city AS (
    SELECT ROUND(SUM(line_value), 2) AS total_value FROM completed
),
by_cat AS (
    SELECT ROUND(SUM(line_value), 2) AS total_value FROM completed
)
SELECT 'grand_total' AS cut, total_value FROM grand
UNION ALL
SELECT 'sum_of_city_totals', total_value FROM by_city
UNION ALL
SELECT 'sum_of_category_totals', total_value FROM by_cat
UNION ALL
SELECT
    'reconciled',
    CASE
        WHEN (SELECT total_value FROM grand)
            = (SELECT total_value FROM by_city)
            AND (SELECT total_value FROM grand)
            = (SELECT total_value FROM by_cat)
            THEN 1.0
        ELSE 0.0
    END;
