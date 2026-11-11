-- Q26: Shared product names
-- Requires: products_clean (staging).
-- Names are compared case-insensitively across the 30 catalogue rows;
-- D04's name+category+price comparison only activates when normalised
-- ids collide, and no name is used on more than one row. Expected
-- reading: 30 rows, 30 distinct names, 0 shared names (name-level
-- duplicate handling is a non-issue for this catalogue).

WITH names AS (
    SELECT LOWER(TRIM(raw_product_name)) AS name
    FROM products_clean
),

multi AS (
    SELECT name FROM names GROUP BY name HAVING COUNT(*) > 1
)

SELECT scope, measure, row_count
FROM (
    SELECT 'product names' AS scope, 'product rows' AS measure,
           COUNT(*) AS row_count, 1 AS scope_ord, 1 AS sort_key
    FROM products_clean
    UNION ALL
    SELECT 'product names', 'distinct names (case-insensitive)',
           COUNT(DISTINCT name), 1, 2
    FROM names
    UNION ALL
    SELECT 'product names', 'names on more than one row',
           COUNT(*), 1, 3
    FROM multi
) AS t
ORDER BY scope_ord, sort_key, measure;
