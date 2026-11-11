-- Q34: Catalogue vs paid price gap per product

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
),

median_paid AS (
    SELECT
        prod_id,
        CAST(
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY net_paid)
            AS NUMERIC
        ) AS median_net
    FROM paid
    GROUP BY prod_id
)

SELECT
    m.prod_id AS product_id,
    c.cat_price AS catalogue_price,
    ROUND(m.median_net, 2) AS median_net_paid,
    ROUND(m.median_net - c.cat_price, 2) AS gap_amount,
    ROUND((m.median_net - c.cat_price) / c.cat_price * 100, 1) AS gap_pct,
    COALESCE(
        CAST(
            ABS(
                SUM(
                    CASE
                        WHEN p.net_paid - c.cat_price >= 0 THEN 1
                        ELSE -1
                    END
                )
            ) AS NUMERIC
        )
        / COUNT(*)
        >= 0.8
        AND ABS(ROUND((m.median_net - c.cat_price) / c.cat_price * 100, 1))
        > 10, FALSE
    ) AS systematic
FROM median_paid AS m
INNER JOIN cat AS c ON m.prod_id = c.prod_id
INNER JOIN paid AS p ON m.prod_id = p.prod_id
GROUP BY m.prod_id, c.cat_price, m.median_net
ORDER BY m.prod_id;
