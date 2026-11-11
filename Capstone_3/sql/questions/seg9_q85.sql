-- Q85: discount-implied catalogue price vs catalogue, top-5 abs gap
-- Bare numbers read as fractions, % forms as hundredths; blanks and
-- unparseable discounts excluded (same rule as the Python twin).

WITH interpreted AS (
    SELECT
        order_id,
        product_id,
        unit_price_paid::numeric AS paid,
        CASE
            WHEN discount ~ '^\d+(\.\d+)?%$'
                THEN SUBSTRING(discount FROM '^(\d+(\.\d+)?)%$')::numeric
                    / 100
            WHEN discount ~ '^\d+(\.\d+)?$'
                THEN discount::numeric
            ELSE NULL
        END AS disc_frac
    FROM trusted_enriched
    WHERE
        status_std = 'Delivered'
        AND line_value IS NOT NULL
        AND unit_price_paid ~ '^\d+(\.\d+)?$'
),
implied AS (
    SELECT
        i.order_id,
        i.product_id,
        ROUND(i.paid / (1 - i.disc_frac), 2) AS implied_price,
        ROUND(p.unit_price::numeric, 2) AS catalogue_price,
        ROUND(ABS(i.paid / (1 - i.disc_frac) - p.unit_price::numeric), 2)
            AS abs_gap
    FROM interpreted AS i
    JOIN products_clean AS p ON p.product_id = i.product_id
    WHERE
        i.disc_frac IS NOT NULL
        AND i.disc_frac < 1
        AND p.unit_price ~ '^\d+(\.\d+)?$'
        AND p.unit_price::numeric > 0
)
SELECT order_id, product_id, implied_price, catalogue_price, abs_gap
FROM implied
ORDER BY abs_gap DESC, order_id COLLATE "C"
LIMIT 5;
