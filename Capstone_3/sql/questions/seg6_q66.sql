-- Q66: GROUPING SETS for totals by category, city, category+city, grand total

SELECT
    category_std,
    city_std,
    SUM(line_value) AS total_value,
    COUNT(*) AS orders,
    GROUPING(category_std) AS is_category_subtotal,
    GROUPING(city_std) AS is_city_subtotal
FROM trusted_enriched
WHERE
    status_std = 'Delivered'
    AND line_value IS NOT NULL
GROUP BY GROUPING SETS (
    (category_std, city_std),  -- detail: category x city
    (category_std),            -- subtotal by category
    (city_std),                -- subtotal by city
    ()                         -- grand total
)
ORDER BY
    GROUPING(category_std), category_std,
    GROUPING(city_std), city_std;

-- Distinguishing true NULL from subtotal:
-- GROUPING() function returns 1 for subtotal rows, 0 for detail rows.
-- True NULL in data would have GROUPING() = 0 for that column.
-- Subtotal row has GROUPING() = 1 for the grouped column(s).

-- Verification: grand total = sum of category subtotals = sum of city subtotals
-- SELECT SUM(CASE WHEN is_category_subtotal = 1 AND is_city_subtotal = 1 THEN total_value END) AS grand
--      SUM(CASE WHEN is_category_subtotal = 1 AND is_city_subtotal = 0 THEN total_value END) AS sum_cat
--      SUM(CASE WHEN is_category_subtotal = 0 AND is_city_subtotal = 1 THEN total_value END) AS sum_city
-- FROM (the above query) t;
-- All three should be equal.