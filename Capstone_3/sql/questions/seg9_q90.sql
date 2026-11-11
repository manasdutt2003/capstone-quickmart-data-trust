-- Q90: first-order-month cohorts, share ordering in the next 6 months
-- Late cohorts are right-censored (fewer offsets), shares use full size.

WITH first_orders AS (
    SELECT customer_id, MIN(order_date) AS first_date
    FROM trusted_enriched
    WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
    GROUP BY customer_id
),
based AS (
    SELECT
        t.customer_id,
        SUBSTRING(f.first_date, 1, 7) AS cohort,
        SUBSTRING(t.order_date, 1, 7) AS ym
    FROM trusted_enriched AS t
    JOIN first_orders AS f ON t.customer_id = f.customer_id
    WHERE t.order_date ~ '^\d{4}-\d{2}-\d{2}$'
),
months AS (
    SELECT DISTINCT ym FROM based
),
idx AS (
    SELECT ym, ROW_NUMBER() OVER (ORDER BY ym) AS i FROM months
),
offsets AS (
    SELECT
        b.cohort,
        (iy.i - ic.i) AS offset,
        b.customer_id
    FROM based AS b
    JOIN idx AS ic ON ic.ym = b.cohort
    JOIN idx AS iy ON iy.ym = b.ym
    WHERE (iy.i - ic.i) BETWEEN 0 AND 6
),
sizes AS (
    SELECT cohort, COUNT(DISTINCT customer_id) AS size
    FROM based
    GROUP BY cohort
)
SELECT
    o.cohort,
    o.offset,
    COUNT(DISTINCT o.customer_id) AS n,
    MAX(s.size) AS size,
    ROUND(
        COUNT(DISTINCT o.customer_id)::numeric / MAX(s.size) * 100, 2
    ) AS share_pct
FROM offsets AS o
JOIN sizes AS s ON o.cohort = s.cohort
GROUP BY o.cohort, o.offset
ORDER BY o.cohort, o.offset;
