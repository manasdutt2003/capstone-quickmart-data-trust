-- Q10: Empty vs placeholder cells per customer column
-- Requires: customers_loaded (staging).
-- Mirrors src/quality_checks.py::PLACEHOLDERS (16-token set) on the raw
-- extract text: empty = blank after strip; placeholder = an explicit token
-- standing in for "no value". Both count as missing everywhere downstream.

WITH tokens (token) AS (
    VALUES ('NA'), ('N/A'), ('na'), ('n/a'), ('-'), ('--'), ('unknown'),
           ('UNKNOWN'), ('Unknown'), ('null'), ('NULL'), ('None'),
           ('none'), ('?'), ('MISSING'), ('missing')
),

cells (col_ord, column_name, value) AS (
    SELECT 1, 'customer_id', raw_customer_id FROM customers_loaded
    UNION ALL
    SELECT 2, 'customer_name', raw_customer_name FROM customers_loaded
    UNION ALL
    SELECT 3, 'email', raw_email FROM customers_loaded
    UNION ALL
    SELECT 4, 'city', raw_city FROM customers_loaded
    UNION ALL
    SELECT 5, 'phone', raw_phone FROM customers_loaded
    UNION ALL
    SELECT 6, 'signup_date', raw_signup_date FROM customers_loaded
)

SELECT
    column_name,
    COUNT(*) FILTER (WHERE COALESCE(TRIM(value), '') = '') AS empty_rows,
    COUNT(*) FILTER (WHERE TRIM(value) IN (SELECT token FROM tokens))
        AS placeholder_rows,
    COUNT(*) FILTER (
        WHERE COALESCE(TRIM(value), '') = ''
           OR TRIM(value) IN (SELECT token FROM tokens)
    ) AS missing_rows
FROM cells
GROUP BY col_ord, column_name
ORDER BY col_ord;
