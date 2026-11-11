-- v_line_value.sql : canonical line-value view.
-- Mirrors src/line_value.py (line_value = quantity * unit_price_paid *
-- (1 - discount_frac), 2 dp) and never redefines it. Consumes cleaned
-- fraction-form discount text; null/empty/non-numeric inputs give NULL,
-- never 0. Casts happen only here, behind regex guards (no implicit casts
-- at load: staging is TEXT-only, see 00_staging.sql).
-- Grain: one row per cleaned order line.
CREATE OR REPLACE VIEW v_line_value AS
SELECT
    order_id,
    CASE
        WHEN
            quantity ~ '^[+-]?(\d+\.?\d*|\.\d+)$'
            AND unit_price_paid ~ '^[+-]?(\d+\.?\d*|\.\d+)$'
            AND discount ~ '^[+-]?(\d+\.?\d*|\.\d+)$'
            THEN ROUND(
                CAST(quantity AS NUMERIC)
                * CAST(unit_price_paid AS NUMERIC)
                * (1 - CAST(discount AS NUMERIC)),
                2
            )
    END AS line_value
FROM orders_clean;
