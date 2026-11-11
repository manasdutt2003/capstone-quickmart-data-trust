-- Q70: Recursive query over manager hierarchy from customer referral field
-- Cycle detection, max depth

-- Note: The extracts do not contain a referral/manager field in customers table.
-- This query assumes a 'referral_id' column exists in customers (self-referencing).
-- Since it doesn't exist in the data, this is a template showing the pattern.

-- WITH RECURSIVE referral_chain AS (
--     -- Anchor: customers with no referral (roots)
--     SELECT
--         customer_id,
--         referral_id,
--         1 AS depth,
--         ARRAY[customer_id] AS path
--     FROM customers
--     WHERE referral_id IS NULL OR referral_id = ''
--
--     UNION ALL
--
--     -- Recursive: follow referral links
--     SELECT
--         c.customer_id,
--         c.referral_id,
--         rc.depth + 1,
--         rc.path || c.customer_id
--     FROM customers c
--     JOIN referral_chain rc ON TRIM(c.referral_id) = TRIM(rc.customer_id)
--     WHERE
--         c.referral_id IS NOT NULL
--         AND c.referral_id <> ''
--         AND NOT c.customer_id = ANY(rc.path)  -- cycle detection
--         AND rc.depth < 100  -- safety depth limit
-- )
-- SELECT
--     MAX(depth) AS max_depth,
--     COUNT(*) AS total_customers_in_chains
-- FROM referral_chain;

-- Cycle detection:
-- 1. ARRAY[customer_id] path tracks visited nodes
-- 2. NOT c.customer_id = ANY(rc.path) prevents revisiting
-- 3. Self-reference (c.referral_id = c.customer_id) caught immediately
-- 4. Mutual reference (A->B, B->A) caught on second iteration

-- Depth limit effect:
-- depth < 100: stops at 100 levels even if chain continues
-- Real-world referral chains rarely exceed 10-20 levels
-- 100 is safe ceiling; deeper chains likely indicate data error

-- Honest analogue on the extracts (executable): the extracts hold no
-- referral/manager column, so no hierarchy can be built. This query
-- reports that fact with counts instead of fabricating a column.
SELECT
    (SELECT COUNT(*) FROM customers_master) AS customers,
    0 AS referral_chains,
    0 AS max_depth,
    'referral_id absent from extracts: no hierarchy to recurse' AS analogue_note;