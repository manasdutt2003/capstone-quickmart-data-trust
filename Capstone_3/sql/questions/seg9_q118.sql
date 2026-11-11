-- Q118: orders per city in delivery_days bands + shares
-- NULL, negative and >7 values sit in outside_or_invalid (counted, never
-- averaged away); bands use closed integer intervals.

WITH banded AS (
    SELECT
        city_std,
        CASE
            WHEN delivery_days ~ '^\d+$'
                AND delivery_days::int BETWEEN 0 AND 2 THEN '0_to_2'
            WHEN delivery_days ~ '^\d+$'
                AND delivery_days::int BETWEEN 3 AND 5 THEN '3_to_5'
            WHEN delivery_days ~ '^\d+$'
                AND delivery_days::int BETWEEN 6 AND 7 THEN '6_to_7'
            ELSE 'outside_or_invalid'
        END AS band
    FROM trusted_enriched
)
SELECT
    city_std,
    band,
    COUNT(*) AS n,
    SUM(COUNT(*)) OVER (PARTITION BY city_std) AS city_n,
    ROUND(
        COUNT(*)::numeric
        / SUM(COUNT(*)) OVER (PARTITION BY city_std) * 100,
        2
    ) AS share_pct
FROM banded
GROUP BY city_std, band
ORDER BY city_std, band;
