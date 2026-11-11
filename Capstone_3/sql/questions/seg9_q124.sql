-- Q124: monthly share of lines >5% off catalogue; doubling flagged
-- Lines with no catalogue price excluded from the rate (counted in docs).

WITH priced AS (
    SELECT
        SUBSTRING(t.order_date, 1, 7) AS ym,
        t.category_std,
        CASE
            WHEN p.unit_price ~ '^\d+(\.\d+)?$'
                AND p.unit_price::numeric > 0
                AND t.unit_price_paid ~ '^\d+(\.\d+)?$'
                AND ABS(
                    t.unit_price_paid::numeric - p.unit_price::numeric
                ) / p.unit_price::numeric > 0.05
                THEN 1
            ELSE 0
        END AS off_price
    FROM trusted_enriched AS t
    JOIN products_clean AS p ON p.product_id = t.product_id
    WHERE
        t.status_std = 'Delivered'
        AND t.line_value IS NOT NULL
        AND p.unit_price ~ '^\d+(\.\d+)?$'
        AND p.unit_price::numeric > 0
        AND t.unit_price_paid ~ '^\d+(\.\d+)?$'
),
monthly AS (
    SELECT
        ym,
        category_std,
        AVG(off_price) * 100 AS share_pct,
        COUNT(*) AS n
    FROM priced
    GROUP BY ym, category_std
),
lagged AS (
    SELECT
        ym,
        category_std,
        share_pct,
        n,
        LAG(share_pct) OVER (
            PARTITION BY category_std ORDER BY ym
        ) AS prev_share
    FROM monthly
)
SELECT
    ym,
    category_std,
    ROUND(share_pct, 2) AS share_pct,
    n,
    (
        prev_share IS NOT NULL
        AND share_pct >= 2 * prev_share
    ) AS doubled
FROM lagged
ORDER BY category_std, ym;
