-- Q44: High quantities (IQR fence)

WITH q AS (
    SELECT CAST(TRIM(quantity) AS NUMERIC) AS qty
    FROM orders
    WHERE TRIM(quantity) ~ '^\d+(\.\d+)?$'
),

stats AS (
    SELECT
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY qty) AS q1,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY qty) AS q3
    FROM q
),

fence AS (
    SELECT q3 + 3 * (q3 - q1) AS fence_val FROM stats
)

SELECT
    'error' AS verdict,
    MAX(f.fence_val) AS fence,
    COUNT(*) FILTER (WHERE q.qty > f.fence_val) AS flagged_rows,
    STRING_AGG(
        DISTINCT CAST(q.qty AS TEXT),
        ','
        ORDER BY CAST(q.qty AS TEXT)
    )
    FILTER (WHERE q.qty > f.fence_val)
        AS flagged_values
FROM q CROSS JOIN fence AS f;
