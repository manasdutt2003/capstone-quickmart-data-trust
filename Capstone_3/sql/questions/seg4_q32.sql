-- Q32: Ghost customer value (orders on unmatched customers)

WITH norm_cust AS (
    SELECT
        UPPER(
            REPLACE(REPLACE(TRIM(customer_id), ' ', ''), '-', '')
        ) AS norm_id
    FROM customers
    WHERE TRIM(customer_id) <> ''
),

ghost AS (
    SELECT o.*
    FROM orders AS o
    WHERE
        UPPER(REPLACE(REPLACE(TRIM(o.customer_id), ' ', ''), '-', '')) NOT IN (
            SELECT norm_cust.norm_id FROM norm_cust
        )
        AND TRIM(o.customer_id) <> ''
)

SELECT
    COUNT(DISTINCT TRIM(customer_id)) AS ghost_customers,
    COUNT(*) AS ghost_orders,
    ROUND(SUM(
        CASE
            WHEN
                TRIM(quantity) ~ '^\d+$'
                AND TRIM(unit_price_paid) ~ '^\d+(\.\d+)?$'
                THEN
                    CAST(quantity AS INT) * CAST(unit_price_paid AS NUMERIC)
                    * (1 - COALESCE(
                        CAST(NULLIF(REPLACE(discount, '%', ''), '') AS NUMERIC)
                        / CASE WHEN discount LIKE '%%' THEN 100 ELSE 1 END, 0
                    ))
            ELSE 0
        END
    ), 2) AS ghost_value
FROM ghost;
