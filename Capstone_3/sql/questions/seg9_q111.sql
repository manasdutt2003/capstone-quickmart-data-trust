-- Q111: category order-share shift >5pp between range halves
-- Split at the midpoint of [min, max] date; second half takes the odd day.

WITH bounds AS (
    SELECT
        MIN(order_date::timestamp) AS lo,
        MAX(order_date::timestamp) AS hi
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
        AND order_date ~ '^\d{4}-\d{2}-\d{2}$'
),
halved AS (
    SELECT
        category_std,
        CASE
            WHEN order_date::timestamp < (
                SELECT lo + ((hi - lo) / 2) FROM bounds
            ) THEN 'first'
            ELSE 'second'
        END AS half
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
        AND order_date ~ '^\d{4}-\d{2}-\d{2}$'
),
counts AS (
    SELECT category_std, half, COUNT(*) AS n
    FROM halved
    GROUP BY category_std, half
),
totals AS (
    SELECT half, SUM(n) AS tot
    FROM counts
    GROUP BY half
),
shares AS (
    SELECT
        c.category_std,
        COALESCE(
            MAX(CASE WHEN c.half = 'first' THEN c.n ELSE 0 END)::numeric
            / NULLIF((SELECT tot FROM totals WHERE half = 'first'), 0)
            * 100,
            0
        ) AS share_first,
        COALESCE(
            MAX(CASE WHEN c.half = 'second' THEN c.n ELSE 0 END)::numeric
            / NULLIF((SELECT tot FROM totals WHERE half = 'second'), 0)
            * 100,
            0
        ) AS share_second
    FROM counts AS c
    GROUP BY c.category_std
)
SELECT
    category_std,
    ROUND(share_first, 2) AS share_first_pct,
    ROUND(share_second, 2) AS share_second_pct,
    ROUND(share_second - share_first, 2) AS shift_pp,
    (ABS(share_second - share_first) > 5) AS mover
FROM shares
ORDER BY category_std;
