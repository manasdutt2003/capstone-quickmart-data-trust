-- Q17: Empty delivery_days by order status
-- Requires: orders_loaded (staging).
-- Empty delivery_days cells (empty or placeholder on the raw text) grouped
-- by cleaned order_status, with within-status shares so statuses of
-- different sizes compare fairly, plus the all-rows coverage context.
-- Expected reading: the 142 empties (2.33%) are spread evenly - every
-- status sits between 1.75% and 3.85%, including Delivered - so entry
-- omission, not a workflow rule; delivery metrics use the 5,961 valued
-- rows.

WITH tokens (token) AS (
    VALUES ('NA'), ('N/A'), ('na'), ('n/a'), ('-'), ('--'), ('unknown'),
           ('UNKNOWN'), ('Unknown'), ('null'), ('NULL'), ('None'),
           ('none'), ('?'), ('MISSING'), ('missing')
),

deliveries AS (
    SELECT
        CASE WHEN TRIM(order_status) IN ('', 'MISSING') THEN '(blank)'
             ELSE TRIM(order_status) END AS status,
        COALESCE(TRIM(raw_delivery_days), '') = ''
            OR TRIM(raw_delivery_days) IN (SELECT token FROM tokens)
            AS is_empty
    FROM orders_loaded
),

by_status AS (
    SELECT status, COUNT(*) AS total_rows,
           COUNT(*) FILTER (WHERE is_empty) AS empty_rows
    FROM deliveries
    GROUP BY status
)

SELECT status, empty_rows, total_rows,
       ROUND(100.0 * empty_rows / total_rows, 2) AS empty_pct
FROM (
    SELECT '(all statuses)' AS status, COUNT(*) AS total_rows,
           COUNT(*) FILTER (WHERE is_empty) AS empty_rows
    FROM deliveries
    UNION ALL
    SELECT status, total_rows, empty_rows FROM by_status
) AS t
ORDER BY CASE status
    WHEN '(all statuses)' THEN 0
    WHEN 'Delivered' THEN 1
    WHEN 'Cancelled' THEN 2
    WHEN 'In Transit' THEN 3
    WHEN 'Pending' THEN 4
    WHEN 'Returned' THEN 5
    ELSE 6
END;
