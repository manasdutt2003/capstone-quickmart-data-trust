-- 05_marts.sql : sales/customer/payment/delivery/cohort + GROUPING SETS
-- Grain stated per mart; all sums reconcile to trusted delivered total.
-- Distinguish subtotal rows with GROUPING().
SELECT
    COALESCE(city_std, '(ALL)') AS city,
    COALESCE(category_std, '(ALL)') AS category,
    SUM(line_value) AS total_value,
    GROUPING(city_std, category_std) AS g
FROM trusted_enriched
WHERE status_std = 'Delivered'
GROUP BY
    GROUPING SETS ((city_std, category_std), (city_std), (category_std), ());
