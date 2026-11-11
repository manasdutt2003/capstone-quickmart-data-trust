-- Q39: Join losses at each stage

SELECT
    'orders-customers (exact)' AS "join",
    (SELECT COUNT(*) FROM orders) AS n_before,
    COUNT(*) AS kept,
    (SELECT COUNT(*) FROM orders) - COUNT(*) AS dropped
FROM orders AS o
INNER JOIN customers AS c
    ON TRIM(o.customer_id) = TRIM(c.customer_id)

UNION ALL

SELECT
    'orders-customers (normalised)' AS "join",
    (SELECT COUNT(*) FROM orders) AS n_before,
    COUNT(*) AS kept,
    (SELECT COUNT(*) FROM orders) - COUNT(*) AS dropped
FROM orders AS o
INNER JOIN customers AS c
    ON
        UPPER(REPLACE(REPLACE(TRIM(o.customer_id), ' ', ''), '-', ''))
        = UPPER(REPLACE(REPLACE(TRIM(c.customer_id), ' ', ''), '-', ''))

UNION ALL

SELECT
    'orders-products (exact)' AS "join",
    (SELECT COUNT(*) FROM orders) AS n_before,
    COUNT(*) AS kept,
    (SELECT COUNT(*) FROM orders) - COUNT(*) AS dropped
FROM orders AS o
INNER JOIN products AS p
    ON TRIM(o.product_id) = TRIM(p.product_id)

UNION ALL

SELECT
    'orders-products (normalised)' AS "join",
    (SELECT COUNT(*) FROM orders) AS n_before,
    COUNT(*) AS kept,
    (SELECT COUNT(*) FROM orders) - COUNT(*) AS dropped
FROM orders AS o
INNER JOIN products AS p
    ON
        UPPER(REPLACE(REPLACE(TRIM(o.product_id), ' ', ''), '-', ''))
        = UPPER(REPLACE(REPLACE(TRIM(p.product_id), ' ', ''), '-', ''))

UNION ALL

SELECT
    'orders-city attribution' AS "join",
    (SELECT COUNT(*) FROM orders) AS n_before,
    COUNT(*) AS kept,
    (SELECT COUNT(*) FROM orders) - COUNT(*) AS dropped
FROM orders AS o
INNER JOIN customers AS c
    ON
        UPPER(REPLACE(REPLACE(TRIM(o.customer_id), ' ', ''), '-', ''))
        = UPPER(REPLACE(REPLACE(TRIM(c.customer_id), ' ', ''), '-', ''))
WHERE TRIM(c.city) <> '';
