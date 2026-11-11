-- Q103: products never in a completed order (NOT IN vs NOT EXISTS)
-- NOT IN is poisoned by a NULL in the set; NOT EXISTS stays correct.
-- The _with_null branch injects one NULL to demonstrate (returns 0 rows).

WITH completed_pids AS (
    SELECT DISTINCT product_id
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
        AND TRIM(product_id) <> ''
),
all_pids AS (
    SELECT DISTINCT TRIM(product_id) AS pid
    FROM products_clean
    WHERE TRIM(product_id) <> ''
),
via_not_exists AS (
    SELECT pid
    FROM all_pids AS a
    WHERE NOT EXISTS (
        SELECT 1 FROM completed_pids AS c WHERE c.product_id = a.pid
    )
),
via_not_in AS (
    SELECT pid
    FROM all_pids
    WHERE pid NOT IN (SELECT product_id FROM completed_pids)
),
via_not_in_null AS (
    SELECT pid
    FROM all_pids
    WHERE pid NOT IN (
        SELECT product_id FROM completed_pids
        UNION ALL
        SELECT NULL
    )
)
SELECT pid AS product_id, 'NOT_EXISTS' AS method FROM via_not_exists
UNION ALL
SELECT pid, 'NOT_IN' AS method FROM via_not_in
UNION ALL
SELECT pid, 'NOT_IN_with_null_demo' AS method FROM via_not_in_null
ORDER BY product_id, method;
