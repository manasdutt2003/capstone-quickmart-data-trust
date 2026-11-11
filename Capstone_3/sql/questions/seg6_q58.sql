-- Q58: Highest and lowest value product per city
-- PARTITION BY + FIRST_VALUE/LAST_VALUE, tie handling

WITH city_product_value AS (
    SELECT
        city_std,
        category_std,
        SUM(line_value) AS total_value
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
    GROUP BY city_std, category_std
),
ranked AS (
    SELECT
        city_std,
        category_std,
        total_value,
        FIRST_VALUE(category_std) OVER (
            PARTITION BY city_std
            ORDER BY total_value DESC, category_std
        ) AS highest_product,
        LAST_VALUE(category_std) OVER (
            PARTITION BY city_std
            ORDER BY total_value DESC, category_std
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS lowest_product,
        ROW_NUMBER() OVER (PARTITION BY city_std ORDER BY total_value DESC, category_std) AS rn_desc,
        ROW_NUMBER() OVER (PARTITION BY city_std ORDER BY total_value ASC, category_std) AS rn_asc
    FROM city_product_value
)
SELECT DISTINCT
    city_std,
    highest_product,
    lowest_product
FROM ranked
WHERE rn_desc = 1 OR rn_asc = 1
ORDER BY city_std;

-- Tie handling:
-- ORDER BY total_value DESC, category_std ensures deterministic tie-breaking
-- by category name (alphabetical). This is arbitrary but deterministic.
-- Alternative: Use MIN(category_std) in a subquery for ties.
-- The tie rule changes which product appears when multiple products
-- have exactly the same total value for a city.