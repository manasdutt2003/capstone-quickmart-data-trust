-- 07_trusted_populations.sql : trusted population views over v_line_value.
-- Prerequisite tables (loaded from pipeline outputs): orders_clean (with
-- source_row_number) and rule_failure_log (source_row_number, rule_id,
-- result). Grain: one row per order line; strict excludes any FAIL or
-- WARNING, lenient excludes only FAIL. Rerun-safe (pure views).
CREATE OR REPLACE VIEW v_trusted_lenient AS
SELECT
    o.order_id,
    o.customer_id,
    o.product_id,
    o.order_date,
    o.quantity,
    o.unit_price_paid,
    o.discount,
    o.payment_mode,
    o.order_status,
    o.delivery_days,
    o.notes,
    v.line_value
FROM orders_clean AS o
INNER JOIN v_line_value AS v
    ON o.order_id = v.order_id
WHERE NOT EXISTS (
    SELECT 1
    FROM rule_failure_log AS r
    WHERE
        o.source_row_number = r.source_row_number
        AND r.result = 'FAIL'
);

CREATE OR REPLACE VIEW v_trusted_strict AS
SELECT
    o.order_id,
    o.customer_id,
    o.product_id,
    o.order_date,
    o.quantity,
    o.unit_price_paid,
    o.discount,
    o.payment_mode,
    o.order_status,
    o.delivery_days,
    o.notes,
    v.line_value
FROM orders_clean AS o
INNER JOIN v_line_value AS v
    ON o.order_id = v.order_id
WHERE NOT EXISTS (
    SELECT 1
    FROM rule_failure_log AS r
    WHERE
        o.source_row_number = r.source_row_number
        AND r.result IN ('FAIL', 'WARNING')
);

CREATE OR REPLACE VIEW v_rejected_orders AS
SELECT
    o.order_id,
    o.customer_id,
    o.product_id,
    o.order_date,
    o.quantity,
    o.unit_price_paid,
    o.discount,
    o.payment_mode,
    o.order_status,
    o.delivery_days,
    o.notes,
    v.line_value
FROM orders_clean AS o
INNER JOIN v_line_value AS v
    ON o.order_id = v.order_id
WHERE EXISTS (
    SELECT 1
    FROM rule_failure_log AS r
    WHERE
        o.source_row_number = r.source_row_number
        AND r.result = 'FAIL'
);

-- trusted_enriched mirrors src/datamarts.enrich over the recommended
-- (lenient) population for 05_marts.sql and 06_segment6_9_answers.sql.
-- Mapping tables city_map, category_map, status_map, pay_map hold
-- (raw_value, standard_value) loaded from mappings/proposed/*.csv.
-- Lookup is exact-on-trimmed-text, falling back to the empty-key row
-- then to UNMAPPED (mirrors normalise.standardise); customers or
-- products with no master row give UNKNOWN (mirrors the merge fillna).
CREATE OR REPLACE VIEW trusted_enriched AS
SELECT
    t.order_id,
    t.customer_id,
    t.product_id,
    t.order_date,
    t.quantity,
    t.unit_price_paid,
    t.discount,
    t.payment_mode,
    t.order_status,
    t.delivery_days,
    t.notes,
    t.line_value,
    CASE
        WHEN cm.customer_id IS NULL THEN 'UNKNOWN'
        ELSE COALESCE(
            (
                SELECT m.standard_value
                FROM city_map AS m
                WHERE m.raw_value = TRIM(cm.city)
            ),
            (
                SELECT m.standard_value
                FROM city_map AS m
                WHERE m.raw_value = ''
            ),
            'UNMAPPED'
        )
    END AS city_std,
    CASE
        WHEN p.product_id IS NULL THEN 'UNKNOWN'
        ELSE COALESCE(
            (
                SELECT m.standard_value
                FROM category_map AS m
                WHERE m.raw_value = TRIM(p.category)
            ),
            (
                SELECT m.standard_value
                FROM category_map AS m
                WHERE m.raw_value = ''
            ),
            'UNMAPPED'
        )
    END AS category_std,
    COALESCE(
        (
            SELECT m.standard_value
            FROM status_map AS m
            WHERE m.raw_value = TRIM(t.order_status)
        ),
        (
            SELECT m.standard_value
            FROM status_map AS m
            WHERE m.raw_value = ''
        ),
        'UNMAPPED'
    ) AS status_std,
    COALESCE(
        (
            SELECT m.standard_value
            FROM pay_map AS m
            WHERE m.raw_value = TRIM(t.payment_mode)
        ),
        (
            SELECT m.standard_value
            FROM pay_map AS m
            WHERE m.raw_value = ''
        ),
        'UNMAPPED'
    ) AS payment_std,
    CASE
        WHEN t.order_date ~ '^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'
            THEN SUBSTRING(t.order_date, 1, 7)
        ELSE 'INVALID'
    END AS order_month
FROM v_trusted_lenient AS t
LEFT JOIN customers_master AS cm
    ON TRIM(t.customer_id) = TRIM(cm.customer_id)
LEFT JOIN products_clean AS p
    ON TRIM(t.product_id) = TRIM(p.product_id);
