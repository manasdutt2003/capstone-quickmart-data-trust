-- Q33: Products never ordered

WITH norm_ord_prod AS (
    SELECT DISTINCT
        UPPER(
            REPLACE(REPLACE(TRIM(product_id), ' ', ''), '-', '')
        ) AS norm_id
    FROM orders
    WHERE TRIM(product_id) <> ''
),

norm_prod AS (
    SELECT
        product_id,
        unit_price,
        stock_qty,
        UPPER(REPLACE(REPLACE(TRIM(product_id), ' ', ''), '-', '')) AS norm_id
    FROM products
    WHERE TRIM(product_id) <> ''
)

SELECT
    p.product_id,
    p.unit_price AS price,
    p.stock_qty AS stock,
    CASE
        WHEN
            CAST(p.stock_qty AS NUMERIC) < 0 OR p.stock_qty ~* '[^0-9.-]'
            THEN 'possibly inactive: no usable stock signal'
        WHEN
            p.unit_price = '' OR p.unit_price = 'NA'
            THEN 'possibly mislabelled: no usable price'
        ELSE 'unpopular or new: priced and stocked, never ordered'
    END AS evidence
FROM norm_prod AS p
WHERE p.norm_id NOT IN (SELECT norm_ord_prod.norm_id FROM norm_ord_prod)
ORDER BY p.product_id;
