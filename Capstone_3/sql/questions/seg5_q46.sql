-- Q46: Discount forms (fraction/percentage/zero/empty/unparseable)

SELECT
    SUM(
        CASE
            WHEN
                TRIM(discount) ~ '^\d*\.\d+$'
                AND CAST(discount AS NUMERIC) > 0
                AND CAST(discount AS NUMERIC) <= 1
                THEN 1
            ELSE 0
        END
    ) AS fraction,
    SUM(
        CASE
            WHEN
                TRIM(discount) ~ '^\d+(\.\d+)?%$'
                THEN 1
            ELSE 0
        END
    ) AS percentage,
    SUM(
        CASE
            WHEN
                TRIM(discount) = '0'
                OR TRIM(discount) = '0%'
                OR TRIM(discount) = '0.0'
                THEN 1
            ELSE 0
        END
    ) AS zero,
    SUM(
        CASE
            WHEN
                TRIM(discount) = ''
                THEN 1
            ELSE 0
        END
    ) AS empty_count,
    SUM(
        CASE
            WHEN
                TRIM(discount) <> ''
                AND TRIM(discount) !~ '^\d*\.\d+$'
                AND TRIM(discount) !~ '^\d+(\.\d+)?%$'
                AND TRIM(discount) NOT IN ('0', '0%', '0.0')
                THEN 1
            ELSE 0
        END
    ) AS unparseable,
    SUM(
        CASE
            WHEN
                TRIM(discount) ~ '^\d*\.\d+$'
                AND (
                    CAST(discount AS NUMERIC) < 0
                    OR CAST(discount AS NUMERIC) > 1
                )
                THEN 1
            ELSE 0
        END
    ) AS out_of_range,
    SUM(
        CASE
            WHEN
                TRIM(discount) = '1'
                THEN 1
            ELSE 0
        END
    ) AS bare_one
FROM orders;
