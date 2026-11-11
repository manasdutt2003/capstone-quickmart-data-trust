-- Q112: top-5 product pairs same customer+date (canonical order)
-- product_a < product_b counts each unordered pair once (else double).

WITH lines AS (
    SELECT DISTINCT customer_id, order_date, product_id
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
)
SELECT a.product_id AS product_id_a, b.product_id AS product_id_b,
    COUNT(*) AS n
FROM lines AS a
JOIN lines AS b
    ON a.customer_id = b.customer_id
    AND a.order_date = b.order_date
    AND a.product_id < b.product_id
GROUP BY a.product_id, b.product_id
ORDER BY n DESC, product_id_a, product_id_b
LIMIT 5;
