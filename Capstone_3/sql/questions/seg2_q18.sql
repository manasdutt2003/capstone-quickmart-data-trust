-- Q18: Co-empty column pairs
-- Requires: orders_loaded (staging).
-- Pair-wise co-emptiness over all 11 order columns (missing = empty or
-- placeholder on the raw text); only pairs with at least one co-missing
-- row are kept, ranked by count. Expected reading: the strongest pairs
-- all involve optional fields (discount, notes, status, payment) going
-- missing together - one cause: rows captured with minimal information
-- leave optional cells blank together; no systemic capture fault.

WITH tokens (token) AS (
    VALUES ('NA'), ('N/A'), ('na'), ('n/a'), ('-'), ('--'), ('unknown'),
           ('UNKNOWN'), ('Unknown'), ('null'), ('NULL'), ('None'),
           ('none'), ('?'), ('MISSING'), ('missing')
),

flags AS (
    SELECT
        _source_row::int AS rid,
        COALESCE(TRIM(raw_order_id), '') = ''
            OR TRIM(raw_order_id) IN (SELECT token FROM tokens) AS m_order_id,
        COALESCE(TRIM(raw_customer_id), '') = ''
            OR TRIM(raw_customer_id) IN (SELECT token FROM tokens) AS m_customer_id,
        COALESCE(TRIM(raw_product_id), '') = ''
            OR TRIM(raw_product_id) IN (SELECT token FROM tokens) AS m_product_id,
        COALESCE(TRIM(raw_order_date), '') = ''
            OR TRIM(raw_order_date) IN (SELECT token FROM tokens) AS m_order_date,
        COALESCE(TRIM(raw_quantity), '') = ''
            OR TRIM(raw_quantity) IN (SELECT token FROM tokens) AS m_quantity,
        COALESCE(TRIM(raw_unit_price_paid), '') = ''
            OR TRIM(raw_unit_price_paid) IN (SELECT token FROM tokens)
            AS m_unit_price_paid,
        COALESCE(TRIM(raw_discount), '') = ''
            OR TRIM(raw_discount) IN (SELECT token FROM tokens) AS m_discount,
        COALESCE(TRIM(raw_payment_mode), '') = ''
            OR TRIM(raw_payment_mode) IN (SELECT token FROM tokens)
            AS m_payment_mode,
        COALESCE(TRIM(raw_order_status), '') = ''
            OR TRIM(raw_order_status) IN (SELECT token FROM tokens)
            AS m_order_status,
        COALESCE(TRIM(raw_delivery_days), '') = ''
            OR TRIM(raw_delivery_days) IN (SELECT token FROM tokens)
            AS m_delivery_days,
        COALESCE(TRIM(raw_notes), '') = ''
            OR TRIM(raw_notes) IN (SELECT token FROM tokens) AS m_notes
    FROM orders_loaded
),

cells AS (
    SELECT rid, 1 AS c_ord, 'order_id' AS column_name, m_order_id AS is_missing FROM flags
    UNION ALL SELECT rid, 2, 'customer_id', m_customer_id FROM flags
    UNION ALL SELECT rid, 3, 'product_id', m_product_id FROM flags
    UNION ALL SELECT rid, 4, 'order_date', m_order_date FROM flags
    UNION ALL SELECT rid, 5, 'quantity', m_quantity FROM flags
    UNION ALL SELECT rid, 6, 'unit_price_paid', m_unit_price_paid FROM flags
    UNION ALL SELECT rid, 7, 'discount', m_discount FROM flags
    UNION ALL SELECT rid, 8, 'payment_mode', m_payment_mode FROM flags
    UNION ALL SELECT rid, 9, 'order_status', m_order_status FROM flags
    UNION ALL SELECT rid, 10, 'delivery_days', m_delivery_days FROM flags
    UNION ALL SELECT rid, 11, 'notes', m_notes FROM flags
)

SELECT a.column_name AS column_a, b.column_name AS column_b,
       COUNT(*) AS co_missing_rows
FROM cells AS a
JOIN cells AS b
  ON a.rid = b.rid
 AND a.c_ord < b.c_ord
 AND a.is_missing
 AND b.is_missing
GROUP BY a.column_name, b.column_name, a.c_ord, b.c_ord
ORDER BY co_missing_rows DESC, a.c_ord, b.c_ord;
