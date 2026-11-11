-- Q109: customer avg qty beyond 2 SD of customer averages, in SQL
-- STDDEV_POP; before vs after excluding out-of-range quantities.

WITH cust_avg AS (
    SELECT
        customer_id,
        AVG(quantity::numeric) AS avg_q
    FROM trusted_enriched
    WHERE quantity ~ '^\d+(\.\d+)?$'
    GROUP BY customer_id
),
stats AS (
    SELECT AVG(avg_q) AS mean_q, STDDEV_POP(avg_q) AS sd_q
    FROM cust_avg
),
cust_avg_valid AS (
    SELECT
        customer_id,
        AVG(quantity::numeric) AS avg_q
    FROM trusted_enriched
    WHERE
        quantity ~ '^\d+(\.\d+)?$'
        AND quantity::numeric BETWEEN 1 AND 10
    GROUP BY customer_id
),
stats_valid AS (
    SELECT AVG(avg_q) AS mean_q, STDDEV_POP(avg_q) AS sd_q
    FROM cust_avg_valid
)
SELECT
    c.customer_id,
    ROUND(c.avg_q, 2) AS avg_qty,
    (
        c.avg_q < (SELECT mean_q - 2 * sd_q FROM stats)
        OR c.avg_q > (SELECT mean_q + 2 * sd_q FROM stats)
    ) AS outlier_before,
    (
        v.avg_q IS NOT NULL
        AND (
            v.avg_q < (SELECT mean_q - 2 * sd_q FROM stats_valid)
            OR v.avg_q > (SELECT mean_q + 2 * sd_q FROM stats_valid)
        )
    ) AS outlier_after
FROM cust_avg AS c
LEFT JOIN cust_avg_valid AS v ON c.customer_id = v.customer_id
ORDER BY c.customer_id;
