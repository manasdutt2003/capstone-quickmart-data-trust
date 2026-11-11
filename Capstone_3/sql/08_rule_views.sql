-- 08_rule_views.sql : SQL twins of the Python rule bodies R01, R03, R06.
-- Each view returns (source_row_number, result, failing_detail) with the
-- same strings as src/validation_rules, for parity tests. All casts sit
-- behind regex guards (staging is TEXT-only, see 00_staging.sql); cleaned
-- inputs are already ISO dates and canonical numbers, so guards only
-- route empties to the same branches as the Python None paths.
-- Normalisation mirrors normalise.norm_id (trim, UPPER, strip spaces and
-- dashes; SQL TRIM removes spaces, matching space-only real data).
-- R06 ships at both tolerances: v_r06_valid_price (10%, canonical) and
-- v_r06_valid_price_tol05 (5%, alternative).

CREATE OR REPLACE VIEW v_r01_customer_exists AS
WITH master AS (
    SELECT DISTINCT TRIM(customer_id) AS cid
    FROM customers_master
    WHERE NULLIF(TRIM(customer_id), '') IS NOT NULL
),

master_norm AS (
    SELECT
        REPLACE(
            REPLACE(UPPER(TRIM(customer_id)), ' ', ''),
            '-',
            ''
        ) AS ncid
    FROM customers_master
    WHERE NULLIF(TRIM(customer_id), '') IS NOT NULL
    GROUP BY 1
)

SELECT
    CASE
        WHEN o.source_row_number ~ '^\d+$'
            THEN CAST(o.source_row_number AS INTEGER)
    END AS source_row_number,
    CASE
        WHEN me.cid IS NOT NULL THEN 'PASS'
        WHEN mn.ncid IS NOT NULL THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    CASE
        WHEN me.cid IS NOT NULL THEN 'matched_exact'
        WHEN mn.ncid IS NOT NULL THEN 'matched_normalised'
        ELSE 'unmatched_after_normalisation'
    END AS failing_detail
FROM orders_clean AS o
LEFT JOIN master AS me
    ON me.cid = TRIM(o.customer_id)
LEFT JOIN master_norm AS mn
    ON mn.ncid = REPLACE(REPLACE(UPPER(TRIM(o.customer_id)), ' ', ''), '-', '');

CREATE OR REPLACE VIEW v_r03_signup_before_order AS
WITH ranked AS (
    SELECT
        signup_date,
        TRIM(customer_id) AS cid,
        ROW_NUMBER() OVER (
            PARTITION BY TRIM(customer_id)
            ORDER BY
                CASE
                    WHEN
                        signup_date
                        ~ '^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'
                        THEN signup_date
                    ELSE '9999-12-31'
                END
        ) AS rn
    FROM customers_master
    WHERE NULLIF(TRIM(customer_id), '') IS NOT NULL
),

master AS (
    SELECT
        cid,
        signup_date
    FROM ranked
    WHERE rn = 1
),

master_norm AS (
    SELECT
        ncid,
        signup_date
    FROM (
        SELECT
            signup_date,
            REPLACE(REPLACE(UPPER(TRIM(customer_id)), ' ', ''), '-', '')
                AS ncid,
            ROW_NUMBER() OVER (
                PARTITION BY
                    REPLACE(REPLACE(UPPER(TRIM(customer_id)), ' ', ''), '-', '')
                ORDER BY
                    CASE
                        WHEN
                            signup_date
                            ~ '^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'
                            THEN signup_date
                        ELSE '9999-12-31'
                    END
            ) AS rn
        FROM customers_master
        WHERE NULLIF(TRIM(customer_id), '') IS NOT NULL
    ) AS t
    WHERE rn = 1
)

SELECT
    CASE
        WHEN o.source_row_number ~ '^\d+$'
            THEN CAST(o.source_row_number AS INTEGER)
    END AS source_row_number,
    CASE
        WHEN me.cid IS NULL AND mn.ncid IS NULL THEN 'PASS'
        WHEN
            o.order_date IS NULL
            OR o.order_date
            !~ '^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'
            THEN 'FAIL'
        WHEN
            COALESCE(me.signup_date, mn.signup_date) IS NULL
            OR COALESCE(me.signup_date, mn.signup_date)
            !~ '^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'
            THEN 'FAIL'
        WHEN COALESCE(me.signup_date, mn.signup_date) <= o.order_date
            THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    CASE
        WHEN me.cid IS NULL AND mn.ncid IS NULL THEN 'skipped_due_to_R01'
        WHEN
            o.order_date IS NULL
            OR o.order_date
            !~ '^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'
            THEN 'unparseable_order_date'
        WHEN
            COALESCE(me.signup_date, mn.signup_date) IS NULL
            OR COALESCE(me.signup_date, mn.signup_date)
            !~ '^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'
            THEN 'unparseable_signup_date'
        WHEN COALESCE(me.signup_date, mn.signup_date) <= o.order_date
            THEN 'signup_ok'
        ELSE 'order_before_signup'
    END AS failing_detail
FROM orders_clean AS o
LEFT JOIN master AS me
    ON me.cid = TRIM(o.customer_id)
LEFT JOIN master_norm AS mn
    ON mn.ncid = REPLACE(REPLACE(UPPER(TRIM(o.customer_id)), ' ', ''), '-', '');

