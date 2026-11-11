-- Q101: mean delivery_days by payment_mode x order_status (pivot)
-- NULLs excluded from both mean and count (AVG skips NULLs).

SELECT
    payment_std,
    status_std,
    ROUND(AVG(delivery_days::numeric), 2) AS mean_days,
    COUNT(delivery_days) AS n
FROM trusted_enriched
WHERE delivery_days ~ '^\d+(\.\d+)?$'
GROUP BY payment_std, status_std
ORDER BY mean_days DESC, payment_std, status_std;
