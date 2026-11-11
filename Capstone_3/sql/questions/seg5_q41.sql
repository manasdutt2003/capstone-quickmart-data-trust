-- Q41: Status spellings

SELECT
    TRIM(order_status) AS raw_value,
    COUNT(*) AS count
FROM orders
GROUP BY TRIM(order_status)
ORDER BY count DESC;
