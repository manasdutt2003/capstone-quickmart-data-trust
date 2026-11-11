-- 04_trusted_orders.sql : legacy stage-count entry point.
-- The single trusted definition lives in 07_trusted_populations.sql
-- (v_trusted_lenient / v_trusted_strict / v_rejected_orders over the
-- 08 rule views). This file adds no rule logic; it only counts stages.
-- Completed = trusted rows whose status is Delivered (any case).
SELECT
    'trusted' AS stage_name,
    COUNT(*) AS n_rows
FROM v_trusted_lenient

UNION ALL

SELECT
    'strict' AS stage_name,
    COUNT(*) AS n_rows
FROM v_trusted_strict

UNION ALL

SELECT
    'rejected' AS stage_name,
    COUNT(*) AS n_rows
FROM v_rejected_orders

UNION ALL

SELECT
    'completed' AS stage_name,
    COUNT(*) AS n_rows
FROM v_trusted_lenient
WHERE UPPER(TRIM(order_status)) = 'DELIVERED';
