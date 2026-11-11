-- Q23: Case/spacing/dash customer id variants
-- Requires: customers_loaded, orders_loaded (staging).
-- norm_id = strip + upper + remove spaces/dashes, applied per row and
-- before/after distinct counts are compared (same definition as
-- src/normalise.py::norm_id and count_before_after_normalising, on the
-- cleaned customer id; order side uses the raw extract spellings).
-- Expected reading: 23 customer rows change form (19 lower-case ids +
-- 4 dashed ids) with distinct ids 500 before and after - no customer is
-- double-counted by spelling; order-side 693 spellings collapse to 482.

SELECT scope, measure, row_count
FROM (
    SELECT 'customers' AS scope,
           'rows changed by normalisation' AS measure,
           COUNT(*) FILTER (
               WHERE TRIM(customer_id)
                     <> regexp_replace(UPPER(TRIM(customer_id)),
                                       '[\s-]+', '', 'g')
                  OR customer_id <> TRIM(customer_id)
           ) AS row_count,
           1 AS scope_ord, 1 AS sort_key
    FROM customers_loaded
    UNION ALL
    SELECT 'customers', 'distinct ids before',
           COUNT(DISTINCT COALESCE(customer_id, '')), 1, 2
    FROM customers_loaded
    UNION ALL
    SELECT 'customers', 'distinct ids after',
           COUNT(DISTINCT regexp_replace(
               UPPER(TRIM(COALESCE(customer_id, ''))), '[\s-]+', '', 'g')),
           1, 3
    FROM customers_loaded
    UNION ALL
    SELECT 'orders', 'distinct raw id spellings',
           COUNT(DISTINCT COALESCE(raw_customer_id, '')), 2, 1
    FROM orders_loaded
    UNION ALL
    SELECT 'orders', 'distinct normalised ids',
           COUNT(DISTINCT regexp_replace(
               UPPER(TRIM(COALESCE(raw_customer_id, ''))),
               '[\s-]+', '', 'g')), 2, 2
    FROM orders_loaded
) AS t
ORDER BY scope_ord, sort_key;
