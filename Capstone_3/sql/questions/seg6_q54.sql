-- Q54: RANK, DENSE_RANK, ROW_NUMBER over customers by completed value
-- Show positions where they disagree

WITH customer_values AS (
    SELECT
        customer_id,
        city_std,
        SUM(line_value) AS total_value
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
    GROUP BY customer_id, city_std
),
ranked AS (
    SELECT
        customer_id,
        city_std,
        total_value,
        RANK() OVER (ORDER BY total_value DESC) AS rnk,
        DENSE_RANK() OVER (ORDER BY total_value DESC) AS dense_rnk,
        ROW_NUMBER() OVER (ORDER BY total_value DESC, customer_id COLLATE "C") AS row_n
    FROM customer_values
)
SELECT
    customer_id,
    city_std,
    total_value,
    rnk,
    dense_rnk,
    row_n,
    CASE
        WHEN rnk <> dense_rnk THEN 'RANK vs DENSE_RANK disagree (tie)'
        WHEN rnk <> row_n THEN 'RANK vs ROW_NUMBER disagree (tie)'
        WHEN dense_rnk <> row_n THEN 'DENSE_RANK vs ROW_NUMBER disagree (tie)'
        ELSE 'agree'
    END AS disagreement
FROM ranked
WHERE rnk <> dense_rnk OR rnk <> row_n OR dense_rnk <> row_n
ORDER BY total_value DESC, customer_id;

-- Which ranking for top 5?
-- DENSE_RANK is correct for "top 5 customers" because:
-- 1. Ties get the same rank (fair to customers with equal value)
-- 2. No gaps in ranking (if two customers tie for 1st, next is 2nd, not 3rd)
-- 3. ROW_NUMBER arbitrarily breaks ties (unfair, non-deterministic without extra ordering)
-- 4. RANK leaves gaps (two 1st place -> next is 3rd), confusing for "top 5" lists