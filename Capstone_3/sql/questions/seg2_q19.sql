-- Q19: Unusable stock per category
-- Requires: products_clean (staging).
-- stock_qty is classified per product - missing (empty/placeholder),
-- bad (parseable-but-invalid: negative or non-integer), else usable - and
-- rolled up per category with case/spacing variants grouped. Mirrors
-- src/quality_checks.py: QC_PROD_STOCK_INVALID = NOT usable.
-- Expected reading: 16 of 30 products are usable (missing 12 + bad 2 =
-- 14 unusable), so category roll-ups are partial (Beverages 0/3) and must
-- publish coverage; an overall stock total would understate.

WITH tokens (token) AS (
    VALUES ('NA'), ('N/A'), ('na'), ('n/a'), ('-'), ('--'), ('unknown'),
           ('UNKNOWN'), ('Unknown'), ('null'), ('NULL'), ('None'),
           ('none'), ('?'), ('MISSING'), ('missing')
),

classified AS (
    SELECT
        CASE WHEN COALESCE(TRIM(raw_category), '') = '' THEN '(blank)'
             ELSE INITCAP(TRIM(raw_category)) END AS category,
        COALESCE(TRIM(raw_stock_qty), '') = ''
            OR TRIM(raw_stock_qty) IN (SELECT token FROM tokens)
            AS is_missing,
        CASE
            WHEN COALESCE(TRIM(raw_stock_qty), '')
                 ~ '^[0-9]+(\.[0-9]+)?$'
            THEN (TRIM(raw_stock_qty))::numeric
                 = FLOOR((TRIM(raw_stock_qty))::numeric)
            ELSE FALSE
        END AS is_integer_number
    FROM products_clean
)

SELECT category, total_products, usable, unusable, missing_rows, bad_rows
FROM (
    SELECT
        category,
        COUNT(*) AS total_products,
        COUNT(*) FILTER (
            WHERE NOT is_missing AND is_integer_number) AS usable,
        COUNT(*) FILTER (
            WHERE is_missing OR NOT is_integer_number) AS unusable,
        COUNT(*) FILTER (WHERE is_missing) AS missing_rows,
        COUNT(*) FILTER (
            WHERE NOT is_missing AND NOT is_integer_number) AS bad_rows
    FROM classified
    GROUP BY category
    UNION ALL
    SELECT
        'all products',
        COUNT(*),
        COUNT(*) FILTER (WHERE NOT is_missing AND is_integer_number),
        COUNT(*) FILTER (WHERE is_missing OR NOT is_integer_number),
        COUNT(*) FILTER (WHERE is_missing),
        COUNT(*) FILTER (WHERE NOT is_missing AND NOT is_integer_number)
    FROM classified
) AS t
ORDER BY CASE WHEN category = 'all products' THEN 2 ELSE 1 END,
         total_products DESC,
         category;
