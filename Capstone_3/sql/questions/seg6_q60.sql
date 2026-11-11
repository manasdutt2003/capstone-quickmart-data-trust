-- Q60: Deduplication step using ROW_NUMBER
-- Deterministic surviving row, test with shuffled input

WITH dedup_candidates AS (
    SELECT
        order_id,
        customer_id,
        product_id,
        order_date,
        quantity,
        unit_price_paid,
        discount,
        payment_mode,
        order_status,
        delivery_days,
        notes,
        ROW_NUMBER() OVER (
            PARTITION BY order_id, customer_id, product_id, order_date
            ORDER BY
                -- Priority: Delivered > other statuses
                CASE WHEN TRIM(order_status) ILIKE 'delivered' THEN 1 ELSE 2 END,
                -- Then by payment mode priority
                CASE TRIM(payment_mode)
                    WHEN 'UPI' THEN 1
                    WHEN 'Credit Card' THEN 2
                    WHEN 'Debit Card' THEN 3
                    WHEN 'NetBanking' THEN 4
                    WHEN 'COD' THEN 5
                    ELSE 6
                END,
                -- Then by earliest order_date (should be same)
                order_date,
                -- Then by order_id for determinism
                order_id
        ) AS rn
    FROM orders
    WHERE TRIM(order_id) <> ''
)
SELECT
    order_id,
    customer_id,
    product_id,
    order_date,
    quantity,
    unit_price_paid,
    discount,
    payment_mode,
    order_status,
    delivery_days,
    notes
FROM dedup_candidates
WHERE rn = 1
ORDER BY order_id;

-- Determinism test:
-- Run the query twice with input rows in different order (shuffled).
-- The output should be identical because:
-- 1. PARTITION BY defines the dedup groups
-- 2. ORDER BY defines priority (deterministic: status, payment, date, order_id)
-- 3. ROW_NUMBER picks exactly one row per group
-- 4. No non-deterministic functions used

-- What would cause outputs to differ:
-- 1. Non-deterministic ORDER BY (e.g., using RANDOM())
-- 2. Missing tiebreaker when priority columns are equal
-- 3. Floating-point comparisons in ORDER BY
-- 4. Different partitioning (e.g., missing columns in PARTITION BY)