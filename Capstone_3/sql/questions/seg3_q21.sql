-- Q21: Which columns differ across duplicate copies
-- Requires: orders_loaded (staging).
-- For each of the 103 repeated order_ids, the number of distinct values is
-- counted per column (order_id + all 10 business columns, cleaned values);
-- a differing column would show a non-zero group count. Expected reading:
-- every count is 0 - the copies are byte-identical double-writes, and
-- keep-first removal never discards edited data (the D02 path stays
-- unexercised).

WITH grouped AS (
    SELECT
        TRIM(order_id) AS oid,
        COUNT(DISTINCT COALESCE(order_id, '')) AS d_order_id,
        COUNT(DISTINCT COALESCE(customer_id, '')) AS d_customer_id,
        COUNT(DISTINCT COALESCE(product_id, '')) AS d_product_id,
        COUNT(DISTINCT COALESCE(order_date, '')) AS d_order_date,
        COUNT(DISTINCT COALESCE(quantity, '')) AS d_quantity,
        COUNT(DISTINCT COALESCE(unit_price_paid, '')) AS d_unit_price_paid,
        COUNT(DISTINCT COALESCE(discount, '')) AS d_discount,
        COUNT(DISTINCT COALESCE(payment_mode, '')) AS d_payment_mode,
        COUNT(DISTINCT COALESCE(order_status, '')) AS d_order_status,
        COUNT(DISTINCT COALESCE(delivery_days, '')) AS d_delivery_days,
        COUNT(DISTINCT COALESCE(notes, '')) AS d_notes
    FROM orders_loaded
    GROUP BY TRIM(order_id)
    HAVING COUNT(*) > 1
)

SELECT column_name, differing_groups
FROM (
    SELECT 1 AS c_ord, 'order_id' AS column_name,
           COUNT(*) FILTER (WHERE d_order_id > 1) AS differing_groups
    FROM grouped
    UNION ALL
    SELECT 2, 'customer_id',
           COUNT(*) FILTER (WHERE d_customer_id > 1) FROM grouped
    UNION ALL
    SELECT 3, 'product_id',
           COUNT(*) FILTER (WHERE d_product_id > 1) FROM grouped
    UNION ALL
    SELECT 4, 'order_date',
           COUNT(*) FILTER (WHERE d_order_date > 1) FROM grouped
    UNION ALL
    SELECT 5, 'quantity',
           COUNT(*) FILTER (WHERE d_quantity > 1) FROM grouped
    UNION ALL
    SELECT 6, 'unit_price_paid',
           COUNT(*) FILTER (WHERE d_unit_price_paid > 1) FROM grouped
    UNION ALL
    SELECT 7, 'discount',
           COUNT(*) FILTER (WHERE d_discount > 1) FROM grouped
    UNION ALL
    SELECT 8, 'payment_mode',
           COUNT(*) FILTER (WHERE d_payment_mode > 1) FROM grouped
    UNION ALL
    SELECT 9, 'order_status',
           COUNT(*) FILTER (WHERE d_order_status > 1) FROM grouped
    UNION ALL
    SELECT 10, 'delivery_days',
           COUNT(*) FILTER (WHERE d_delivery_days > 1) FROM grouped
    UNION ALL
    SELECT 11, 'notes', COUNT(*) FILTER (WHERE d_notes > 1) FROM grouped
) AS t
ORDER BY c_ord;
