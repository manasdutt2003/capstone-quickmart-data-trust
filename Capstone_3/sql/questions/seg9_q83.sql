-- Q83: ordered Jan-Jun 2026 but not Jul-Oct 2026 (EXCEPT + NOT EXISTS)
-- Empty customer_ids excluded on both sides; NULLs would split them.

WITH h1 AS (
    SELECT DISTINCT customer_id
    FROM trusted_enriched
    WHERE
        order_month BETWEEN '2026-01' AND '2026-06'
        AND TRIM(customer_id) <> ''
),
h2 AS (
    SELECT DISTINCT customer_id
    FROM trusted_enriched
    WHERE
        order_month BETWEEN '2026-07' AND '2026-10'
        AND TRIM(customer_id) <> ''
),
via_except AS (
    SELECT customer_id FROM h1
    EXCEPT
    SELECT customer_id FROM h2
),
via_not_exists AS (
    SELECT customer_id
    FROM h1
    WHERE NOT EXISTS (
        SELECT 1 FROM h2 WHERE h2.customer_id = h1.customer_id
    )
)
SELECT customer_id, 'EXCEPT' AS method FROM via_except
UNION ALL
SELECT customer_id, 'NOT_EXISTS' AS method FROM via_not_exists
ORDER BY customer_id, method;
