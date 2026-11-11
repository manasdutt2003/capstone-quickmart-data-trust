-- Q24: Customers with and without orders
-- Requires: customers_loaded, orders_loaded (staging).
-- Rebuilds the D03 customer master (email groups with earliest signup as
-- survivor; placeholder emails stay separate), matches order-side customer
-- ids (raw spellings normalised) against master ids, and applies the
-- cross-id loser remap before matching (same-id remaps are identity).
-- Expected reading: master 499 = 479 with orders + 20 without; 482
-- normalised order-side ids, 5,899 order rows attach, and the only
-- unresolved rows are 144 unknown-id rows (quarantine backup R01) + 60
-- blanks - nothing else is unresolved.

WITH cleaned AS (
    SELECT
        customer_id AS cid,
        COALESCE(TRIM(signup_date), '') AS sd,
        UPPER(TRIM(COALESCE(email, ''))) AS email_key
    FROM customers_loaded
),

flagged AS (
    SELECT cid, sd, email_key,
           email_key IN ('', 'NA', 'N/A', 'NULL', 'NONE', 'UNKNOWN',
                         '?', '-', '--') AS is_ph
    FROM cleaned
),

numbered AS (
    SELECT cid, email_key, is_ph,
           ROW_NUMBER() OVER (PARTITION BY email_key ORDER BY sd, cid)
               AS rn
    FROM flagged
),

survivors AS (
    SELECT cid FROM numbered WHERE is_ph OR rn = 1
),

losers AS (
    SELECT n.cid AS loser_id, s.cid AS survivor_id
    FROM numbered AS n
    JOIN numbered AS s
      ON s.email_key = n.email_key AND s.rn = 1 AND NOT s.is_ph
    WHERE NOT n.is_ph AND n.rn > 1
),

cross_remap AS (
    SELECT DISTINCT
        regexp_replace(UPPER(TRIM(loser_id)), '[\s-]+', '', 'g')
            AS loser_n,
        regexp_replace(UPPER(TRIM(survivor_id)), '[\s-]+', '', 'g')
            AS survivor_n
    FROM losers
    WHERE regexp_replace(UPPER(TRIM(loser_id)), '[\s-]+', '', 'g')
       <> regexp_replace(UPPER(TRIM(survivor_id)), '[\s-]+', '', 'g')
),

master_norm AS (
    SELECT DISTINCT regexp_replace(UPPER(TRIM(cid)), '[\s-]+', '', 'g')
        AS mid
    FROM survivors
),

order_ids AS (
    SELECT regexp_replace(UPPER(TRIM(COALESCE(raw_customer_id, ''))),
                          '[\s-]+', '', 'g') AS oid_n
    FROM orders_loaded
),

attached AS (
    SELECT COALESCE(cr.survivor_n, o.oid_n) AS mid
    FROM order_ids AS o
    LEFT JOIN cross_remap AS cr ON cr.loser_n = o.oid_n
)

SELECT scope, measure, row_count
FROM (
    SELECT 'customer master' AS scope, 'master rows (after D03)' AS measure,
           COUNT(*) AS row_count, 1 AS scope_ord, 1 AS sort_key
    FROM survivors
    UNION ALL
    SELECT 'customer master', 'with orders', COUNT(DISTINCT m.mid), 1, 2
    FROM master_norm AS m
    WHERE EXISTS (SELECT 1 FROM attached AS a WHERE a.mid = m.mid)
    UNION ALL
    SELECT 'customer master', 'without orders', COUNT(DISTINCT m.mid), 1, 3
    FROM master_norm AS m
    WHERE NOT EXISTS (SELECT 1 FROM attached AS a WHERE a.mid = m.mid)
    UNION ALL
    SELECT 'order-side ids', 'distinct normalised ids',
           COUNT(DISTINCT oid_n), 2, 1
    FROM order_ids
    UNION ALL
    SELECT 'order-side ids', 'rows attachable to master', COUNT(*), 2, 2
    FROM attached AS a
    JOIN master_norm AS m ON m.mid = a.mid
    UNION ALL
    SELECT 'D03 remap', 'rows under merged loser id', COUNT(*), 3, 1
    FROM order_ids AS o
    JOIN cross_remap AS cr ON cr.loser_n = o.oid_n
    UNION ALL
    SELECT 'unmatched orders', 'unknown id rows', COUNT(*), 4, 1
    FROM attached AS a
    LEFT JOIN master_norm AS m ON m.mid = a.mid
    WHERE m.mid IS NULL AND a.mid <> ''
    UNION ALL
    SELECT 'unmatched orders', 'blank customer_id rows', COUNT(*), 4, 2
    FROM order_ids
    WHERE oid_n = ''
) AS t
ORDER BY scope_ord, sort_key;
