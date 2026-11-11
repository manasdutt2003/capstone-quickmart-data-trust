-- Q47: Delivery extremes by status

WITH delivery_class AS (
    SELECT
        TRIM(order_status) AS order_status,
        TRIM(delivery_days) AS delivery_days,
        CASE
            WHEN TRIM(order_status) ILIKE 'delivered'
                THEN
                    CASE
                        WHEN
                            TRIM(delivery_days) = ''
                            THEN 'missing_delivery_days'
                        WHEN
                            TRIM(delivery_days) ~ '^-\d+'
                            THEN 'negative_delivery_days'
                        WHEN
                            CAST(delivery_days AS INT) > 30
                            THEN 'above_upper_bound_30'
                        ELSE 'ok'
                    END
            WHEN TRIM(order_status) ILIKE 'cancelled'
                THEN
                    CASE
                        WHEN
                            TRIM(delivery_days) = ''
                            OR TRIM(delivery_days) = '0'
                            THEN 'ok'
                        WHEN
                            TRIM(delivery_days) ~ '^\d+'
                            THEN 'cancelled_with_delivery_days'
                        ELSE 'no_delivery_rule_for_status'
                    END
            ELSE 'no_delivery_rule_for_status'
        END AS detail
    FROM orders
)

SELECT
    order_status || '|' || detail AS by_status_detail,
    COUNT(*) AS n
FROM delivery_class
GROUP BY order_status, detail
ORDER BY order_status, detail;
