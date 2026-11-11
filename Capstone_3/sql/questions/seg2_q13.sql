-- Q13: Empty unit_price_paid cells by order month and by product
-- Requires: orders_loaded (staging).
-- The 267 missing prices are bucketed by the month of the usable
-- order_date (rows without a usable date fall in a '(no date)' bucket)
-- and by raw product_id spelling. Expected reading: no month or product
-- carries an unusual share - near uniform spread (~8.9 expected per
-- product); the only note is that 11 empty prices sit on rows whose
-- order_date is itself unusable.

WITH tokens (token) AS (
    VALUES ('NA'), ('N/A'), ('na'), ('n/a'), ('-'), ('--'), ('unknown'),
           ('UNKNOWN'), ('Unknown'), ('null'), ('NULL'), ('None'),
           ('none'), ('?'), ('MISSING'), ('missing')
),

missing_prices AS (
    SELECT
        CASE WHEN TRIM(order_date) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
             THEN LEFT(TRIM(order_date), 7) END AS month,
        CASE WHEN TRIM(raw_product_id) IS NULL THEN '(blank)'
             WHEN TRIM(raw_product_id) = '' THEN '(blank)'
             ELSE TRIM(raw_product_id) END AS pid,
        CASE WHEN TRIM(raw_product_id) IS NULL THEN 'zzz'
             WHEN TRIM(raw_product_id) = '' THEN 'zzz'
             ELSE TRIM(raw_product_id) END AS pid_sort
    FROM orders_loaded
    WHERE COALESCE(TRIM(raw_unit_price_paid), '') = ''
       OR TRIM(raw_unit_price_paid) IN (SELECT token FROM tokens)
),

buckets AS (
    SELECT
        'month' AS scope,
        COALESCE(month, '(no date)') AS label,
        COALESCE(month, '9999-99') AS sort_label,
        COUNT(*) AS empty_rows
    FROM missing_prices
    GROUP BY 2, 3
    UNION ALL
    SELECT 'product', pid, pid_sort, COUNT(*)
    FROM missing_prices
    GROUP BY 2, 3
)

SELECT
    scope,
    label,
    empty_rows,
    ROUND(100.0 * empty_rows / (SELECT COUNT(*) FROM missing_prices), 1)
        AS share_pct
FROM buckets
ORDER BY CASE scope WHEN 'month' THEN 1 ELSE 2 END,
         empty_rows DESC,
         sort_label;
