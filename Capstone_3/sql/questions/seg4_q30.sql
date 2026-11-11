-- Q30: Customer match rules and counts
-- Rules considered: (a) exact stripped match, (b) normalised match
-- (trim, UPPER, strip spaces/dashes)
-- Adopted: (b) - case/dash variants are entry noise; rescues orders
-- without inventing customers

WITH norm_cust AS (
    SELECT
        customer_id,
        UPPER(REPLACE(REPLACE(TRIM(customer_id), ' ', ''), '-', '')) AS norm_id
    FROM customers
    WHERE TRIM(customer_id) <> ''
),

norm_orders AS (
    SELECT
        order_id,
        customer_id,
        UPPER(REPLACE(REPLACE(TRIM(customer_id), ' ', ''), '-', '')) AS norm_id
    FROM orders
)

SELECT
    COUNT(*) FILTER (WHERE o.customer_id = c.customer_id) AS exact_matched,
    COUNT(*) FILTER (
        WHERE o.norm_id = c.norm_id AND o.customer_id <> c.customer_id
    ) AS rescued_by_normalisation,
    COUNT(*) FILTER (
        WHERE o.norm_id NOT IN (SELECT norm_cust.norm_id FROM norm_cust)
    )
        AS unmatched
FROM norm_orders AS o
LEFT JOIN norm_cust AS c ON o.norm_id = c.norm_id;

-- Top unmatched value
WITH norm_cust AS (
    SELECT
        UPPER(
            REPLACE(REPLACE(TRIM(customer_id), ' ', ''), '-', '')
        ) AS norm_id
    FROM customers
    WHERE TRIM(customer_id) <> ''
),

unmatched AS (
    SELECT TRIM(customer_id) AS cust_id
    FROM orders
    WHERE
        UPPER(REPLACE(REPLACE(TRIM(customer_id), ' ', ''), '-', '')) NOT IN (
            SELECT norm_cust.norm_id FROM norm_cust
        )
        AND TRIM(customer_id) <> ''
)

SELECT
    cust_id,
    COUNT(*) AS cnt
FROM unmatched
GROUP BY cust_id
ORDER BY cnt DESC
LIMIT 1;
