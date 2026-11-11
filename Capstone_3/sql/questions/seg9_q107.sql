-- Q107: first month a product's count exceeds its own average
-- Average over the product's own active months; flat sellers never exceed.

WITH monthly AS (
    SELECT
        product_id,
        SUBSTRING(order_date, 1, 7) AS ym,
        COUNT(*) AS n
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
        AND order_date ~ '^\d{4}-\d{2}-\d{2}$'
    GROUP BY product_id, SUBSTRING(order_date, 1, 7)
),
with_avg AS (
    SELECT
        product_id,
        ym,
        n,
        AVG(n) OVER (PARTITION BY product_id) AS avg_n
    FROM monthly
)
SELECT
    product_id,
    MIN(CASE WHEN n > avg_n THEN ym ELSE NULL END)
        AS first_above_month,
    (MIN(CASE WHEN n > avg_n THEN ym ELSE NULL END) IS NULL) AS never
FROM with_avg
GROUP BY product_id
ORDER BY product_id;
