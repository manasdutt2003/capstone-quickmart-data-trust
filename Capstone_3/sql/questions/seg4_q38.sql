-- Q38: Orders before signup
-- TODAY is read from v_run_params (single SQL home of the reference date).

WITH parsed_signups AS (
    SELECT
        TRIM(customer_id) AS cust_id,
        CASE
            WHEN signup_date ~ '^\d{4}-\d{2}-\d{2}$' THEN signup_date
            WHEN
                signup_date ~ '^\d{2}/\d{2}/\d{4}$'
                THEN
                    SUBSTR(signup_date, 7, 4)
                    || '-'
                    || SUBSTR(signup_date, 1, 2)
                    || '-'
                    || SUBSTR(signup_date, 4, 2)
            WHEN signup_date ~ '^\d{2}-\w{3}-\d{2}$'
                THEN
                    '20' || SUBSTR(signup_date, 8, 2) || '-'
                    || CASE SUBSTR(signup_date, 4, 3)
                        WHEN 'Jan' THEN '01' WHEN 'Feb' THEN '02' WHEN
                            'Mar'
                            THEN '03'
                        WHEN 'Apr' THEN '04' WHEN 'May' THEN '05' WHEN
                            'Jun'
                            THEN '06'
                        WHEN 'Jul' THEN '07' WHEN 'Aug' THEN '08' WHEN
                            'Sep'
                            THEN '09'
                        WHEN 'Oct' THEN '10' WHEN 'Nov' THEN '11' WHEN
                            'Dec'
                            THEN '12'
                    END || '-' || SUBSTR(signup_date, 1, 2)
            WHEN
                signup_date ~ '^\d{2}\.\d{2}\.\d{4}$'
                THEN
                    SUBSTR(signup_date, 7, 4)
                    || '-'
                    || SUBSTR(signup_date, 4, 2)
                    || '-'
                    || SUBSTR(signup_date, 1, 2)
        END AS signup_dt
    FROM customers
    WHERE TRIM(customer_id) <> '' AND signup_date <> ''
),

parsed_orders AS (
    SELECT
        TRIM(customer_id) AS cust_id,
        CASE
            WHEN order_date ~ '^\d{4}-\d{2}-\d{2}$' THEN order_date
            WHEN
                order_date ~ '^\d{2}/\d{2}/\d{4}$'
                THEN
                    SUBSTR(order_date, 7, 4)
                    || '-'
                    || SUBSTR(order_date, 1, 2)
                    || '-'
                    || SUBSTR(order_date, 4, 2)
            WHEN order_date ~ '^\d{2}-\w{3}-\d{2}$'
                THEN
                    '20' || SUBSTR(order_date, 8, 2) || '-'
                    || CASE SUBSTR(order_date, 4, 3)
                        WHEN 'Jan' THEN '01' WHEN 'Feb' THEN '02' WHEN
                            'Mar'
                            THEN '03'
                        WHEN 'Apr' THEN '04' WHEN 'May' THEN '05' WHEN
                            'Jun'
                            THEN '06'
                        WHEN 'Jul' THEN '07' WHEN 'Aug' THEN '08' WHEN
                            'Sep'
                            THEN '09'
                        WHEN 'Oct' THEN '10' WHEN 'Nov' THEN '11' WHEN
                            'Dec'
                            THEN '12'
                    END || '-' || SUBSTR(order_date, 1, 2)
            WHEN
                order_date ~ '^\d{2}\.\d{2}\.\d{4}$'
                THEN
                    SUBSTR(order_date, 7, 4)
                    || '-'
                    || SUBSTR(order_date, 4, 2)
                    || '-'
                    || SUBSTR(order_date, 1, 2)
        END AS order_dt
    FROM orders
    WHERE TRIM(customer_id) <> '' AND order_date <> ''
),

bad_orders AS (
    SELECT
        o.cust_id,
        o.order_dt,
        s.signup_dt
    FROM parsed_orders AS o
    INNER JOIN parsed_signups AS s ON o.cust_id = s.cust_id
    WHERE o.order_dt < s.signup_dt
)

SELECT
    (SELECT COUNT(*) FROM bad_orders) AS orders,
    (SELECT COUNT(DISTINCT cust_id) FROM bad_orders) AS customers,
    (
        SELECT COUNT(*) FROM parsed_signups
        WHERE signup_dt > (SELECT v.today::TEXT FROM v_run_params AS v))
        AS future_signups_in_master,
    (
        SELECT COUNT(*) FROM parsed_orders
        WHERE order_dt > (SELECT v.today::TEXT FROM v_run_params AS v)
    ) AS future_orders;
