-- Q48: Outside served cities

WITH served AS (
    SELECT UNNEST(ARRAY['Bengaluru', 'Chennai', 'Hyderabad', 'Pune']) AS city
),

cust_city AS (
    SELECT
        TRIM(customer_id) AS cust_id,
        TRIM(city) AS city
    FROM customers
),

order_cities AS (
    SELECT
        TRIM(o.customer_id) AS cust_id,
        COALESCE(c.city, 'UNMATCHED') AS city
    FROM orders AS o
    LEFT JOIN cust_city AS c ON TRIM(o.customer_id) = c.cust_id
),

outside AS (
    SELECT order_cities.city
    FROM order_cities
    WHERE order_cities.city NOT IN (SELECT served.city FROM served)
)

SELECT
    ARRAY['Bengaluru', 'Chennai', 'Hyderabad', 'Pune'] AS served,
    (
        SELECT ARRAY_AGG(d.city ORDER BY d.city)
        FROM (SELECT DISTINCT outside.city FROM outside) AS d
    ) AS outside_values,
    (SELECT COUNT(*) FROM outside) AS outside_orders,
    ROUND(SUM(
        CASE
            WHEN
                TRIM(o.quantity) ~ '^\d+$'
                AND TRIM(o.unit_price_paid) ~ '^\d+(\.\d+)?$'
                THEN
                    CAST(o.quantity AS INT)
                    * CAST(o.unit_price_paid AS NUMERIC)
                    * (1 - COALESCE(
                        CAST(
                            NULLIF(REPLACE(o.discount, '%', ''), '')
                            AS NUMERIC
                        )
                        / CASE
                            WHEN o.discount LIKE '%%' THEN 100
                            ELSE 1
                        END,
                        0
                    ))
            ELSE 0
        END
    ), 2) AS outside_value,
    (
        SELECT COUNT(DISTINCT TRIM(customers.customer_id))
        FROM customers
        WHERE
            TRIM(customers.city) NOT IN (SELECT served.city FROM served)
            AND TRIM(customers.city) <> ''
    ) AS outside_customers
FROM orders AS o
WHERE EXISTS (
    SELECT 1
    FROM order_cities AS oc
    WHERE
        TRIM(o.customer_id) = oc.cust_id
        AND oc.city NOT IN (SELECT served.city FROM served)
);
