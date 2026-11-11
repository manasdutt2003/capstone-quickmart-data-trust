-- Q43: Quantity kinds breakdown (R05 classifications)

SELECT
    SUM(CASE WHEN TRIM(quantity) ~ '^[a-zA-Z]+' THEN 1 ELSE 0 END) AS words,
    SUM(CASE WHEN TRIM(quantity) ~ '^\d*\.\d+$' THEN 1 ELSE 0 END) AS decimals,
    SUM(CASE WHEN TRIM(quantity) = '0' THEN 1 ELSE 0 END) AS zero,
    SUM(CASE WHEN TRIM(quantity) ~ '^-\d+' THEN 1 ELSE 0 END) AS negative,
    SUM(CASE WHEN TRIM(quantity) = '' THEN 1 ELSE 0 END) AS empty_count,
    COUNT(
        *) FILTER (
        WHERE TRIM(quantity) ~ '^[a-zA-Z]+'
        OR TRIM(quantity) ~ '^\d*\.\d+$'
        OR TRIM(quantity) = '0'
        OR TRIM(quantity) ~ '^-\d+'
        OR TRIM(quantity) = ''
    ) AS bad_total
FROM orders;
