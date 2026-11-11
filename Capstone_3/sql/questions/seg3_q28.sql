-- Q28: Customers with several cities
-- Requires: customers_raw (staging: verbatim extract in file order),
-- customers_master.
-- Shared-email groups (case-folded key, 9-token placeholder emails
-- excluded) are compared on the raw city spelling; the keeper is the
-- earliest raw signup_date, then raw customer_id, then file order
-- (src/deduplication.py::build_customer_master ranks by signup_date then
-- id), and the other occurrence is dropped. Expected reading: 18 of 21
-- groups differ; the 18 dropped occurrences span 8 case-insensitive raw
-- spellings; the master keeps one city per survivor
-- (195+106+80+47+34+37 = 499).

WITH cust AS (
    SELECT
        LOWER(TRIM(email)) AS em,
        TRIM(city) AS city,
        signup_date,
        customer_id,
        _source_row::int AS src
    FROM customers_raw
    WHERE UPPER(TRIM(email)) NOT IN
        ('', 'NA', 'N/A', 'NULL', 'NONE', 'UNKNOWN', '?', '-', '--')
),

shared AS (
    SELECT em FROM cust GROUP BY em HAVING COUNT(*) > 1
),

grouped AS (
    SELECT
        c.em,
        c.city,
        ROW_NUMBER() OVER (
            PARTITION BY c.em
            ORDER BY c.signup_date COLLATE "C",
                     c.customer_id COLLATE "C",
                     c.src
        ) AS keeper
    FROM cust AS c
    JOIN shared AS s ON s.em = c.em
),

survivor AS (
    SELECT em, city AS keeper_city FROM grouped WHERE keeper = 1
),

valid AS (
    SELECT em, city
    FROM grouped
    WHERE city <> '' AND UPPER(city) NOT IN ('NA', 'N/A', 'UNKNOWN')
),

differing AS (
    SELECT em FROM valid GROUP BY em
    HAVING COUNT(DISTINCT UPPER(city)) > 1
),

dropped AS (
    SELECT v.city AS city, COUNT(*) AS n
    FROM valid AS v
    JOIN differing AS d ON d.em = v.em
    JOIN survivor AS s ON s.em = v.em
    WHERE UPPER(v.city) <> UPPER(COALESCE(s.keeper_city, ''))
    GROUP BY v.city
)

SELECT scope, measure, row_count
FROM (
    SELECT 'merge city check' AS scope,
           'shared-email groups' AS measure,
           COUNT(*) AS row_count, 1 AS scope_ord, 1 AS sort_key
    FROM shared
    UNION ALL
    SELECT 'merge city check', 'groups with differing cities',
           COUNT(*), 1, 2
    FROM differing
    UNION ALL
    SELECT 'merge city check', 'dropped city occurrences',
           COALESCE(SUM(n), 0), 1, 3
    FROM dropped
    UNION ALL
    SELECT 'merge city check', 'raw spellings (case-insensitive)',
           COUNT(DISTINCT UPPER(TRIM(city))), 1, 4
    FROM customers_raw
    WHERE TRIM(city) <> ''
    UNION ALL
    SELECT 'dropped city (raw spelling)', city, n, 2, 100 - n
    FROM dropped
    UNION ALL
    SELECT 'master city (after D03)', 'master rows', COUNT(*), 3, 0
    FROM customers_master
    UNION ALL
    SELECT 'master city (after D03)', city, COUNT(*),
           3, 1000 - COUNT(*)
    FROM customers_master
    GROUP BY city
) AS t
ORDER BY scope_ord, sort_key, measure COLLATE "C";
