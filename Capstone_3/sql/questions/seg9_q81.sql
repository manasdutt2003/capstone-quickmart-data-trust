-- Q81: share of category completed value from the top NTILE(10) bucket
-- NTILE assigns by row position, so tied values split across bucket edges.

WITH product_values AS (
    SELECT
        category_std,
        product_id,
        SUM(line_value) AS value
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
    GROUP BY category_std, product_id
),
bucketed AS (
    SELECT
        category_std,
        value,
        NTILE(10) OVER (
            PARTITION BY category_std
            ORDER BY value DESC, product_id COLLATE "C"
        ) AS bucket
    FROM product_values
),
totals AS (
    SELECT
        category_std,
        COUNT(*) AS n_products,
        SUM(value) AS total_value,
        SUM(CASE WHEN bucket = 1 THEN value ELSE 0 END) AS top_value
    FROM bucketed
    GROUP BY category_std
)
SELECT
    category_std,
    n_products,
    ROUND(top_value, 2) AS top_bucket_value,
    ROUND(top_value / total_value * 100, 2) AS top_share_pct
FROM totals
ORDER BY category_std;
