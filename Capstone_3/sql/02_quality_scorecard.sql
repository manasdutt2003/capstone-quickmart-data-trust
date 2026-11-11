-- 02_quality_scorecard.sql : reproducible 0-100 scorecard view.
-- Weights: completeness 30, uniqueness 25, referential 25, conformance 20.
-- (Weights live here and in docs/rule_catalog.md; quality_inputs below
-- only aggregates v_column_profile plus id/FK checks.)
-- Gaming warning: a team can inflate the score (1) by mapping blanks to a
-- dummy standard value (raises completeness without fixing data) or (2) by
-- dropping quarantined rows before profiling. Mitigation: profile RAW
-- staging tables, never cleaned subsets, and keep this file unedited.
CREATE OR REPLACE VIEW quality_inputs AS
WITH cells AS (
    SELECT
        tbl,
        SUM(n_rows) AS cells,
        SUM(n_missing) AS missing,
        SUM(n_usable) AS usable,
        SUM(n_unusable) AS unusable
    FROM v_column_profile
    GROUP BY tbl
),

unq AS (
    SELECT
        'customers_master' AS tbl,
        COUNT(*) AS rows_,
        COUNT(
            DISTINCT NULLIF(TRIM(customer_id), '')
        ) AS ids
    FROM customers_master

    UNION ALL

    SELECT
        'products_clean' AS tbl,
        COUNT(*) AS rows_,
        COUNT(
            DISTINCT NULLIF(TRIM(product_id), '')
        ) AS ids
    FROM products_clean

    UNION ALL

    SELECT
        'orders_clean' AS tbl,
        COUNT(*) AS rows_,
        COUNT(
            DISTINCT NULLIF(TRIM(order_id), '')
        ) AS ids
    FROM orders_clean
),

fk AS (
    SELECT
        COUNT(*) AS rows_,
        SUM(
            CASE
                WHEN c.customer_id IS NULL THEN 0
                WHEN p.product_id IS NULL THEN 0
                ELSE 1
            END
        ) AS ok
    FROM orders_clean AS o
    LEFT JOIN customers_master AS c
        ON TRIM(o.customer_id) = TRIM(c.customer_id)
    LEFT JOIN products_clean AS p
        ON TRIM(o.product_id) = TRIM(p.product_id)
)

SELECT
    cells.tbl,
    ROUND(
        100.0 * (cells.cells - cells.missing) / cells.cells, 2
    ) AS completeness,
    ROUND(
        100.0 * unq.ids / unq.rows_, 2
    ) AS uniqueness,
    CASE
        WHEN cells.tbl = 'orders_clean'
            THEN ROUND(100.0 * fk.ok / fk.rows_, 2)
        ELSE 100.00
    END AS referential_integrity,
    COALESCE(
        ROUND(
            100.0 * cells.usable
            / NULLIF(cells.usable + cells.unusable, 0),
            2
        ),
        100.00
    ) AS conformance
FROM cells
INNER JOIN unq
    ON cells.tbl = unq.tbl
CROSS JOIN fk;

CREATE OR REPLACE VIEW v_quality_scorecard AS
SELECT
    tbl,
    (
        0.30 * completeness
        + 0.25 * uniqueness
        + 0.25 * referential_integrity
        + 0.20 * conformance
    )::numeric(5, 2) AS score_0_100
FROM quality_inputs;
