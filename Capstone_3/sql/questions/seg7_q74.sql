-- Q74: Order status transition validation (honest analogue)
-- The extracts hold NO transition history: each order has a single
-- order_status snapshot and no timestamp column for status changes.
-- Per-order path reconstruction (Placed -> Pending -> ... ) is therefore
-- impossible. The analogue below classifies the single observed status
-- per order into terminal/non-terminal and reports the missing evidence.

WITH status_snapshot AS (
    SELECT
        TRIM(order_status) AS status,
        COUNT(*) AS orders
    FROM orders
    WHERE TRIM(order_id) <> ''
    GROUP BY TRIM(order_status)
),
classified AS (
    SELECT
        status,
        orders,
        CASE
            WHEN status IN ('Delivered', 'Cancelled', 'Returned') THEN 'terminal'
            WHEN status IN ('Pending', 'In Transit') THEN 'non_terminal'
            WHEN status = '' THEN 'missing'
            ELSE 'unknown_spelling'
        END AS state_class
    FROM status_snapshot
)
SELECT
    state_class,
    status,
    orders
FROM classified
ORDER BY state_class, status;

-- Missing evidence: order_status_log(order_id, status, transition_ts)
-- does not exist in the extracts, so skip/revisit patterns cannot be
-- observed. Enforcement recommendation (trigger on a future status-log
-- table + a transition-matrix reference table) is documented in
-- docs/answers_segment6_7.md Q74.

-- Enforcement at write time (preferred over detection):
-- 1. Trigger on order_status_log insert/update
-- 2. Check transition validity before commit
-- 3. Reject invalid transitions with clear error message
-- 4. Store valid transition matrix in a reference table for maintainability