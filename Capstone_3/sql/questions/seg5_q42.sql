-- Q42: Category merge/separate decisions

SELECT
    category,
    COUNT(*) AS product_count
FROM products
WHERE TRIM(category) <> ''
GROUP BY category
ORDER BY product_count DESC;

-- Decisions (documented, not computed):
-- GROCERY/Grocery/grocery -> merge (case only)
-- Snacks/snacks -> merge (case only)
-- Dairy -> Dairy & Eggs (suffix only, served list has Dairy & Eggs)
-- Beverages, Household -> keep (singletons, no word-sharing rival)
