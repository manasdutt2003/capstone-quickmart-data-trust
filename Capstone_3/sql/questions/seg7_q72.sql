-- Q72: Rules evaluation via LATERAL join
-- Each order gets concatenated violated rule names (deterministic order)

-- The live rules table on this database is rule_failure_log
-- (source_row_number, rule_id, result, failing_detail), loaded from
-- outputs/rule_failure_log.csv. One row per order per evaluated rule.

SELECT
    o.order_id,
    COALESCE(r.violated_rules, '') AS violated_rules
FROM trusted_enriched o
JOIN orders_clean oc ON oc.order_id = o.order_id
LEFT JOIN LATERAL (
    SELECT STRING_AGG(r.rule_id, ',' ORDER BY r.rule_id) AS violated_rules
    FROM rule_failure_log r
    WHERE r.source_row_number = oc.source_row_number
) r ON TRUE
WHERE o.status_std = 'Delivered'
ORDER BY o.order_id;

-- Deterministic output:
-- 1. STRING_AGG with ORDER BY rule_id ensures consistent ordering
-- 2. LATERAL processes each order independently (no cartesian with other orders)
-- 3. rule_failure_log is static during query execution

-- Avoiding cartesian explosion:
-- 1. LATERAL processes one order at a time, evaluating rules against that order only
-- 2. Join key is source_row_number (one order's rows only)
-- 3. If a rule had multiple applicable conditions, they are pre-combined
--    into a single failing_detail per rule per order upstream

-- Determinism guarantee:
-- - Same rule_failure_log + same orders = same violated_rules string
-- - ORDER BY rule_id in STRING_AGG
-- - No non-deterministic functions in predicates