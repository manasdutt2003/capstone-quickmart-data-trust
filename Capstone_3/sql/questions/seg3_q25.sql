-- Q25: Shared email addresses
-- Requires: customers_loaded (staging).
-- Customers are grouped by normalised email with placeholders excluded
-- (placeholder means an empty or sentinel email, never merged); every
-- group with more than one row is a merge decision. The excluded split
-- uses the raw email texts. Expected reading: 21 groups needing a
-- decision, 21 extra rows merged, 42 emails excluded (32 empty + 10
-- placeholder N/A) - excluding them prevents false merges, since many
-- customers legitimately share blank/sentinel values.

WITH cleaned AS (
    SELECT
        UPPER(TRIM(COALESCE(email, ''))) AS email_key,
        COALESCE(TRIM(raw_email), '') AS raw_email
    FROM customers_loaded
),

flagged AS (
    SELECT email_key, raw_email,
           email_key IN ('', 'NA', 'N/A', 'NULL', 'NONE', 'UNKNOWN',
                         '?', '-', '--') AS is_ph
    FROM cleaned
),

grouped AS (
    SELECT email_key, COUNT(*) AS n
    FROM flagged
    WHERE NOT is_ph
    GROUP BY email_key
)

SELECT scope, measure, row_count
FROM (
    SELECT 'shared-email groups' AS scope,
           'groups needing a decision' AS measure,
           COUNT(*) AS row_count, 1 AS scope_ord, 1 AS sort_key
    FROM grouped
    WHERE n > 1
    UNION ALL
    SELECT 'shared-email groups', 'extra rows merged', SUM(n - 1), 1, 2
    FROM grouped
    WHERE n > 1
    UNION ALL
    SELECT 'excluded emails', 'empty',
           COUNT(*) FILTER (WHERE raw_email = ''), 2, 1
    FROM flagged
    WHERE is_ph
    UNION ALL
    SELECT 'excluded emails', 'placeholder',
           COUNT(*) FILTER (
               WHERE raw_email IN ('NA', 'N/A', 'na', 'n/a', '-', '--',
                                   'unknown', 'UNKNOWN', 'Unknown', 'null',
                                   'NULL', 'None', 'none', '?', 'MISSING',
                                   'missing')), 2, 2
    FROM flagged
    WHERE is_ph
    UNION ALL
    SELECT 'excluded emails', 'total excluded', COUNT(*), 2, 3
    FROM flagged
    WHERE is_ph
) AS t
ORDER BY scope_ord, sort_key;
