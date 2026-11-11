-- Q88: products above their own median monthly qty in every active month
-- Median per product via window percentile_cont; global median would differ.

WITH monthly AS (
    SELECT
        product_id,
        SUBSTRING(order_date, 1, 7) AS ym,
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
    GROUP BY product_id, SUBSTRING(order_date, 1, 7)
),
with_med AS (
    SELECT
        product_id,
        ym,
        qty
    FROM monthly
),
medians AS (
    SELECT
        product_id,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY qty) AS med_qty
    FROM monthly
    GROUP BY product_id
),
joined AS (
    SELECT m.product_id, m.ym, m.qty, d.med_qty
    FROM monthly AS m
    JOIN medians AS d ON m.product_id = d.product_id
)
SELECT
    product_id,
    ROUND(MAX(med_qty)::numeric, 2) AS median_monthly_qty,
    (MIN(qty) > MAX(med_qty)) AS all_months_above
FROM joined
GROUP BY product_id
ORDER BY product_id;
