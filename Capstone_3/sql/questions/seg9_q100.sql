-- Q100: two different same-category products, same customer+date
-- Canonical ordering (a < b) counts each pair once. Empty (no such pair
-- in completed orders) is the correct answer; basket-vs-duplicate evidence
-- in docs/answers_segment8_9.md.

WITH lines AS (
    SELECT DISTINCT customer_id, order_date, category_std, product_id,
        quantity
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
)
SELECT
    a.customer_id,
    a.order_date,
    a.category_std,
    a.product_id AS product_id_a,
    b.product_id AS product_id_b,
    a.quantity AS quantity_a,
    b.quantity AS quantity_b
FROM lines AS a
JOIN lines AS b
    ON a.customer_id = b.customer_id
    AND a.order_date = b.order_date
    AND a.category_std = b.category_std
    AND a.product_id < b.product_id
ORDER BY a.customer_id, a.order_date, product_id_a, product_id_b;
