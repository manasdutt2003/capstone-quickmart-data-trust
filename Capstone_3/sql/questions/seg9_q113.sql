-- Q113: customers above p90 cancel/return rate (min 5 orders first)
-- Filtering after the percentile would let 1-order 100% rates set the bar.

WITH rates AS (
    SELECT
        customer_id,
        COUNT(*) AS n,
        AVG(
            CASE
                WHEN status_std IN ('Cancelled', 'Returned') THEN 1.0
                ELSE 0.0
            END
        ) AS rate
    FROM trusted_enriched
    GROUP BY customer_id
    HAVING COUNT(*) >= 5
),
p90 AS (
    SELECT percentile_cont(0.9) WITHIN GROUP (ORDER BY rate) AS p90_rate
    FROM rates
)
SELECT r.customer_id, r.n, ROUND(r.rate, 4) AS rate
FROM rates AS r, p90 AS p
WHERE r.rate > p.p90_rate
ORDER BY r.rate DESC, r.customer_id;
