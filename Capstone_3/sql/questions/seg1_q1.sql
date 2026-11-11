-- Q1: Rows per extract vs rows loaded
-- Requires: orders_loaded, customers_loaded, products_clean (staging).
-- The loader keeps every data row as text (the blank-line filter never
-- fired); counting the loaded rows per table makes any future drop visible
-- against data/raw_manifest.json rows_in_file.

SELECT scope, rows_loaded
FROM (
    SELECT 'customers' AS scope, 1 AS ord, COUNT(*) AS rows_loaded
    FROM customers_loaded
    UNION ALL
    SELECT 'products', 2, COUNT(*)
    FROM products_clean
    UNION ALL
    SELECT 'orders', 3, COUNT(*)
    FROM orders_loaded
) AS counts
ORDER BY ord;
