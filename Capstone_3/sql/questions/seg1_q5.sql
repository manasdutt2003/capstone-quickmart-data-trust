-- Q5: Leading zeros and variant spellings in ids
-- Requires: customers_loaded, orders_loaded (staging).
-- Counts rows carrying each variant class, rows that norm_id (strip, UPPER,
-- remove spaces/dashes) would rewrite, and distinct spellings vs distinct
-- norm ids - so canonicalisation is lossless (500 = 500, 693 -> 482) and
-- leading zeros in order_id are never integerised.

WITH cust AS (
    SELECT
        customer_id,
        COALESCE(raw_customer_id, '') AS raw_customer_id,
        UPPER(REPLACE(REPLACE(TRIM(COALESCE(raw_customer_id, '')), ' ', ''),
                      '-', '')) AS norm_id,
        UPPER(REPLACE(REPLACE(TRIM(customer_id), ' ', ''), '-', ''))
            AS clean_norm_id
    FROM customers_loaded
),

orders_norm AS (
    SELECT
        order_id,
        COALESCE(raw_customer_id, '') AS raw_customer_id,
        COALESCE(raw_product_id, '') AS raw_product_id,
        UPPER(REPLACE(REPLACE(TRIM(COALESCE(raw_customer_id, '')), ' ', ''),
                      '-', '')) AS cust_norm_id,
        UPPER(REPLACE(REPLACE(TRIM(COALESCE(raw_product_id, '')), ' ', ''),
                      '-', '')) AS prod_norm_id
    FROM orders_loaded
)

SELECT scope, column_name, variant, row_count
FROM (
    SELECT 1 AS sort_key, 'customers' AS scope,
           'raw_customer_id' AS column_name, 'trailing space' AS variant,
           COUNT(*) AS row_count
    FROM cust
    WHERE raw_customer_id <> TRIM(raw_customer_id)
    UNION ALL
    SELECT 2, 'customers', 'raw_customer_id', 'lower case', COUNT(*)
    FROM cust
    WHERE raw_customer_id <> UPPER(raw_customer_id)
    UNION ALL
    SELECT 3, 'customers', 'raw_customer_id', 'contains dash', COUNT(*)
    FROM cust
    WHERE raw_customer_id LIKE '%-%'
    UNION ALL
    SELECT 4, 'customers', 'raw_customer_id', 'rewritten by norm_id',
           COUNT(*)
    FROM cust
    WHERE norm_id <> raw_customer_id
    UNION ALL
    SELECT 5, 'customers', 'customer_id', 'rewritten by norm_id', COUNT(*)
    FROM cust
    WHERE clean_norm_id <> customer_id
    UNION ALL
    SELECT 6, 'customers', 'raw_customer_id', 'distinct spellings',
           COUNT(DISTINCT raw_customer_id)
    FROM cust
    UNION ALL
    SELECT 7, 'customers', 'raw_customer_id', 'distinct ids after norm_id',
           COUNT(DISTINCT norm_id)
    FROM cust
    UNION ALL
    SELECT 8, 'orders', 'raw_customer_id', 'trailing space', COUNT(*)
    FROM orders_norm
    WHERE raw_customer_id <> TRIM(raw_customer_id)
    UNION ALL
    SELECT 9, 'orders', 'raw_customer_id', 'lower case', COUNT(*)
    FROM orders_norm
    WHERE raw_customer_id <> UPPER(raw_customer_id)
    UNION ALL
    SELECT 10, 'orders', 'raw_customer_id', 'contains dash', COUNT(*)
    FROM orders_norm
    WHERE raw_customer_id LIKE '%-%'
    UNION ALL
    SELECT 11, 'orders', 'raw_customer_id', 'rewritten by norm_id', COUNT(*)
    FROM orders_norm
    WHERE cust_norm_id <> raw_customer_id
    UNION ALL
    SELECT 12, 'orders', 'raw_customer_id', 'distinct spellings',
           COUNT(DISTINCT raw_customer_id)
    FROM orders_norm
    UNION ALL
    SELECT 13, 'orders', 'raw_customer_id', 'distinct ids after norm_id',
           COUNT(DISTINCT cust_norm_id)
    FROM orders_norm
    UNION ALL
    SELECT 14, 'orders', 'raw_product_id', 'single-dash form (P-21)',
           COUNT(*)
    FROM orders_norm
    WHERE raw_product_id ~ '^P-\d{1,3}$'
    UNION ALL
    SELECT 15, 'orders', 'raw_product_id', 'doubled-dash form (P--10)',
           COUNT(*)
    FROM orders_norm
    WHERE raw_product_id ~ '^P--\d{1,3}$'
    UNION ALL
    SELECT 16, 'orders', 'raw_product_id', 'lower case', COUNT(*)
    FROM orders_norm
    WHERE raw_product_id <> UPPER(raw_product_id)
    UNION ALL
    SELECT 17, 'orders', 'raw_product_id', 'rewritten by norm_id', COUNT(*)
    FROM orders_norm
    WHERE prod_norm_id <> raw_product_id
    UNION ALL
    SELECT 18, 'orders', 'order_id', 'variant rows (space/case/dash)',
           COUNT(*)
    FROM orders_norm
    WHERE order_id <> TRIM(order_id)
       OR order_id <> UPPER(order_id)
       OR order_id LIKE '%-%'
    UNION ALL
    SELECT 19, 'orders', 'order_id', 'leading-zero form O0####', COUNT(*)
    FROM orders_norm
    WHERE order_id ~ '^O0\d{3,4}$'
) AS variants
ORDER BY sort_key;
