-- Q93: distinct categories per customer in the last 180 data days
-- Window [max-180, max] inclusive; boundary-day orders count.

WITH bounds AS (
    SELECT MAX(order_date::date) AS end_date
    FROM trusted_enriched
    WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
)
SELECT
    t.customer_id,
    COUNT(DISTINCT t.category_std) AS n_categories
FROM trusted_enriched AS t, bounds AS b
WHERE
    t.order_date ~ '^\d{4}-\d{2}-\d{2}$'
    AND t.order_date::date BETWEEN b.end_date - 180 AND b.end_date
GROUP BY t.customer_id
ORDER BY n_categories DESC, t.customer_id;
