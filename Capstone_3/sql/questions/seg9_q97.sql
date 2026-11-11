-- Q97: monthly value per category + 3M moving average + YoY
-- Self-join on month minus 12; first 12 months show NULL YoY, never 0.

WITH monthly AS (
    SELECT
        category_std,
        order_month,
        SUM(line_value) AS value
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
    GROUP BY category_std, order_month
),
with_ma AS (
    SELECT
        category_std,
        order_month,
        value,
        AVG(value) OVER (
            PARTITION BY category_std
            ORDER BY order_month
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ) AS ma_3m
    FROM monthly
)
SELECT
    m.category_std,
    m.order_month,
    ROUND(m.value, 2) AS value,
    ROUND(m.ma_3m, 2) AS ma_3m,
    ROUND(y.value, 2) AS yoy_value
FROM with_ma AS m
LEFT JOIN monthly AS y
    ON y.category_std = m.category_std
    AND y.order_month = (
        (SUBSTRING(m.order_month, 1, 4)::int - 1)::text
        || SUBSTRING(m.order_month, 5, 3)
    )
ORDER BY m.category_std, m.order_month;
