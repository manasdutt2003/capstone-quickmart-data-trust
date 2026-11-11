-- Q6: Which date values changed when parsed (and in which families)
-- Requires: orders_loaded, customers_loaded (staging).
-- Mirrors src/normalise.py::parse_date: values are classified by shape in
-- the loader's format order (ISO first, day-first DD/MM/YYYY before
-- month-first); blanks/placeholders stay unparseable. Counts split raw
-- values into already-ISO / changed form / unparseable.

WITH months (token) AS (
    VALUES ('jan'), ('feb'), ('mar'), ('apr'), ('may'), ('jun'),
           ('jul'), ('aug'), ('sep'), ('oct'), ('nov'), ('dec')
),

dates AS (
    SELECT 'customers' AS scope, TRIM(raw_signup_date) AS raw
    FROM customers_loaded
    UNION ALL
    SELECT 'orders', TRIM(raw_order_date)
    FROM orders_loaded
),

shapes AS (
    SELECT
        scope,
        raw,
        (regexp_match(LOWER(raw), '^[0-9]{1,2}-([a-z]{3})-[0-9]{2,4}$'))[1]
            AS dash_month,
        (regexp_match(LOWER(raw), '^[0-9]{1,2} ([a-z]{3}) [0-9]{4}$'))[1]
            AS space_month
    FROM dates
),

flags AS (
    SELECT
        scope,
        raw,
        dash_month IN (SELECT token FROM months) AS dash_ok,
        space_month IN (SELECT token FROM months) AS space_ok
    FROM shapes
),

classified AS (
    SELECT
        scope,
        CASE
            WHEN raw IS NULL OR raw = '' THEN 'unparseable'
            WHEN raw ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN 'already ISO'
            WHEN raw ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$' THEN 'changed'
            WHEN raw ~ '^[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{4}$' THEN 'changed'
            WHEN dash_ok THEN 'changed'
            WHEN raw ~ '^[0-9]{4}/[0-9]{1,2}/[0-9]{1,2}$' THEN 'changed'
            WHEN space_ok THEN 'changed'
            ELSE 'unparseable'
        END AS status,
        CASE
            WHEN raw ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$' THEN 'DD/MM/YYYY'
            WHEN raw ~ '^[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{4}$' THEN 'DD.MM.YYYY'
            WHEN dash_ok THEN 'DD-Mon-YY'
            WHEN raw ~ '^[0-9]{4}/[0-9]{1,2}/[0-9]{1,2}$' THEN 'YYYY/MM/DD'
            WHEN space_ok THEN 'DD Mon YYYY'
            ELSE '-'
        END AS form
    FROM flags
)

SELECT scope, status, form, COUNT(*) AS row_count
FROM classified
GROUP BY scope, status, form
ORDER BY
    CASE scope WHEN 'customers' THEN 1 ELSE 2 END,
    CASE status
        WHEN 'already ISO' THEN 1
        WHEN 'changed' THEN 2
        ELSE 3
    END,
    CASE form
        WHEN '-' THEN 0
        WHEN 'DD/MM/YYYY' THEN 1
        WHEN 'DD.MM.YYYY' THEN 2
        WHEN 'DD-Mon-YY' THEN 3
        WHEN 'YYYY/MM/DD' THEN 4
        ELSE 5
    END;
