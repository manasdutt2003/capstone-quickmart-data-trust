-- Q104: notes mentioning delivery problems vs late share per city
-- Late = strictly above the city median (the median itself is on-time).

WITH flagged AS (
    SELECT
        city_std,
        CASE
            WHEN notes ~* '(delay|late|damage|broken|wrong|missing|never|not deliver)'
                THEN 1
            ELSE 0
        END AS mentions,
        CASE
            WHEN delivery_days ~ '^\d+(\.\d+)?$'
                THEN delivery_days::numeric
            ELSE NULL
        END AS days
    FROM trusted_enriched
),
medians AS (
    SELECT
        city_std,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY days) AS med_days
    FROM flagged
    WHERE days IS NOT NULL
    GROUP BY city_std
)
SELECT
    f.city_std,
    COUNT(*) AS n,
    ROUND(AVG(f.mentions)::numeric * 100, 2) AS mention_share_pct,
    ROUND(
        AVG(CASE WHEN f.days > m.med_days THEN 1 ELSE 0 END)::numeric
        * 100,
        2
    ) AS late_share_pct,
    ROUND(m.med_days::numeric, 2) AS median_days
FROM flagged AS f
JOIN medians AS m ON f.city_std = m.city_std
GROUP BY f.city_std, m.med_days
ORDER BY f.city_std;
