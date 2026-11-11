-- Q68: Sessionise order events per customer with 30-minute inactivity gap
-- Window functions only, no procedural loop

WITH ordered_events AS (
    SELECT
        customer_id,
        order_id,
        order_date::timestamp AS event_ts,
        LAG(order_date::timestamp) OVER (
            PARTITION BY customer_id
            ORDER BY order_date::timestamp, order_id COLLATE "C"
        ) AS prev_ts
    FROM trusted_enriched
    WHERE status_std = 'Delivered'
),
session_boundaries AS (
    SELECT
        customer_id,
        event_ts,
        CASE
            WHEN prev_ts IS NULL THEN 1
            WHEN event_ts - prev_ts > INTERVAL '30 minutes' THEN 1
            ELSE 0
        END AS new_session
    FROM ordered_events
),
session_ids AS (
    SELECT
        customer_id,
        event_ts,
        SUM(new_session) OVER (
            PARTITION BY customer_id
            ORDER BY event_ts
            ROWS UNBOUNDED PRECEDING
        ) AS session_id
    FROM session_boundaries
),
session_stats AS (
    SELECT
        customer_id,
        session_id,
        MIN(event_ts) AS session_start,
        MAX(event_ts) AS session_end,
        COUNT(*) AS event_count,
        EXTRACT(EPOCH FROM (MAX(event_ts) - MIN(event_ts))) / 60 AS session_length_min
    FROM session_ids
    GROUP BY customer_id, session_id
)
SELECT
    COUNT(*) AS total_sessions,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY session_length_min) AS median_session_length_min,
    COUNT(*) FILTER (WHERE event_count > 10) AS sessions_over_10_events
FROM session_stats;

-- Identical timestamps handling:
-- ORDER BY event_ts, order_id ensures deterministic ordering even with identical timestamps.
-- If two events have exactly the same timestamp, order_id breaks the tie.
-- This means they are in the same session (0 gap) unless the 30-min gap is exceeded from previous event.

-- Why row-by-row procedural approach fails:
-- 1. Cannot handle concurrent sessions across multiple customers efficiently
-- 2. Requires maintaining session state in variables (not set-based)
-- 3. Much slower for large datasets (iterative vs set-based)
-- 4. Harder to parallelize and optimize
-- 5. Identical timestamps require explicit tie-breaking logic that's easier in ORDER BY