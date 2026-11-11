-- 03_dedup.sql : deterministic order-line dedup, frozen order
-- D01 (exact) -> D03 (customer id remap) -> D02 (order_id priority) ->
-- D05 (line key). Mirrors src/deduplication.py; the code remaps D03 ids
-- before D01 matching, and D02 keeps one survivor per order_id whenever a
-- status ranking is available. D06 never removes rows; near-duplicate
-- flags live in v_d06_review_flags. Tiebreaker everywhere is
-- CAST(source_row_number AS INTEGER). Only staging columns are read.

-- D06 is flag-only: same name on two ids is review evidence, not a merge.
CREATE OR REPLACE VIEW v_d06_review_flags AS
SELECT
    'same name, different id (review only)' AS evidence,
    TRIM(a.customer_id) AS customer_a,
    TRIM(b.customer_id) AS customer_b,
    TRIM(a.customer_name) AS shared_name
FROM customers_master AS a
INNER JOIN customers_master AS b
    ON
        TRIM(a.customer_name) = TRIM(b.customer_name)
        AND TRIM(a.customer_id) < TRIM(b.customer_id)
WHERE NULLIF(TRIM(a.customer_name), '') IS NOT NULL;

WITH cust_ranked AS (
    SELECT
        TRIM(customer_id) AS cid,
        LOWER(TRIM(email)) AS norm_email,
        ROW_NUMBER() OVER (
            PARTITION BY LOWER(TRIM(email))
            ORDER BY signup_date, TRIM(customer_id)
        ) AS rn
    FROM customers_master
    WHERE
        NULLIF(TRIM(email), '') IS NOT NULL
        AND UPPER(TRIM(email)) NOT IN (
            'NA', 'N/A', 'NULL', 'NONE', 'UNKNOWN', '?', '-', '--'
        )
),

survivor AS (
    SELECT
        norm_email,
        cid AS survivor_cid
    FROM cust_ranked
    WHERE rn = 1
),

remap AS (
    SELECT
        r.cid AS loser_cid,
        s.survivor_cid
    FROM cust_ranked AS r
    INNER JOIN survivor AS s
        ON r.norm_email = s.norm_email
    WHERE r.rn > 1
),

d01base AS (
    SELECT
        o.order_id,
        o.product_id,
        o.order_date,
        o.quantity,
        o.unit_price_paid,
        o.discount,
        o.payment_mode,
        o.order_status,
        o.delivery_days,
        o.notes,
        o.raw_order_id,
        o.raw_customer_id,
        o.raw_product_id,
        o.raw_order_date,
        o.raw_quantity,
        o.raw_unit_price_paid,
        o.raw_discount,
        o.raw_payment_mode,
        o.raw_order_status,
        o.raw_delivery_days,
        o.raw_notes,
        o._source_row,
        o.source_file,
        o.source_row_number,
        o.dedup_rule_applied,
        o.rules_passed,
        o.rules_failed,
        COALESCE(m.survivor_cid, TRIM(o.customer_id)) AS customer_id
    FROM orders_clean AS o
    LEFT JOIN remap AS m
        ON TRIM(o.customer_id) = m.loser_cid
),

d01 AS (
    SELECT
        b.*,
        ROW_NUMBER() OVER (
            PARTITION BY
                b.customer_id,
                b.product_id,
                b.order_date,
                b.quantity,
                b.unit_price_paid,
                b.discount,
                b.payment_mode,
                b.order_status,
                b.delivery_days,
                b.notes
            ORDER BY CAST(b.source_row_number AS INTEGER) ASC
        ) AS rn1
    FROM d01base AS b
),

d01kept AS (
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
        raw_order_id,
        raw_customer_id,
        raw_product_id,
        raw_order_date,
        raw_quantity,
        raw_unit_price_paid,
        raw_discount,
        raw_payment_mode,
        raw_order_status,
        raw_delivery_days,
        raw_notes,
        _source_row,
        source_file,
        source_row_number,
        dedup_rule_applied,
        rules_passed,
        rules_failed
    FROM d01
    WHERE rn1 = 1
),

d02 AS (
    SELECT
        d.*,
        ROW_NUMBER() OVER (
            PARTITION BY d.order_id
            ORDER BY
                CASE UPPER(TRIM(d.order_status))
                    WHEN 'DELIVERED' THEN 0
                    WHEN 'IN TRANSIT' THEN 1
                    WHEN 'PENDING' THEN 2
                    WHEN 'RETURNED' THEN 3
                    WHEN 'CANCELLED' THEN 4
                    WHEN 'MISSING' THEN 5
                    WHEN 'UNMAPPED' THEN 6
                    ELSE 9
                END ASC,
                (
                    CASE
                        WHEN d.order_status <> '' THEN 1
                        ELSE 0
                    END
                    + CASE
                        WHEN d.payment_mode <> '' THEN 1
                        ELSE 0
                    END
                ) DESC,
                d.order_status ASC,
                d.payment_mode ASC,
                CAST(d.source_row_number AS INTEGER) ASC
        ) AS rn2
    FROM d01kept AS d
),

d02kept AS (
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
        raw_order_id,
        raw_customer_id,
        raw_product_id,
        raw_order_date,
        raw_quantity,
        raw_unit_price_paid,
        raw_discount,
        raw_payment_mode,
        raw_order_status,
        raw_delivery_days,
        raw_notes,
        _source_row,
        source_file,
        source_row_number,
        dedup_rule_applied,
        rules_passed,
        rules_failed
    FROM d02
    WHERE rn2 = 1
),

d05 AS (
    SELECT
        d.*,
        ROW_NUMBER() OVER (
            PARTITION BY
                UPPER(TRIM(d.customer_id)),
                UPPER(TRIM(d.product_id)),
                TRIM(d.order_date),
                TRIM(d.quantity),
                TRIM(d.unit_price_paid)
            ORDER BY CAST(d.source_row_number AS INTEGER) ASC
        ) AS rn5
    FROM d02kept AS d
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
    notes,
    raw_order_id,
    raw_customer_id,
    raw_product_id,
    raw_order_date,
    raw_quantity,
    raw_unit_price_paid,
    raw_discount,
    raw_payment_mode,
    raw_order_status,
    raw_delivery_days,
    raw_notes,
    _source_row,
    source_file,
    source_row_number,
    dedup_rule_applied,
    rules_passed,
    rules_failed
FROM d05
WHERE rn5 = 1;
