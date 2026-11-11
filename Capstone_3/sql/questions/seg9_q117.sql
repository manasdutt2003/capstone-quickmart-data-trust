-- Q117: most-frequent vs most-recent payment_mode (tie: count, name)
-- ROW_NUMBER over (count DESC, payment ASC); alt tiebreak changes the count.

WITH counts AS (
    SELECT customer_id, payment_std, COUNT(*) AS n
    FROM trusted_enriched
    WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
    GROUP BY customer_id, payment_std
),
frequent AS (
    SELECT DISTINCT ON (customer_id)
        customer_id,
        payment_std AS frequent
    FROM counts
    ORDER BY customer_id, n DESC, payment_std COLLATE "C"
),
recent AS (
    SELECT DISTINCT ON (customer_id)
        customer_id,
        payment_std AS recent
    FROM trusted_enriched
    WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
    ORDER BY customer_id, order_date DESC, order_id COLLATE "C" DESC
)
SELECT f.customer_id, f.frequent, r.recent
FROM frequent AS f
JOIN recent AS r ON f.customer_id = r.customer_id
WHERE f.frequent IS DISTINCT FROM r.recent
ORDER BY f.customer_id;
