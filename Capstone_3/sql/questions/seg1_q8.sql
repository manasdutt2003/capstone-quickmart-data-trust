-- Q8: Commas and double quotes trapped inside notes
-- Requires: orders_loaded (staging).
-- Standard CSV quoting keeps embedded specials inside the field; the
-- field-count audit that proves no row was split is loader-level (see
-- docs/sql_answers_segment1_3.md). This counts how many notes actually
-- carry commas / double quotes.

SELECT check_name, row_count
FROM (
    SELECT 'notes empty' AS check_name, 1 AS sort_key,
           COUNT(*) AS row_count
    FROM orders_loaded
    WHERE raw_notes IS NULL OR TRIM(raw_notes) = ''
    UNION ALL
    SELECT 'notes with comma', 2, COUNT(*)
    FROM orders_loaded
    WHERE raw_notes LIKE '%,%'
    UNION ALL
    SELECT 'notes with double quote', 3, COUNT(*)
    FROM orders_loaded
    WHERE raw_notes LIKE '%"%'
    UNION ALL
    SELECT 'notes with comma and quote', 4, COUNT(*)
    FROM orders_loaded
    WHERE raw_notes LIKE '%,%' AND raw_notes LIKE '%"%'
) AS checks
ORDER BY sort_key;
