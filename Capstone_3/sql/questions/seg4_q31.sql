-- Q31: Product match - typing variants vs nonexistent
-- Typing variant: unmatched value sharing substring with real normalised id
-- Nonexistent: empty or no overlap

WITH norm_prod AS (
    SELECT
        product_id,
        UPPER(REPLACE(REPLACE(TRIM(product_id), ' ', ''), '-', '')) AS norm_id
    FROM products
    WHERE TRIM(product_id) <> ''
),

unmatched AS (
    SELECT
        TRIM(o.product_id) AS prod_id,
        UPPER(REPLACE(REPLACE(TRIM(o.product_id), ' ', ''), '-', '')) AS norm_id
    FROM orders AS o
    WHERE
        UPPER(REPLACE(REPLACE(TRIM(o.product_id), ' ', ''), '-', '')) NOT IN (
            SELECT norm_prod.norm_id FROM norm_prod
        )
        AND TRIM(o.product_id) <> ''
),

classified AS (
    SELECT
        prod_id,
        CASE WHEN EXISTS (
            SELECT 1 FROM norm_prod AS p
            WHERE
                u.norm_id LIKE '%' || p.norm_id || '%'
                OR p.norm_id LIKE '%' || u.norm_id || '%'
        ) THEN 'typing_variant' ELSE 'nonexistent' END AS kind
    FROM unmatched AS u
)

SELECT
    kind,
    COUNT(*) AS cnt
FROM classified
GROUP BY kind

UNION ALL

SELECT
    'empty' AS kind,
    COUNT(*) AS cnt
FROM orders
WHERE TRIM(product_id) = '';

-- Top typing variant
WITH norm_prod AS (
    SELECT
        UPPER(
            REPLACE(REPLACE(TRIM(product_id), ' ', ''), '-', '')
        ) AS norm_id
    FROM products
    WHERE TRIM(product_id) <> ''
),

typing AS (
    SELECT TRIM(o.product_id) AS prod_id
    FROM orders AS o
    WHERE
        UPPER(REPLACE(REPLACE(TRIM(o.product_id), ' ', ''), '-', '')) NOT IN (
            SELECT norm_prod.norm_id FROM norm_prod
        )
        AND TRIM(o.product_id) <> ''
        AND EXISTS (
            SELECT 1 FROM norm_prod AS p
            WHERE
                UPPER(
                    REPLACE(REPLACE(TRIM(o.product_id), ' ', ''), '-', '')
                ) LIKE '%'
                || p.norm_id
                || '%'
                OR p.norm_id LIKE '%'
                || UPPER(REPLACE(REPLACE(TRIM(o.product_id), ' ', ''), '-', ''))
                || '%'
        )
)

SELECT
    prod_id,
    COUNT(*) AS cnt
FROM typing
GROUP BY prod_id
ORDER BY cnt DESC
LIMIT 1;

-- Top missing
WITH norm_prod AS (
    SELECT
        UPPER(
            REPLACE(REPLACE(TRIM(product_id), ' ', ''), '-', '')
        ) AS norm_id
    FROM products
    WHERE TRIM(product_id) <> ''
),

missing AS (
    SELECT TRIM(o.product_id) AS prod_id
    FROM orders AS o
    WHERE (
        UPPER(REPLACE(REPLACE(TRIM(o.product_id), ' ', ''), '-', '')) NOT IN (
            SELECT norm_prod.norm_id FROM norm_prod
        )
        AND NOT EXISTS (
            SELECT 1 FROM norm_prod AS p
            WHERE
                UPPER(
                    REPLACE(REPLACE(TRIM(o.product_id), ' ', ''), '-', '')
                ) LIKE '%'
                || p.norm_id
                || '%'
                OR p.norm_id LIKE '%'
                || UPPER(REPLACE(REPLACE(TRIM(o.product_id), ' ', ''), '-', ''))
                || '%'
        )
    )
    OR TRIM(o.product_id) = ''
)

SELECT
    prod_id,
    COUNT(*) AS cnt
FROM missing
GROUP BY prod_id
ORDER BY cnt DESC
LIMIT 1;
