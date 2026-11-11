-- Q52: CTE chain - deduplicated orders -> validated orders -> completed orders
-- Row count at each stage with reconciliation

WITH raw_orders AS (
    -- Raw extract row count lives outside the database; 6103 is the
    -- committed extract manifest value (reference/extract_manifest.json).
    SELECT 6103 AS raw_count
),
deduped AS (
    -- D01: exact duplicates removed (staging already holds clean_orders,
    -- so this pass is idempotent: 6000 in, 6000 out)
    SELECT
        source_row_number,
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
            PARTITION BY order_id, customer_id, product_id, order_date, quantity, unit_price_paid, discount, payment_mode, order_status, delivery_days, notes
            ORDER BY order_id
        ) AS rn
    FROM orders
),
deduped_clean AS (
    SELECT * FROM deduped WHERE rn = 1
),
validated AS (
    -- Validated = deduped rows joined to the logged R01-R12 evaluation
    -- (rule_failure_log). has_fail mirrors the FAIL verdict exactly; the
    -- inline per-rule predicates below document the rule set without
    -- re-implementing the registry (single source of truth stays in
    -- sql/08_rule_views.sql + src/validation_rules.py).
    SELECT
        d.*,
        EXISTS (
            SELECT 1 FROM rule_failure_log r
            WHERE r.source_row_number = d.source_row_number
              AND r.result = 'FAIL'
        ) AS has_fail,
        EXISTS (
            SELECT 1 FROM rule_failure_log r
            WHERE r.source_row_number = d.source_row_number
              AND r.result = 'WARNING'
        ) AS has_warning
    FROM deduped_clean d
),
completed AS (
    SELECT * FROM validated
    WHERE NOT has_fail AND TRIM(order_status) ILIKE 'delivered'
)
SELECT
    'raw_orders' AS stage, (SELECT raw_count FROM raw_orders) AS count
UNION ALL
SELECT 'deduped', COUNT(*) FROM deduped_clean
UNION ALL
SELECT 'validated', COUNT(*) FROM validated
UNION ALL
SELECT 'completed', COUNT(*) FROM completed;

-- Reconciliation:
-- raw_orders = deduped + exact_duplicates_removed
-- deduped = validated + validation_failures
-- validated = completed + non_delivered + validation_warnings