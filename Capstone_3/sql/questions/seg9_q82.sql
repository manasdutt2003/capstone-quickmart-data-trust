-- Q82: longest run of consecutive dates with zero orders
-- Recursive calendar left-joined to daily counts; gaps-and-islands bounds.

WITH RECURSIVE bounds AS (
    SELECT
        MIN(order_date::date) AS lo,
        MAX(order_date::date) AS hi
    FROM trusted_enriched
    WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
),
calendar (d) AS (
    SELECT lo FROM bounds
    UNION ALL
    SELECT d + 1 FROM calendar, bounds WHERE d < hi
),
daily AS (
    SELECT order_date::date AS d, COUNT(*) AS n
    FROM trusted_enriched
    WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
    GROUP BY order_date::date
),
flagged AS (
    SELECT c.d
    FROM calendar AS c
    LEFT JOIN daily AS dy ON c.d = dy.d
    WHERE COALESCE(dy.n, 0) = 0
),
islands AS (
    SELECT
        d,
        d - ROW_NUMBER() OVER (ORDER BY d)::int AS island
    FROM flagged
),
runs AS (
    SELECT
        MIN(d) AS start_date,
        MAX(d) AS end_date,
        COUNT(*) AS run_length
    FROM islands
    GROUP BY island
)
SELECT run_length, start_date, end_date
FROM runs
ORDER BY run_length DESC, start_date
LIMIT 1;
