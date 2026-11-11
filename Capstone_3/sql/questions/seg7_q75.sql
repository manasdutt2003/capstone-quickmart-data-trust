-- Q75: Reproducible data-quality scorecard as single SQL view
-- Completeness, uniqueness, referential integrity, conformance
-- Weighted and normalized to 0-100

-- Weights (configurable):
-- Completeness: 30%
-- Uniqueness: 20%
-- Referential Integrity: 30%
-- Conformance: 20%

-- NULL-safety: staging is TEXT loaded via COPY, which reads unquoted
-- empty fields as NULL, so blank means NULLIF(TRIM(x), '') IS NULL
-- (a bare = '' misses NULLs; see the parity log in
-- tests/test_questions_seg6_7.py).

WITH table_scores AS (
    SELECT 'customers' AS table_name,
        (1 - (
            (SELECT COUNT(*) FROM customers WHERE NULLIF(TRIM(customer_id), '') IS NULL)
            + (SELECT COUNT(*) FROM customers WHERE NULLIF(TRIM(customer_name), '') IS NULL)
            + (SELECT COUNT(*) FROM customers WHERE NULLIF(TRIM(email), '') IS NULL)
            + (SELECT COUNT(*) FROM customers WHERE NULLIF(TRIM(city), '') IS NULL)
            + (SELECT COUNT(*) FROM customers WHERE NULLIF(TRIM(phone), '') IS NULL)
            + (SELECT COUNT(*) FROM customers WHERE NULLIF(TRIM(signup_date), '') IS NULL)
        )::numeric / (SELECT COUNT(*) * 6 FROM customers)) * 100 AS completeness,
        (1 - (SELECT COUNT(*) - COUNT(DISTINCT NULLIF(TRIM(customer_id), '')) FROM customers)::numeric / NULLIF((SELECT COUNT(*) FROM customers), 0)) * 100 AS uniqueness,
        (1 - (
            SELECT COUNT(DISTINCT TRIM(o.customer_id))
            FROM orders o LEFT JOIN customers c ON NULLIF(TRIM(o.customer_id), '') = NULLIF(TRIM(c.customer_id), '')
            WHERE NULLIF(TRIM(o.customer_id), '') IS NOT NULL AND c.customer_id IS NULL
        )::numeric / NULLIF((SELECT COUNT(DISTINCT TRIM(customer_id)) FROM orders WHERE NULLIF(TRIM(customer_id), '') IS NOT NULL), 0)) * 100 AS referential_integrity,
        (1 - (SELECT COUNT(*) FROM customers WHERE NULLIF(TRIM(email), '') IS NULL OR TRIM(email) NOT LIKE '%@%.%' OR NULLIF(TRIM(phone), '') IS NULL OR TRIM(phone) !~ '^\d{10}$' OR NULLIF(TRIM(signup_date), '') IS NULL OR TRIM(signup_date) !~ '^\d{4}-\d{2}-\d{2}$')::numeric / (SELECT COUNT(*) FROM customers)) * 100 AS conformance

    UNION ALL
    SELECT 'products',
        (1 - (
            (SELECT COUNT(*) FROM products WHERE NULLIF(TRIM(product_id), '') IS NULL)
            + (SELECT COUNT(*) FROM products WHERE NULLIF(TRIM(product_name), '') IS NULL)
            + (SELECT COUNT(*) FROM products WHERE NULLIF(TRIM(category), '') IS NULL)
            + (SELECT COUNT(*) FROM products WHERE NULLIF(TRIM(unit_price), '') IS NULL)
            + (SELECT COUNT(*) FROM products WHERE NULLIF(TRIM(stock_qty), '') IS NULL)
        )::numeric / (SELECT COUNT(*) * 5 FROM products)) * 100,
        (1 - (SELECT COUNT(*) - COUNT(DISTINCT NULLIF(TRIM(product_id), '')) FROM products)::numeric / NULLIF((SELECT COUNT(*) FROM products), 0)) * 100,
        (1 - (
            SELECT COUNT(DISTINCT TRIM(o.product_id)) FROM orders o LEFT JOIN products p ON NULLIF(TRIM(o.product_id), '') = NULLIF(TRIM(p.product_id), '')
            WHERE NULLIF(TRIM(o.product_id), '') IS NOT NULL AND p.product_id IS NULL
        )::numeric / NULLIF((SELECT COUNT(DISTINCT TRIM(product_id)) FROM orders WHERE NULLIF(TRIM(product_id), '') IS NOT NULL), 0)) * 100,
        (1 - (SELECT COUNT(*) FROM products WHERE NULLIF(TRIM(unit_price), '') IS NULL OR TRIM(unit_price) !~ '^\d+(\.\d+)?$')::numeric / (SELECT COUNT(*) FROM products)) * 100

    UNION ALL
    SELECT 'orders',
        (1 - (
            (SELECT COUNT(*) FROM orders WHERE NULLIF(TRIM(order_id), '') IS NULL)
            + (SELECT COUNT(*) FROM orders WHERE NULLIF(TRIM(customer_id), '') IS NULL)
            + (SELECT COUNT(*) FROM orders WHERE NULLIF(TRIM(product_id), '') IS NULL)
            + (SELECT COUNT(*) FROM orders WHERE NULLIF(TRIM(order_date), '') IS NULL)
            + (SELECT COUNT(*) FROM orders WHERE NULLIF(TRIM(quantity), '') IS NULL)
            + (SELECT COUNT(*) FROM orders WHERE NULLIF(TRIM(unit_price_paid), '') IS NULL)
            + (SELECT COUNT(*) FROM orders WHERE NULLIF(TRIM(discount), '') IS NULL)
            + (SELECT COUNT(*) FROM orders WHERE NULLIF(TRIM(payment_mode), '') IS NULL)
            + (SELECT COUNT(*) FROM orders WHERE NULLIF(TRIM(order_status), '') IS NULL)
            + (SELECT COUNT(*) FROM orders WHERE NULLIF(TRIM(delivery_days), '') IS NULL)
        )::numeric / (SELECT COUNT(*) * 10 FROM orders)) * 100,
        (1 - (SELECT COUNT(*) - COUNT(DISTINCT NULLIF(TRIM(order_id), '')) FROM orders)::numeric / NULLIF((SELECT COUNT(*) FROM orders), 0)) * 100,
        (1 - (
            (SELECT COUNT(DISTINCT TRIM(o.customer_id))
             FROM orders o LEFT JOIN customers c ON NULLIF(TRIM(o.customer_id), '') = NULLIF(TRIM(c.customer_id), '')
             WHERE NULLIF(TRIM(o.customer_id), '') IS NOT NULL AND c.customer_id IS NULL)
            + (SELECT COUNT(DISTINCT TRIM(o.product_id))
               FROM orders o LEFT JOIN products p ON NULLIF(TRIM(o.product_id), '') = NULLIF(TRIM(p.product_id), '')
               WHERE NULLIF(TRIM(o.product_id), '') IS NOT NULL AND p.product_id IS NULL)
        )::numeric / NULLIF(
            (SELECT COUNT(DISTINCT TRIM(customer_id)) FROM orders WHERE NULLIF(TRIM(customer_id), '') IS NOT NULL)
            + (SELECT COUNT(DISTINCT TRIM(product_id)) FROM orders WHERE NULLIF(TRIM(product_id), '') IS NOT NULL), 0)) * 100,
        (1 - (SELECT COUNT(*) FROM orders WHERE NULLIF(TRIM(quantity), '') IS NULL OR TRIM(quantity) !~ '^\d+$' OR NULLIF(TRIM(unit_price_paid), '') IS NULL OR TRIM(unit_price_paid) !~ '^\d+(\.\d+)?$' OR NULLIF(TRIM(discount), '') IS NULL OR TRIM(discount) !~ '^(\d+(\.\d+)?%?|\d*\.\d+|0)$' OR NULLIF(TRIM(payment_mode), '') IS NULL OR TRIM(payment_mode) NOT IN ('COD', 'Credit Card', 'Debit Card', 'NetBanking', 'UPI') OR NULLIF(TRIM(order_status), '') IS NULL OR TRIM(order_status) NOT IN ('Delivered', 'Cancelled', 'Returned', 'Pending', 'In Transit') OR (NULLIF(TRIM(delivery_days), '') IS NOT NULL AND TRIM(delivery_days) !~ '^\d+$'))::numeric / (SELECT COUNT(*) FROM orders)) * 100
),
weighted AS (
    SELECT table_name, ROUND(completeness * 0.30 + uniqueness * 0.20 + referential_integrity * 0.30 + conformance * 0.20, 2) AS weighted_score
    FROM table_scores
)
SELECT scope, score_0_100 FROM (
    SELECT 'Overall' AS scope, ROUND(AVG(weighted_score), 2) AS score_0_100 FROM weighted
    UNION ALL
    SELECT table_name AS scope, weighted_score AS score_0_100 FROM weighted
) s
ORDER BY CASE WHEN scope = 'Overall' THEN 0 ELSE 1 END, scope;

-- What the score means to Neha:
-- 90-100: Data is trustworthy for all decisions
-- 70-89: Data usable with caveats (documented in issue log)
-- 50-69: Data needs cleaning before major decisions
-- <50: Data not reliable; investigate root causes

-- Two ways to game the score:
-- 1. Reduce weight of weak dimension: e.g., if conformance is low, lower its weight and raise completeness
-- 2. Relax conformance rules: e.g., accept "N/A" as valid email, making conformance artificially high