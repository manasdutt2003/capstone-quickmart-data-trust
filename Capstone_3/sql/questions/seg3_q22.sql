-- Q22: Repeated customers - same person?
-- Requires: customers_loaded (staging).
-- Mirrors src/deduplication.py::build_customer_master (D03): customers are
-- grouped by normalised email (lower + strip; placeholder emails never
-- merge), survivor = earliest signup_date then lower id, one loser record
-- per extra row. Expected reading: 21 merges = 20 same-id repeat
-- registrations + 1 cross-id merge (shared email); master 520 -> 499.

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
    SELECT n.email_key, n.cid AS loser_id, s.cid AS survivor_id
    FROM numbered AS n
    JOIN numbered AS s
      ON s.email_key = n.email_key AND s.rn = 1 AND NOT s.is_ph
    WHERE NOT n.is_ph AND n.rn > 1
)

SELECT scope, measure, row_count
FROM (
    SELECT 'D03 email merges' AS scope,
           'same-id repeat merges' AS measure,
           COUNT(*) FILTER (
               WHERE regexp_replace(UPPER(TRIM(loser_id)), '[\s-]+', '', 'g')
                   = regexp_replace(UPPER(TRIM(survivor_id)), '[\s-]+', '', 'g')
           ) AS row_count,
           1 AS scope_ord, 1 AS sort_key
    FROM losers
    UNION ALL
    SELECT 'D03 email merges', 'cross-id merges',
           COUNT(*) FILTER (
               WHERE regexp_replace(UPPER(TRIM(loser_id)), '[\s-]+', '', 'g')
                   <> regexp_replace(UPPER(TRIM(survivor_id)), '[\s-]+', '', 'g')
           ), 1, 2
    FROM losers
    UNION ALL
    SELECT 'D03 email merges', 'merged rows (losers)',
           COUNT(*), 1, 3
    FROM losers
    UNION ALL
    SELECT 'D03 email merges', 'merge groups',
           COUNT(DISTINCT email_key), 1, 4
    FROM losers
    UNION ALL
    SELECT 'customer master', 'customers before', COUNT(*), 2, 1
    FROM customers_loaded
    UNION ALL
    SELECT 'customer master', 'master rows (after D03)', COUNT(*), 2, 2
    FROM survivors
) AS t
ORDER BY scope_ord, sort_key;
