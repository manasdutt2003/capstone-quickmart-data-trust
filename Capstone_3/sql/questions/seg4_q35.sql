-- Q35: Price closeness (R06 tolerance = 10%)

WITH cat AS (
    SELECT
        CAST(unit_price AS NUMERIC) AS cat_price,
        TRIM(product_id) AS prod_id
    FROM products
    WHERE
        TRIM(product_id) <> ''
        AND unit_price ~ '^\d+(\.\d+)?$'
        AND CAST(unit_price AS NUMERIC) > 0
),

paid AS (
    SELECT
        p.prod_id,
        p.net_paid,
        c.cat_price,
        CASE
            WHEN
                ABS(p.net_paid - c.cat_price) / c.cat_price <= 0.10
                THEN 'within_tolerance'
            ELSE 'outside_tolerance'
        END AS detail
    FROM (
        SELECT
            TRIM(product_id) AS prod_id,
            CAST(unit_price_paid AS NUMERIC)
            * (1 - COALESCE(
                CAST(NULLIF(REPLACE(discount, '%', ''), '') AS NUMERIC)
                / CASE WHEN discount LIKE '%%' THEN 100 ELSE 1 END, 0
            )) AS net_paid
        FROM orders
        WHERE
            TRIM(product_id) <> ''
            AND unit_price_paid ~ '^\d+(\.\d+)?$'
            AND CAST(unit_price_paid AS NUMERIC) >= 0
            AND (discount = '' OR discount ~ '^(\d+(\.\d+)?%?|\d*\.\d+)$')
    ) AS p
    INNER JOIN cat AS c ON p.prod_id = c.prod_id
)

SELECT
    detail,
    COUNT(*) AS n
FROM paid
GROUP BY detail

UNION ALL

SELECT
    'non_positive_price' AS detail,
    COUNT(*) AS n
FROM orders
WHERE
    TRIM(unit_price_paid) = ''
    OR unit_price_paid !~ '^\d+(\.\d+)?$'
    OR CAST(unit_price_paid AS NUMERIC) <= 0

UNION ALL

SELECT
    'unverifiable:no_catalogue_price' AS detail,
    COUNT(*) AS n
FROM orders AS o
WHERE
    TRIM(o.product_id) <> ''
    AND NOT EXISTS (
        SELECT 1 FROM cat AS c
        WHERE c.prod_id = TRIM(o.product_id)
    );
