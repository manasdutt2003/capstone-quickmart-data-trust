-- Q27: Repeated product_ids and D04
-- Requires: products_clean (staging).
-- Raw ids are counted for exact repeats, then spelling variants are
-- normalised (norm_id: strip, upper-case, drop spaces and dashes). The
-- five variant rows normalise to ids no other row carries, so D04 never
-- merges and never conflicts. Expected reading: 0 repeats, 5 changed
-- rows (p09, P-10, P-20, P-26, P-30), 30 raw ids -> 30 normalised ids
-- (30 rows after D04).

WITH ids AS (
    SELECT
        raw_product_id AS raw_id,
        UPPER(REGEXP_REPLACE(TRIM(raw_product_id), '[\s-]+', '', 'g'))
            AS norm_id
    FROM products_clean
),

counted AS (
    SELECT
        COUNT(*) AS rows_total,
        COUNT(*) FILTER (WHERE TRIM(raw_id) <> norm_id) AS rows_changed,
        COUNT(DISTINCT raw_id) AS distinct_raw,
        COUNT(DISTINCT norm_id) AS distinct_norm
    FROM ids
)

SELECT scope, measure, row_count
FROM (
    SELECT 'product ids' AS scope, 'product rows' AS measure,
           rows_total AS row_count, 1 AS scope_ord, 1 AS sort_key
    FROM counted
    UNION ALL
    SELECT 'product ids', 'repeated raw id rows',
           rows_total - distinct_raw, 1, 2
    FROM counted
    UNION ALL
    SELECT 'product ids', 'rows changed by normalisation',
           rows_changed, 1, 3
    FROM counted
    UNION ALL
    SELECT 'product ids', 'distinct raw ids',
           distinct_raw, 1, 4
    FROM counted
    UNION ALL
    SELECT 'product ids', 'distinct normalised ids',
           distinct_norm, 1, 5
    FROM counted
    UNION ALL
    SELECT 'product ids', 'rows after D04 (one per normalised id)',
           distinct_norm, 1, 6
    FROM counted
    UNION ALL
    SELECT 'product ids', 'D04 merge groups (normalised ids on >1 row)',
           COUNT(*), 1, 7
    FROM (
        SELECT norm_id FROM ids GROUP BY norm_id HAVING COUNT(*) > 1
    ) AS dup
) AS t
ORDER BY scope_ord, sort_key, measure;
