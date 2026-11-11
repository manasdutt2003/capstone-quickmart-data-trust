-- Q15: Missing and text-form product prices
-- Requires: products_clean (staging).
-- Mirrors src/normalise.py::parse_float: plain numbers, numbers written
-- with text (rupee sign, thousands comma, '?' stray) that still parse, and
-- unusable values (NA/blank) that stay null; QC_PROD_PRICE_INVALID (2) is
-- the cross-check. Expected reading: 6 non-numeric texts = 4 text forms
-- (P-10 rupee-60, P13/P25 rupee-210, P21 '1,200') + 2 unusable (NA);
-- 28 prices are parseable.

WITH classified AS (
    SELECT
        raw_product_id,
        raw_unit_price,
        CASE
            WHEN TRIM(raw_unit_price) ~ '^[0-9]+(\.[0-9]+)?$'
                THEN 'plain number'
            WHEN TRIM(REPLACE(REPLACE(REPLACE(raw_unit_price, '₹', ''),
                                      ',', ''), '?', ''))
                 ~ '^[0-9]+(\.[0-9]+)?$'
                THEN 'text form (₹/comma)'
            ELSE 'unusable (NA/blank)'
        END AS price_class
    FROM products_clean
)

SELECT
    price_class,
    row_count,
    CASE WHEN price_class = 'plain number' THEN '-' ELSE products END AS products
FROM (
    SELECT
        price_class,
        COUNT(*) AS row_count,
        STRING_AGG(TRIM(raw_product_id) || ' ' || TRIM(raw_unit_price),
                   ', ' ORDER BY raw_product_id) AS products,
        CASE price_class
            WHEN 'plain number' THEN 1
            WHEN 'text form (₹/comma)' THEN 2
            ELSE 3
        END AS sort_key
    FROM classified
    GROUP BY price_class
    UNION ALL
    SELECT
        'parseable total',
        COUNT(*),
        '-',
        4
    FROM classified
    WHERE price_class IN ('plain number', 'text form (₹/comma)')
) AS t
ORDER BY sort_key;
