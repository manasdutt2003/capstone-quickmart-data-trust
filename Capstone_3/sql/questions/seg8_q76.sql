-- Q76: LATERAL latest-payment vs window/DISTINCT ON under ties
-- Counterexample on a tied pair: DISTINCT ON (ORDER BY payment_mode)
-- and ROW_NUMBER (same ordering) agree deterministically; a LATERAL
-- LIMIT 1 with no ORDER BY is arbitrary. Equivalent iff ordering is total.

WITH tied (order_id, order_date, payment_mode) AS (
    VALUES
        ('O-TIE', '2024-01-01', 'UPI'),
        ('O-TIE', '2024-01-01', 'COD')
),
distinct_pick AS (
    SELECT DISTINCT ON (order_id)
        order_id,
        payment_mode AS distinct_on_pick
    FROM tied
    ORDER BY order_id, payment_mode COLLATE "C"
),
window_pick AS (
    SELECT order_id, payment_mode AS window_pick
    FROM (
        SELECT
            order_id,
            payment_mode,
            ROW_NUMBER() OVER (
                PARTITION BY order_id
                ORDER BY payment_mode COLLATE "C"
            ) AS rn
        FROM tied
    ) ranked
    WHERE rn = 1
)
SELECT
    'counterexample: two rows tie on (order_id, order_date)' AS finding,
    distinct_on_pick,
    window_pick,
    (distinct_on_pick = window_pick) AS agree_with_tiebreak,
    'LATERAL ... LIMIT 1 with no ORDER BY is arbitrary on ties - add ORDER BY payment_mode to make all three equivalent' AS rule
FROM distinct_pick
CROSS JOIN window_pick;
