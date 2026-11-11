-- Q7: Non-ASCII characters in the decoded files (the rupee sign)
-- Requires: orders_loaded, customers_loaded, products_clean (staging).
-- UTF-8/BOM detection and the cp1252 misread demo are loader-level (see
-- docs/sql_answers_segment1_3.md); what the SQL layer can show is the
-- decoded content: rows carrying any non-ASCII character (octet_length vs
-- length) and the exact count of rupee-sign characters.

WITH counts AS (
    SELECT
        'customers' AS scope,
        COUNT(*) FILTER (
            WHERE octet_length(to_jsonb(t)::text)
                  <> length(to_jsonb(t)::text)) AS rows_with_non_ascii,
        SUM(
            length(to_jsonb(t)::text)
            - length(REPLACE(to_jsonb(t)::text, '₹', ''))) AS rupee_chars
    FROM customers_loaded AS t
    UNION ALL
    SELECT
        'products',
        COUNT(*) FILTER (
            WHERE octet_length(to_jsonb(t)::text)
                  <> length(to_jsonb(t)::text)),
        SUM(
            length(to_jsonb(t)::text)
            - length(REPLACE(to_jsonb(t)::text, '₹', '')))
    FROM products_clean AS t
    UNION ALL
    SELECT
        'orders',
        COUNT(*) FILTER (
            WHERE octet_length(to_jsonb(t)::text)
                  <> length(to_jsonb(t)::text)),
        SUM(
            length(to_jsonb(t)::text)
            - length(REPLACE(to_jsonb(t)::text, '₹', '')))
    FROM orders_loaded AS t
)

SELECT scope, rows_with_non_ascii, rupee_chars
FROM counts
ORDER BY CASE scope
    WHEN 'customers' THEN 1
    WHEN 'products' THEN 2
    ELSE 3
END;
