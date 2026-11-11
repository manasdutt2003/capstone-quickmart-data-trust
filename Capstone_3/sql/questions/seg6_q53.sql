-- Q53: Check constraint / trigger for quantity range
-- Agreed range: 1 to 10 (from Q44 IQR fence)
-- Test against crafted rows including boundary values

-- Check constraint (recommended for new data)
-- ALTER TABLE orders
-- ADD CONSTRAINT chk_quantity_range
-- CHECK (quantity IS NOT NULL AND quantity ~ '^\d+$' AND CAST(quantity AS INT) BETWEEN 1 AND 10);

-- Trigger approach (handles existing data + new inserts)
-- CREATE OR REPLACE FUNCTION validate_quantity_range()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     IF NEW.quantity IS NULL OR NEW.quantity !~ '^\d+$' OR CAST(NEW.quantity AS INT) NOT BETWEEN 1 AND 10 THEN
--         RAISE EXCEPTION 'Quantity must be integer between 1 and 10, got: %', NEW.quantity;
--     END IF;
--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;

-- CREATE TRIGGER trg_quantity_range
-- BEFORE INSERT OR UPDATE ON orders
-- FOR EACH ROW EXECUTE FUNCTION validate_quantity_range();

-- Test cases:
-- 1. quantity = '1'      -> PASS (lower boundary)
-- 2. quantity = '10'     -> PASS (upper boundary)
-- 3. quantity = '0'      -> FAIL (below lower bound)
-- 4. quantity = '11'     -> FAIL (above upper bound)
-- 5. quantity = 'abc'    -> FAIL (non-numeric)
-- 6. quantity = '5.5'    -> FAIL (not integer)
-- 7. quantity = ''       -> FAIL (empty)
-- 8. quantity = NULL     -> FAIL (null)

-- Why trigger over constraint:
-- 1. Constraint only validates new data; trigger can log/reject with custom message
-- 2. Constraint fails silently on bulk load; trigger can route bad rows to quarantine table
-- 3. Existing invalid rows in table would violate constraint on creation
-- 4. Trigger allows custom logging for audit trail

-- Trade-off: Trigger has slight performance overhead vs constraint (negligible for this volume)

-- Executable validation view over the agreed range (1 to 10):
WITH tests(qty, expected) AS (
    VALUES
        ('1', 'PASS'),
        ('10', 'PASS'),
        ('0', 'FAIL'),
        ('11', 'FAIL'),
        ('abc', 'FAIL'),
        ('5.5', 'FAIL'),
        ('', 'FAIL')
)
SELECT
    qty,
    expected,
    CASE
        WHEN qty ~ '^\d+$' AND CAST(qty AS INT) BETWEEN 1 AND 10
            THEN 'PASS'
        ELSE 'FAIL'
    END AS actual,
    expected = CASE
        WHEN qty ~ '^\d+$' AND CAST(qty AS INT) BETWEEN 1 AND 10
            THEN 'PASS'
        ELSE 'FAIL'
    END AS matches_expected
FROM tests
ORDER BY qty;