-- Q20: Repeated order_ids and what the pipeline removed
-- Requires: orders_loaded (staging).
-- Mirrors src/deduplication.py: D01 = exact business-row copies over
-- BUSINESS_COLS (order_id excluded), keep-first in source-row order;
-- D02 = an order_id group whose business tuples differ (priority-survivor
-- path, unexercised when conflicts are 0). Statuses use the cleaned
-- marker (blank -> '(blank)'). Expected reading: 103 repeated ids / 206
-- rows, every copy exact (conflicting groups 0), 103 copies removed,
-- repeats spanning all statuses - system double-writes, not workflow.

WITH ranked AS (
    SELECT
        TRIM(order_id) AS oid,
        _source_row::int AS src,
        ROW(COALESCE(customer_id, ''), COALESCE(product_id, ''),
            COALESCE(order_date, ''), COALESCE(quantity, ''),
            COALESCE(unit_price_paid, ''), COALESCE(discount, ''),
            COALESCE(payment_mode, ''), COALESCE(order_status, ''),
            COALESCE(delivery_days, ''), COALESCE(notes, '')) AS biz_tuple,
        order_status
    FROM orders_loaded
),

numbered AS (
    SELECT oid, order_status,
           ROW_NUMBER() OVER (PARTITION BY biz_tuple ORDER BY src)
               AS tuple_rn
    FROM ranked
),

groups AS (
    SELECT oid, COUNT(*) AS n, COUNT(DISTINCT biz_tuple) AS distinct_tuples
    FROM ranked
    GROUP BY oid
)

SELECT scope, measure, row_count
FROM (
    SELECT 'duplicate order ids' AS scope, 'repeated order_ids' AS measure,
           COUNT(*) AS row_count, 1 AS scope_ord, 1 AS sort_key
    FROM groups WHERE n > 1
    UNION ALL
    SELECT 'duplicate order ids', 'rows involved', SUM(n), 1, 2
    FROM groups WHERE n > 1
    UNION ALL
    SELECT 'duplicate order ids', 'conflicting groups',
           COUNT(*) FILTER (WHERE distinct_tuples > 1), 1, 3
    FROM groups WHERE n > 1
    UNION ALL
    SELECT 'duplicate order ids', 'removed by D01 (keep first)',
           COUNT(*), 1, 4
    FROM numbered WHERE tuple_rn > 1
    UNION ALL
    SELECT 'duplicate order ids', 'QC_ORD_ID_DUP rows', SUM(n), 1, 5
    FROM groups WHERE n > 1
    UNION ALL
    SELECT 'removed copy status',
           CASE WHEN order_status IN ('', 'MISSING') THEN '(blank)'
                ELSE order_status END,
           COUNT(*), 2, 100 - COUNT(*)
    FROM numbered WHERE tuple_rn > 1
    GROUP BY 2
) AS t
ORDER BY scope_ord, sort_key, measure;
