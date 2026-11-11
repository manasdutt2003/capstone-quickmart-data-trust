-- Q120: completed line values exposed with no raw columns
-- View projects only allowed columns; the parity test asserts no query
-- over it returns raw unit_price_paid text. Rerun-safe.

CREATE OR REPLACE VIEW v_completed_line_values AS
SELECT
    order_id,
    customer_id,
    product_id,
    order_date,
    city_std,
    category_std,
    status_std,
    payment_std,
    order_month,
    line_value
FROM trusted_enriched
WHERE
    status_std = 'Delivered'
    AND line_value IS NOT NULL;

SELECT
    order_id,
    customer_id,
    product_id,
    order_date,
    city_std,
    category_std,
    status_std,
    payment_std,
    order_month,
    line_value
FROM v_completed_line_values
ORDER BY order_id;