CREATE OR REPLACE VIEW v_r06_valid_price AS
WITH c AS (
    SELECT
        pid,
        price
    FROM (
        SELECT
            CAST(unit_price AS NUMERIC) AS price,
            TRIM(product_id) AS pid,
            ROW_NUMBER() OVER (
                PARTITION BY TRIM(product_id)
                ORDER BY CAST(_source_row AS INTEGER)
            ) AS rn
        FROM products_clean
        WHERE
            NULLIF(TRIM(product_id), '') IS NOT NULL
            AND unit_price ~ '^[+-]?(\d+\.?\d*|\.\d+)$'
            AND CAST(unit_price AS NUMERIC) > 0
    ) AS t
    WHERE rn = 1
)

SELECT
    CASE
        WHEN o.source_row_number ~ '^\d+$'
            THEN CAST(o.source_row_number AS INTEGER)
    END AS source_row_number,
    CASE
        WHEN
            o.unit_price_paid IS NULL
            OR TRIM(o.unit_price_paid)
            !~ '^[+-]?(\d+\.?\d*|\.\d+)$'
            OR CAST(TRIM(o.unit_price_paid) AS NUMERIC) <= 0
            THEN 'FAIL'
        WHEN c.pid IS NULL THEN 'WARNING'
        WHEN
            ABS(
                CAST(TRIM(o.unit_price_paid) AS NUMERIC)
                * (1 - CASE
                    WHEN NULLIF(TRIM(o.discount), '') IS NULL THEN 0
                    WHEN TRIM(o.discount) ~ '^[+-]?(\d+\.?\d*|\.\d+)$'
                        THEN CAST(TRIM(o.discount) AS NUMERIC)
                    ELSE 0
                END)
                - c.price
            ) / c.price <= 0.100000001
            THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    CASE
        WHEN
            o.unit_price_paid IS NULL
            OR TRIM(o.unit_price_paid)
            !~ '^[+-]?(\d+\.?\d*|\.\d+)$'
            OR CAST(TRIM(o.unit_price_paid) AS NUMERIC) <= 0
            THEN 'non_positive_price'
        WHEN c.pid IS NULL THEN 'unverifiable:no_catalogue_price'
        WHEN
            ABS(
                CAST(TRIM(o.unit_price_paid) AS NUMERIC)
                * (1 - CASE
                    WHEN NULLIF(TRIM(o.discount), '') IS NULL THEN 0
                    WHEN TRIM(o.discount) ~ '^[+-]?(\d+\.?\d*|\.\d+)$'
                        THEN CAST(TRIM(o.discount) AS NUMERIC)
                    ELSE 0
                END)
                - c.price
            ) / c.price <= 0.100000001
            THEN 'within_tolerance'
        ELSE 'outside_tolerance'
    END AS failing_detail
FROM orders_clean AS o
LEFT JOIN c
    ON c.pid = TRIM(o.product_id);

CREATE OR REPLACE VIEW v_r06_valid_price_tol05 AS
WITH c AS (
    SELECT
        pid,
        price
    FROM (
        SELECT
            CAST(unit_price AS NUMERIC) AS price,
            TRIM(product_id) AS pid,
            ROW_NUMBER() OVER (
                PARTITION BY TRIM(product_id)
                ORDER BY CAST(_source_row AS INTEGER)
            ) AS rn
        FROM products_clean
        WHERE
            NULLIF(TRIM(product_id), '') IS NOT NULL
            AND unit_price ~ '^[+-]?(\d+\.?\d*|\.\d+)$'
            AND CAST(unit_price AS NUMERIC) > 0
    ) AS t
    WHERE rn = 1
)

SELECT
    CASE
        WHEN o.source_row_number ~ '^\d+$'
            THEN CAST(o.source_row_number AS INTEGER)
    END AS source_row_number,
    CASE
        WHEN
            o.unit_price_paid IS NULL
            OR TRIM(o.unit_price_paid)
            !~ '^[+-]?(\d+\.?\d*|\.\d+)$'
            OR CAST(TRIM(o.unit_price_paid) AS NUMERIC) <= 0
            THEN 'FAIL'
        WHEN c.pid IS NULL THEN 'WARNING'
        WHEN
            ABS(
                CAST(TRIM(o.unit_price_paid) AS NUMERIC)
                * (1 - CASE
                    WHEN NULLIF(TRIM(o.discount), '') IS NULL THEN 0
                    WHEN TRIM(o.discount) ~ '^[+-]?(\d+\.?\d*|\.\d+)$'
                        THEN CAST(TRIM(o.discount) AS NUMERIC)
                    ELSE 0
                END)
                - c.price
            ) / c.price <= 0.050000001
            THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    CASE
        WHEN
            o.unit_price_paid IS NULL
            OR TRIM(o.unit_price_paid)
            !~ '^[+-]?(\d+\.?\d*|\.\d+)$'
            OR CAST(TRIM(o.unit_price_paid) AS NUMERIC) <= 0
            THEN 'non_positive_price'
        WHEN c.pid IS NULL THEN 'unverifiable:no_catalogue_price'
        WHEN
            ABS(
                CAST(TRIM(o.unit_price_paid) AS NUMERIC)
                * (1 - CASE
                    WHEN NULLIF(TRIM(o.discount), '') IS NULL THEN 0
                    WHEN TRIM(o.discount) ~ '^[+-]?(\d+\.?\d*|\.\d+)$'
                        THEN CAST(TRIM(o.discount) AS NUMERIC)
                    ELSE 0
                END)
                - c.price
            ) / c.price <= 0.050000001
            THEN 'within_tolerance'
        ELSE 'outside_tolerance'
    END AS failing_detail
FROM orders_clean AS o
LEFT JOIN c
    ON c.pid = TRIM(o.product_id);
