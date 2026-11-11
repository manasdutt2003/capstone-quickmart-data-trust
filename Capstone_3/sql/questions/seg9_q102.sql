-- Q102: customers reaching a 10th trusted order earliest (tie: id)
-- ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING counts earlier rows;
-- the 10th order has earlier_n = 9. Empty (nobody reaches 10) is correct.

WITH sequenced AS (
    SELECT
        customer_id,
        order_id,
        order_date,
        COUNT(*) OVER (
            PARTITION BY customer_id
            ORDER BY order_date, order_id COLLATE "C"
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS earlier_n
    FROM trusted_enriched
    WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
)
SELECT customer_id, order_date, order_id
FROM sequenced
WHERE earlier_n = 9
ORDER BY order_date, customer_id, order_id;
