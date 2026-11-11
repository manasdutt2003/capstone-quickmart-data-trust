-- Q62: Median delivery_days per city
-- Percentile function vs manual rank version

-- Version 1: percentile_cont (interpolated)
SELECT
    city_std,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY delivery_days::int) AS median_delivery_days
FROM trusted_enriched
WHERE
    status_std = 'Delivered'
    AND delivery_days ~ '^\d+$'
GROUP BY city_std
ORDER BY city_std;

-- Version 2: Manual rank (integer position, no interpolation)
WITH ranked AS (
    SELECT
        city_std,
        delivery_days::int AS days,
        ROW_NUMBER() OVER (PARTITION BY city_std ORDER BY delivery_days::int) AS rn,
        COUNT(*) OVER (PARTITION BY city_std) AS cnt
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND delivery_days ~ '^\d+$'
),
mid AS (
    SELECT city_std, days
    FROM ranked
    WHERE rn IN ((cnt + 1) / 2, (cnt + 2) / 2)
)
SELECT city_std, ROUND(AVG(days), 2) AS median_days
FROM mid
GROUP BY city_std
ORDER BY city_std;

-- Difference:
-- percentile_cont interpolates between the two middle values for even counts.
-- Manual rank averages the two middle values (same as percentile_cont for this case).
-- percentile_disc would return the lower middle value (no interpolation).
-- For even counts, percentile_cont and manual rank (averaging) give same result.
-- percentile_disc differs by returning the lower value.
-- Report uses percentile_cont (standard statistical median).