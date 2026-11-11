-- Q87: completed value by city+category with subtotals and grand total
-- GROUPING() = 1 marks subtotal rows; true NULLs would show 0.

WITH completed AS (
    SELECT city_std, category_std, line_value
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
)
SELECT
    city_std,
    category_std,
    ROUND(SUM(line_value), 2) AS total_value,
    GROUPING(city_std) AS g_city,
    GROUPING(category_std) AS g_cat,
    CASE
        WHEN GROUPING(city_std) = 1 AND GROUPING(category_std) = 1
            THEN 'grand'
        WHEN GROUPING(city_std) = 1 THEN 'category'
        WHEN GROUPING(category_std) = 1 THEN 'city'
        ELSE 'cell'
    END AS kind
FROM completed
GROUP BY GROUPING SETS (
    (city_std, category_std),
    (city_std),
    (category_std),
    ()
)
ORDER BY kind, city_std NULLS LAST, category_std NULLS LAST;
