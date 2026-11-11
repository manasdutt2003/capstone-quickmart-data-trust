-- Q40: Payment spellings with standard mapping

WITH mapping AS (
    SELECT
        raw,
        standard
    FROM payment_mapping
),

raw_pay AS (
    SELECT
        TRIM(payment_mode) AS val,
        COUNT(*) AS cnt
    FROM orders
    GROUP BY TRIM(payment_mode)
)

SELECT
    r.val AS raw_value,
    r.cnt AS count,
    COALESCE(m.standard, 'UNMAPPED') AS standard_value,
    (m.standard IS NOT NULL AND m.standard NOT LIKE 'UNMAPPED_%') AS assignable
FROM raw_pay AS r
LEFT JOIN mapping AS m ON r.val = m.raw
ORDER BY r.cnt DESC;
