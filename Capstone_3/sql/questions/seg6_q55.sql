-- Q55: Customers whose most recent order used a payment mode never used before
-- Nested subquery with tie handling on order_date

WITH customer_payment_history AS (
    SELECT
        o.customer_id,
        o.order_date,
        o.order_id,
        o.payment_std AS payment_mode,
        ROW_NUMBER() OVER (
            PARTITION BY o.customer_id
            ORDER BY o.order_date DESC, o.order_id COLLATE "C" DESC
        ) AS rn_desc,
        -- Earlier orders (strictly before this order's date, or same date but earlier order_id)
        COUNT(*) FILTER (
            WHERE o2.payment_std = o.payment_std
              AND (o2.order_date < o.order_date OR (o2.order_date = o.order_date AND o2.order_id COLLATE "C" < o.order_id COLLATE "C"))
        ) AS prior_uses
    FROM trusted_enriched o
    LEFT JOIN trusted_enriched o2
        ON o.customer_id = o2.customer_id
        AND o2.status_std = 'Delivered'
    WHERE o.status_std = 'Delivered'
    GROUP BY o.customer_id, o.order_date, o.order_id, o.payment_std
),
most_recent AS (
    SELECT
        customer_id,
        order_date,
        order_id,
        payment_mode,
        prior_uses
    FROM customer_payment_history
    WHERE rn_desc = 1
)
SELECT
    customer_id,
    order_date,
    payment_mode,
    CASE WHEN prior_uses = 0 THEN 'NEW_MODE' ELSE 'EXISTING' END AS mode_status
FROM most_recent
WHERE prior_uses = 0
ORDER BY customer_id;

-- Tie handling: When two orders share the same order_date for a customer,
-- we use order_id DESC as tiebreaker (most recent order_id = most recent).
-- Alternative: order_id ASC (earlier order_id = more recent).
-- The alternative definition changes the answer for customers with same-date orders
-- where the payment modes differ between the two orders.