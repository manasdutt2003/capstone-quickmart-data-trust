-- Q36: Fuzzy-attributed orders (matched only via normalised ID)

WITH norm_cust AS (
    SELECT
        customer_id,
        UPPER(REPLACE(REPLACE(TRIM(customer_id), ' ', ''), '-', '')) AS norm_id
    FROM customers
    WHERE TRIM(customer_id) <> ''
),

order_class AS (
    SELECT
        o.*,
        CASE
            WHEN
                TRIM(o.customer_id) IN (
                    SELECT norm_cust.customer_id FROM norm_cust
                )
                THEN 'matched_exact'
            WHEN
                UPPER(
                    REPLACE(REPLACE(TRIM(o.customer_id), ' ', ''), '-', '')
                ) IN (SELECT norm_cust.norm_id FROM norm_cust
                )
                THEN 'matched_normalised'
            ELSE 'unmatched'
        END AS match_type
    FROM orders AS o
),

fuzzy AS (
    SELECT *
    FROM order_class
    WHERE match_type = 'matched_normalised'
),

total_val AS (
    SELECT
        SUM(
            CASE
                WHEN
                    TRIM(quantity) ~ '^\d+$'
                    AND TRIM(unit_price_paid) ~ '^\d+(\.\d+)?$'
                    THEN
                        CAST(quantity AS INT) * CAST(unit_price_paid AS NUMERIC)
                        * (1 - COALESCE(
                            CAST(NULLIF(
                                REPLACE(discount, '%', ''), ''
                            ) AS NUMERIC)
                            / CASE WHEN discount LIKE '%%' THEN 100 ELSE 1 END,
                            0
                        ))
                ELSE 0
            END
        ) AS val
    FROM orders
),

fuzzy_val AS (
    SELECT
        SUM(
            CASE
                WHEN
                    TRIM(quantity) ~ '^\d+$'
                    AND TRIM(unit_price_paid) ~ '^\d+(\.\d+)?$'
                    THEN
                        CAST(quantity AS INT) * CAST(unit_price_paid AS NUMERIC)
                        * (1 - COALESCE(
                            CAST(NULLIF(
                                REPLACE(discount, '%', ''), ''
                            ) AS NUMERIC)
                            / CASE WHEN discount LIKE '%%' THEN 100 ELSE 1 END,
                            0
                        ))
                ELSE 0
            END
        ) AS val
    FROM fuzzy
)

SELECT
    (SELECT COUNT(*) FROM fuzzy) AS fuzzy_orders,
    ROUND(
        (SELECT val FROM fuzzy_val) / (SELECT val FROM total_val) * 100, 2
    ) AS fuzzy_value_share_pct;
