-- Q108: same-customer orders in the prior 30d, both engines
-- Correlated [d-30, d] count vs RANGE frame minus self; boundary days:
-- '< d' would drop same-day peers, '<= d-30' flips the 30th day.

WITH dated AS (
    SELECT customer_id, order_id, order_date::date AS d
    FROM trusted_enriched
    WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
),
correlated AS (
    SELECT
        o.order_id,
        (
            SELECT COUNT(*)
            FROM dated AS i
            WHERE
                i.customer_id = o.customer_id
                AND i.order_id <> o.order_id
                AND i.d BETWEEN o.d - 30 AND o.d
        ) AS prior_30d
    FROM dated AS o
),
ranged AS (
    SELECT
        order_id,
        COUNT(*) OVER (
            PARTITION BY customer_id
            ORDER BY d
            RANGE BETWEEN INTERVAL '30 days' PRECEDING AND CURRENT ROW
        ) - 1 AS range_n
    FROM dated
)
SELECT
    c.order_id,
    c.prior_30d,
    (c.prior_30d = r.range_n) AS engines_agree
FROM correlated AS c
JOIN ranged AS r ON c.order_id = r.order_id
ORDER BY c.order_id;
