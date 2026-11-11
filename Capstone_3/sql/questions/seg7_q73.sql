-- Q73: Browse-to-purchase-to-delivery funnel
-- Conditional aggregation + window function, 14-day window

-- Note: The extracts do not contain browse events (page views, product views).
-- This query uses order events as proxy:
-- Stage 1: Order placed (any status)
-- Stage 2: Order confirmed (status in 'Pending', 'In Transit', 'Delivered')
-- Stage 3: Delivered (status = 'Delivered')
-- Each stage must occur within 14 days of previous.

WITH customer_stages AS (
    SELECT
        customer_id,
        MIN(CASE WHEN order_status IS NOT NULL THEN order_date END) AS stage1_order_placed,
        MIN(CASE WHEN order_status IN ('Pending', 'In Transit', 'Delivered') THEN order_date END) AS stage2_confirmed,
        MIN(CASE WHEN order_status = 'Delivered' THEN order_date END) AS stage3_delivered
    FROM orders
    WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
    GROUP BY customer_id
),
funnel AS (
    SELECT
        customer_id,
        stage1_order_placed,
        stage2_confirmed,
        stage3_delivered,
        CASE WHEN stage1_order_placed IS NOT NULL THEN 1 ELSE 0 END AS reached_stage1,
        CASE WHEN stage2_confirmed IS NOT NULL AND stage2_confirmed::date <= stage1_order_placed::date + INTERVAL '14 days' THEN 1 ELSE 0 END AS reached_stage2,
        CASE WHEN stage3_delivered IS NOT NULL AND stage3_delivered::date <= COALESCE(stage2_confirmed, stage1_order_placed)::date + INTERVAL '14 days' THEN 1 ELSE 0 END AS reached_stage3
    FROM customer_stages
)
SELECT
    'Stage 1: Order Placed' AS stage, SUM(reached_stage1) AS count
FROM funnel
UNION ALL
SELECT
    'Stage 2: Confirmed (within 14d)', SUM(reached_stage2)
FROM funnel
UNION ALL
SELECT
    'Stage 3: Delivered (within 14d of prev)', SUM(reached_stage3)
FROM funnel
UNION ALL
SELECT
    'Lost at Stage 2', SUM(reached_stage1) - SUM(reached_stage2)
FROM funnel
UNION ALL
SELECT
    'Lost at Stage 3', SUM(reached_stage2) - SUM(reached_stage3)
FROM funnel;

-- Missing earlier stage handling:
-- If a customer has stage3 but no stage1 (impossible in real data, but possible if data missing),
-- the 14-day window from stage1 would be NULL, so stage2/stage3 would not count.
-- This is correct: you can't confirm an order that was never placed.

-- Largest share lost:
-- Compare 'Lost at Stage 2' vs 'Lost at Stage 3'.
-- The larger number indicates the bottleneck stage.