-- Q123: customers buying every catalogue category (division + HAVING)
-- Blank categories: division ignores them, HAVING COUNT(DISTINCT) can
-- match the wrong total if blanks are counted. Empty (nobody covers all
-- categories) is the correct answer.

WITH catalogue AS (
    SELECT DISTINCT TRIM(category) AS cat
    FROM products_clean
    WHERE TRIM(category) <> ''
),
cust_cats AS (
    SELECT DISTINCT customer_id, category_std AS cat
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
        AND TRIM(category_std) NOT IN ('', 'UNMAPPED', 'UNKNOWN')
),
via_division AS (
    SELECT customer_id
    FROM (SELECT DISTINCT customer_id FROM cust_cats) AS c
    WHERE NOT EXISTS (
        SELECT 1
        FROM catalogue
        WHERE NOT EXISTS (
            SELECT 1
            FROM cust_cats
            WHERE
                cust_cats.customer_id = c.customer_id
                AND cust_cats.cat = catalogue.cat
        )
    )
),
via_having AS (
    SELECT customer_id
    FROM cust_cats
    GROUP BY customer_id
    HAVING COUNT(DISTINCT cat) = (SELECT COUNT(*) FROM catalogue)
)
SELECT customer_id, 'NOT_EXISTS_division' AS method FROM via_division
UNION ALL
SELECT customer_id, 'HAVING_count' AS method FROM via_having
ORDER BY customer_id, method;
