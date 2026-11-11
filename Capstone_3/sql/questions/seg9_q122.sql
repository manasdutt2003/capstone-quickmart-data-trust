-- Q122: products rank-1 in monthly qty within category, >=3 months
-- DENSE_RANK ties share rank 1, so tied months add every tied product.

WITH monthly AS (
    SELECT
        category_std,
        SUBSTRING(order_date, 1, 7) AS ym,
        product_id,
        SUM(
            CASE
                WHEN quantity ~ '^\d+$' THEN quantity::int
                ELSE 0
            END
        ) AS qty
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
        AND order_date ~ '^\d{4}-\d{2}-\d{2}$'
    GROUP BY category_std, SUBSTRING(order_date, 1, 7), product_id
),
ranked AS (
    SELECT
        product_id,
        DENSE_RANK() OVER (
            PARTITION BY category_std, ym ORDER BY qty DESC
        ) AS rnk
    FROM monthly
)
SELECT product_id, COUNT(*) AS months_at_1
FROM ranked
WHERE rnk = 1
GROUP BY product_id
HAVING COUNT(*) >= 3
ORDER BY months_at_1 DESC, product_id;
