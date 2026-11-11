-- Q3: Value forms that a typed read would mangle
-- Requires: orders_loaded, products_clean (staging).
-- Every value is loaded as text; this lists the raw text forms per
-- numeric-looking column (rupee and percent forms, blanks, 'NA', 'three',
-- '2.5', '-2') so dtype guessing can never change them silently.

SELECT scope, column_name, value_form, row_count
FROM (
    SELECT 1 AS sort_key, 'orders' AS scope, 'quantity' AS column_name,
           COALESCE(NULLIF(raw_quantity, ''), '(blank)') AS value_form,
           COUNT(*) AS row_count
    FROM orders_loaded
    GROUP BY raw_quantity
    UNION ALL
    SELECT 2, 'orders', 'discount',
           COALESCE(NULLIF(raw_discount, ''), '(blank)'),
           COUNT(*)
    FROM orders_loaded
    GROUP BY raw_discount
    UNION ALL
    SELECT 3, 'products', 'unit_price',
           COALESCE(NULLIF(raw_unit_price, ''), '(blank)'),
           COUNT(*)
    FROM products_clean
    GROUP BY raw_unit_price
) AS forms
ORDER BY sort_key, row_count DESC, value_form;
