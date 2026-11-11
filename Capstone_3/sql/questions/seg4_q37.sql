-- Q37: Every-month vs one-month customers
-- TODAY is not read here; months come from the data itself.

WITH parsed_orders AS (
    SELECT
        TRIM(customer_id) AS cust_id,
        CASE
            WHEN order_date ~ '^\d{4}-\d{2}-\d{2}$'
                THEN
                    SUBSTRING(order_date, 1, 7)
            WHEN order_date ~ '^\d{2}/\d{2}/\d{4}$'
                THEN
                    SUBSTRING(order_date, 7, 4)
                    || '-'
                    || SUBSTRING(order_date, 1, 2)
            WHEN order_date ~ '^\d{2}-\w{3}-\d{2}$'
                THEN
                    '20'
                    || SUBSTRING(order_date, 8, 2)
                    || '-'
                    || CASE SUBSTRING(order_date, 4, 3)
                        WHEN 'Jan' THEN '01'
                        WHEN 'Feb' THEN '02'
                        WHEN 'Mar' THEN '03'
                        WHEN 'Apr' THEN '04'
                        WHEN 'May' THEN '05'
                        WHEN 'Jun' THEN '06'
                        WHEN 'Jul' THEN '07'
                        WHEN 'Aug' THEN '08'
                        WHEN 'Sep' THEN '09'
                        WHEN 'Oct' THEN '10'
                        WHEN 'Nov' THEN '11'
                        WHEN 'Dec' THEN '12'
                    END
            WHEN order_date ~ '^\d{2}\.\d{2}\.\d{4}$'
                THEN
                    SUBSTRING(order_date, 7, 4)
                    || '-'
                    || SUBSTRING(order_date, 4, 2)
        END AS ym
    FROM orders
    WHERE
        TRIM(customer_id) <> ''
        AND order_date <> ''
),

months AS (
    SELECT DISTINCT ym
    FROM parsed_orders
    WHERE ym IS NOT NULL
),

cust_months AS (
    SELECT
        cust_id,
        COUNT(DISTINCT ym) AS month_count,
        ARRAY_AGG(DISTINCT ym ORDER BY ym) AS months_list
    FROM parsed_orders
    WHERE ym IS NOT NULL
    GROUP BY cust_id
),

every_month AS (
    SELECT cust_months.cust_id
    FROM cust_months
    WHERE cust_months.month_count = (SELECT COUNT(*) FROM months)
),

one_month AS (
    SELECT cust_months.cust_id
    FROM cust_months
    WHERE cust_months.month_count = 1
),

norm_cust AS (
    SELECT
        customers.city,
        TRIM(customers.customer_id) AS cust_id,
        UPPER(
            REPLACE(REPLACE(TRIM(customers.customer_id), ' ', ''), '-', '')
        ) AS norm_id
    FROM customers
    WHERE TRIM(customers.customer_id) <> ''
),

ghost_cust AS (
    SELECT
        UPPER(
            REPLACE(REPLACE(TRIM(orders.customer_id), ' ', ''), '-', '')
        ) AS norm_id
    FROM orders
    WHERE
        UPPER(
            REPLACE(REPLACE(TRIM(orders.customer_id), ' ', ''), '-', '')
        ) NOT IN (SELECT ghost_norm.norm_id FROM norm_cust AS ghost_norm)
        AND TRIM(orders.customer_id) <> ''
    GROUP BY norm_id
)

SELECT
    (SELECT ARRAY_AGG(months.ym ORDER BY months.ym) FROM months) AS months,
    (SELECT COUNT(*) FROM months) AS n_months,
    (
        SELECT
            JSON_BUILD_OBJECT(
                'n',
                COUNT(*),
                'cities',
                JSON_OBJECT_AGG(city_counts.city, city_counts.cnt)
            )
        FROM (
            SELECT
                norm_cust.city,
                COUNT(*) AS cnt
            FROM every_month
            INNER JOIN norm_cust
                ON every_month.cust_id = norm_cust.cust_id
            GROUP BY norm_cust.city
        ) AS city_counts
    ) AS every_month,
    (
        SELECT
            JSON_BUILD_OBJECT(
                'n',
                COUNT(*),
                'cities',
                JSON_OBJECT_AGG(city_counts.city, city_counts.cnt)
            )
        FROM (
            SELECT
                norm_cust.city,
                COUNT(*) AS cnt
            FROM one_month
            INNER JOIN norm_cust
                ON one_month.cust_id = norm_cust.cust_id
            GROUP BY norm_cust.city
        ) AS city_counts
    ) AS one_month,
    (
        SELECT
            COUNT(
                DISTINCT UPPER(
                    REPLACE(
                        REPLACE(TRIM(ghost_orders.customer_id), ' ', ''),
                        '-',
                        ''
                    )
                )
            )
        FROM orders AS ghost_orders
        INNER JOIN one_month
            ON TRIM(ghost_orders.customer_id) = one_month.cust_id
        WHERE UPPER(
            REPLACE(
                REPLACE(TRIM(ghost_orders.customer_id), ' ', ''),
                '-',
                ''
            )
        ) IN (SELECT ghost_cust.norm_id FROM ghost_cust)
    ) AS one_month_unmatched;
