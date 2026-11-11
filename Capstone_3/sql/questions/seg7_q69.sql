-- Q69: Execution plan analysis for monthly completed value per category joined to customer
-- Identify join type (hash/merge/nested loop), propose index/partitioning

-- Query to analyze:
-- EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
-- SELECT
--     date_trunc('month', o.order_date)::date AS order_month,
--     c.city_std,
--     p.category_std,
--     SUM(o.line_value) AS total_value
-- FROM trusted_enriched o
-- JOIN customers c ON TRIM(o.customer_id) = TRIM(c.customer_id)
-- JOIN products p ON TRIM(o.product_id) = TRIM(p.product_id)
-- WHERE o.status_std = 'Delivered'
--   AND o.line_value IS NOT NULL
-- GROUP BY order_month, c.city_std, p.category_std
-- ORDER BY order_month, c.city_std, p.category_std;

-- Observed plan on current data (~522 trusted rows, 499 customers):
-- 1. Seq Scan on orders_clean with status/line_value filters
-- 2. Nested Loop joins to customers_master and products_clean
--    (planner avoids hashing: dimensions are tiny, join keys need
--    TRIM() so no usable btree index applies)
-- 3. One Hash Anti Join for the NOT EXISTS (rule_failure_log)
-- 4. GroupAggregate + Sort

-- For larger data (>100K rows):
-- - Merge Join becomes favorable if inputs are sorted
-- - Nested Loop only if one side is very small (<100 rows)

-- Proposed optimization:
-- 1. Index on trusted_enriched(status_std, line_value) for filter
-- 2. Index on customers(customer_id) for join
-- 3. Index on products(product_id) for join
-- 4. Partition trusted_enriched by order_date (monthly) for:
--    - Partition pruning on order_date range queries
--    - Better parallelism

-- Trade-offs for daily load:
-- + Query performance: partition pruning eliminates irrelevant partitions
-- + Parallel query: each partition processed independently
-- - Load complexity: must route rows to correct partition
-- - Maintenance: partition management (add/drop monthly)
-- - Index overhead: local indexes per partition vs global

-- Recommended: Monthly range partitioning on order_date
-- CREATE TABLE trusted_enriched_partitioned (LIKE trusted_enriched) PARTITION BY RANGE (order_date);
-- CREATE TABLE trusted_enriched_2024_01 PARTITION OF trusted_enriched_partitioned
--     FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Live plan for the analysis query on current data (executable):
EXPLAIN
SELECT
    SUBSTRING(o.order_date, 1, 7) AS order_month,
    TRIM(c.city) AS city,
    TRIM(p.category) AS category,
    SUM(o.line_value) AS total_value
FROM trusted_enriched o
JOIN customers_master c ON TRIM(o.customer_id) = TRIM(c.customer_id)
JOIN products_clean p ON TRIM(o.product_id) = TRIM(p.product_id)
WHERE o.status_std = 'Delivered'
    AND o.line_value IS NOT NULL
GROUP BY SUBSTRING(o.order_date, 1, 7), TRIM(c.city), TRIM(p.category)
ORDER BY SUBSTRING(o.order_date, 1, 7), TRIM(c.city), TRIM(p.category);