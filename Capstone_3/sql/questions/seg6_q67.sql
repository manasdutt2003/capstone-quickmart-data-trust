-- Q67: Complex query with 3+ CTEs, window function, correlated subquery, set operation
-- Customers with completed order but no delivery_days on ANY order

WITH completed_orders AS (
    SELECT
        customer_id,
        order_id,
        delivery_days,
        order_date
    FROM trusted_enriched
    WHERE status_std = 'Delivered'
),
customers_with_null_delivery AS (
    SELECT DISTINCT customer_id
    FROM completed_orders
    WHERE delivery_days IS NULL OR TRIM(delivery_days) = ''
),
all_completed_customers AS (
    SELECT DISTINCT customer_id
    FROM completed_orders
),
customers_all_orders_have_delivery AS (
    SELECT customer_id
    FROM completed_orders
    WHERE delivery_days IS NOT NULL AND TRIM(delivery_days) <> ''
    GROUP BY customer_id
    HAVING COUNT(*) = COUNT(delivery_days)
      AND COUNT(*) = (SELECT COUNT(*) FROM completed_orders co WHERE co.customer_id = completed_orders.customer_id)
),
customers_missing_delivery AS (
    SELECT cwd.customer_id
    FROM customers_with_null_delivery cwd
    WHERE NOT EXISTS (
        SELECT 1
        FROM customers_all_orders_have_delivery caohd
        WHERE caohd.customer_id = cwd.customer_id
    )
)
SELECT customer_id
FROM customers_missing_delivery
ORDER BY customer_id;

-- Anti-join approach (equivalent):
-- SELECT DISTINCT co.customer_id
-- FROM completed_orders co
-- WHERE co.delivery_days IS NULL OR TRIM(co.delivery_days) = ''
-- EXCEPT
-- SELECT DISTINCT co2.customer_id
-- FROM completed_orders co2
-- WHERE co2.delivery_days IS NOT NULL AND TRIM(co2.delivery_days) <> ''
-- GROUP BY co2.customer_id
-- HAVING COUNT(*) = (SELECT COUNT(*) FROM completed_orders co3 WHERE co3.customer_id = co2.customer_id);

-- Execution plan expectation:
-- 1. CTE completed_orders: Seq Scan on trusted_enriched (filtered by status_std)
-- 2. CTE customers_with_null_delivery: Hash Aggregate on filtered rows
-- 3. Anti-join: Hash Anti Join between null-delivery and all-delivery customers
-- 4. Final sort

-- If orders table grew 10x:
-- 1. Seq Scan cost increases linearly
-- 2. Hash Anti Join memory may spill to disk
-- 3. First failure: Hash Anti Join spilling (work_mem exceeded)
-- Why: Anti-join builds hash table of all-delivery customers; 10x growth may exceed work_mem