-- Q56: Three-month moving average of completed sales per category
-- Direction changes in moving average

WITH monthly_category AS (
    SELECT
        order_month,
        category_std,
        SUM(line_value) AS monthly_value
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
    GROUP BY order_month, category_std
),
moving_avg AS (
    SELECT
        order_month,
        category_std,
        monthly_value,
        AVG(monthly_value) OVER (
            PARTITION BY category_std
            ORDER BY order_month
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ) AS ma_3m
    FROM monthly_category
),
with_prev AS (
    SELECT
        order_month,
        category_std,
        monthly_value,
        ma_3m,
        LAG(ma_3m) OVER (
            PARTITION BY category_std ORDER BY order_month
        ) AS prev_ma_3m
    FROM moving_avg
),
direction AS (
    SELECT
        order_month,
        category_std,
        monthly_value,
        ROUND(ma_3m, 2) AS ma_3m,
        CASE
            WHEN prev_ma_3m IS NULL THEN 'START'
            WHEN ma_3m > prev_ma_3m THEN 'UP'
            WHEN ma_3m < prev_ma_3m THEN 'DOWN'
            ELSE 'FLAT'
        END AS direction,
        LAG(CASE
            WHEN prev_ma_3m IS NULL THEN 'START'
            WHEN ma_3m > prev_ma_3m THEN 'UP'
            WHEN ma_3m < prev_ma_3m THEN 'DOWN'
            ELSE 'FLAT'
        END) OVER (PARTITION BY category_std ORDER BY order_month) AS prev_direction
    FROM with_prev
)
SELECT
    order_month,
    category_std,
    ma_3m,
    direction,
    CASE
        WHEN prev_direction IS NULL OR prev_direction = 'START' THEN 'N/A'
        WHEN direction <> prev_direction AND direction NOT IN ('START', 'FLAT') AND prev_direction NOT IN ('START', 'FLAT')
        THEN 'DIRECTION_CHANGE'
        ELSE 'CONTINUE'
    END AS change_flag
FROM direction
WHERE direction IN ('UP', 'DOWN')
ORDER BY category_std, order_month;

-- Months with no sales in a category:
-- The window frame ROWS BETWEEN 2 PRECEDING AND CURRENT ROW treats missing months as non-existent
-- (they don't contribute to the average). This means a gap in data compresses the window.
-- Alternative: Use RANGE with date casting to include zero-value months explicitly.
-- The ROWS approach is simpler but may smooth over gaps; RANGE is more accurate for calendar time.