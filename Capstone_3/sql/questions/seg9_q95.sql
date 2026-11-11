-- Q95: monthly order count rising in each of 4 consecutive months
-- LAG + gaps-and-islands over qualifying months; pairwise-only would flag
-- any single rise. Empty (no customer qualifies) is the correct answer.

WITH monthly AS (
    SELECT
        customer_id,
        SUBSTRING(order_date, 1, 7) AS ym,
        COUNT(*) AS n
    FROM trusted_enriched
    WHERE order_date ~ '^\d{4}-\d{2}-\d{2}$'
    GROUP BY customer_id, SUBSTRING(order_date, 1, 7)
),
flagged AS (
    SELECT
        customer_id,
        ym,
        n,
        (n > LAG(n) OVER (
            PARTITION BY customer_id ORDER BY ym
        )) AS rise
    FROM monthly
),
streaks AS (
    SELECT
        customer_id,
        MAX(streak_len) AS max_rise_streak
    FROM (
        SELECT
            customer_id,
            COUNT(*) AS streak_len
        FROM (
            SELECT
                customer_id,
                ym,
                ROW_NUMBER() OVER (
                    PARTITION BY customer_id ORDER BY ym
                )
                - ROW_NUMBER() OVER (
                    PARTITION BY customer_id, rise ORDER BY ym
                ) AS island
            FROM flagged
            WHERE rise IS TRUE
        ) islands
        GROUP BY customer_id, island
    ) grouped
    GROUP BY customer_id
)
SELECT customer_id, max_rise_streak
FROM streaks
WHERE max_rise_streak >= 3
ORDER BY customer_id;
