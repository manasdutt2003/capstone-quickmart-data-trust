-- Q110: normalised ids in one source only, split by direction
-- orders_only ids have no city (city lives in customers).

WITH o_ids AS (
    SELECT DISTINCT LOWER(TRIM(customer_id)) AS cid
    FROM orders_clean
    WHERE TRIM(customer_id) <> ''
),
c_ids AS (
    SELECT DISTINCT LOWER(TRIM(customer_id)) AS cid
    FROM customers_master
    WHERE TRIM(customer_id) <> ''
)
SELECT cid AS customer_id, 'orders_only' AS direction
FROM o_ids
WHERE cid NOT IN (SELECT cid FROM c_ids)
UNION ALL
SELECT cid, 'customers_only'
FROM c_ids
WHERE cid NOT IN (SELECT cid FROM o_ids)
ORDER BY direction, customer_id;
