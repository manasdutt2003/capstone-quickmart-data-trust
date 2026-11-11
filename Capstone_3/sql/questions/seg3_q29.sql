-- Q29: Delivered left after dedup
-- Requires: quality_datamart (staging; 6,103 cleaned rows in file order).
-- Delivered value = quantity x unit_price_paid on the cleaned columns
-- (missing -> 0), before vs after the D01 keep-first removal over the 10
-- business columns in source-row order (mirrors seg3_q20.sql). Commission
-- mirrors reports/deduplication_report.md: line value = round(parsed
-- quantity x parsed price x (1 - parsed discount), 2) on the parsed raw
-- columns, commission = round(0.08 x line value, 2) per row - before on
-- all 6,103 rows, after on the 6,000 kept ones (cleaned columns). The
-- top-3 check re-ranks city/category/month by delivered value on both
-- sides. Expected reading: 1,803 -> 1,769 rows, value 4,542,010 ->
-- 4,524,250 (removed 17,760), commission 1,266,157.90 -> 1,258,401.62
-- (leakage 7,756.28), 6,103 = 6,000 + 103, every top-3 position unchanged.

WITH prep AS (
    SELECT
        d.*,
        ROW_NUMBER() OVER (
            PARTITION BY
                COALESCE(d.customer_id, ''), COALESCE(d.product_id, ''),
                COALESCE(d.order_date, ''), COALESCE(d.quantity, ''),
                COALESCE(d.unit_price_paid, ''), COALESCE(d.discount, ''),
                COALESCE(d.payment_mode, ''), COALESCE(d.order_status, ''),
                COALESCE(d.delivery_days, ''), COALESCE(d.notes, '')
            ORDER BY d._source_row::int
        ) AS keep_rn
    FROM quality_datamart AS d
),

strings AS (
    SELECT
        keep_rn,
        LOWER(TRIM(status_std)) AS status_key,
        city_std,
        category_std,
        order_month,
        TRIM(quantity) AS cq,
        TRIM(unit_price_paid) AS cp,
        REPLACE(REPLACE(LOWER(TRIM(discount)), 'percent', ''), '%', '')
            AS cd,
        TRIM(REPLACE(REPLACE(REPLACE(TRIM(raw_quantity), ',', ''),
            '₹', ''), '?', '')) AS rq,
        TRIM(REPLACE(REPLACE(REPLACE(TRIM(raw_unit_price_paid), ',', ''),
            '₹', ''), '?', '')) AS rp,
        REPLACE(REPLACE(LOWER(TRIM(raw_discount)), 'percent', ''), '%', '')
            AS rd
    FROM prep
),

calc AS (
    SELECT
        keep_rn,
        status_key,
        city_std,
        category_std,
        order_month,
        CASE WHEN cq ~ '^[+-]?[0-9]+(\.[0-9]+)?$'
             THEN CAST(cq AS NUMERIC) END AS val_q,
        CASE WHEN cp ~ '^[+-]?[0-9]+(\.[0-9]+)?$'
             THEN CAST(cp AS NUMERIC) END AS val_p,

        -- parse_int mirror on the raw quantity (parse_float, integers only)
        CASE
            WHEN rq = ''
              OR UPPER(rq) IN ('NA', 'N/A', 'NULL', 'NONE', 'UNKNOWN')
            THEN NULL
            WHEN rq ~ '^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$'
             AND CAST(rq AS NUMERIC) = TRUNC(CAST(rq AS NUMERIC))
            THEN CAST(rq AS NUMERIC)
        END AS r_q,

        -- parse_float mirror on the raw price
        CASE
            WHEN rp = ''
              OR UPPER(rp) IN ('NA', 'N/A', 'NULL', 'NONE', 'UNKNOWN')
            THEN NULL
            WHEN rp ~ '^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$'
            THEN CAST(rp AS NUMERIC)
        END AS r_p,

        -- parse_discount_frac mirror on the raw discount (None -> 0 later)
        CASE
            WHEN TRIM(rd) IN ('', 'na', 'n/a', 'null', 'none', 'unknown')
            THEN NULL
            WHEN TRIM(REPLACE(rd, ',', ''))
                 ~ '^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$'
            THEN CASE
                WHEN CAST(TRIM(REPLACE(rd, ',', '')) AS NUMERIC) < 0
                THEN NULL
                WHEN CAST(TRIM(REPLACE(rd, ',', '')) AS NUMERIC) <= 1
                THEN CAST(TRIM(REPLACE(rd, ',', '')) AS NUMERIC)
                ELSE CAST(TRIM(REPLACE(rd, ',', '')) AS NUMERIC) / 100
            END
        END AS r_d,

        -- same three mirrors on the cleaned columns (commission after)
        CASE
            WHEN cq = ''
              OR UPPER(cq) IN ('NA', 'N/A', 'NULL', 'NONE', 'UNKNOWN')
            THEN NULL
            WHEN cq ~ '^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$'
             AND CAST(cq AS NUMERIC) = TRUNC(CAST(cq AS NUMERIC))
            THEN CAST(cq AS NUMERIC)
        END AS c_q,
        CASE
            WHEN cp = ''
              OR UPPER(cp) IN ('NA', 'N/A', 'NULL', 'NONE', 'UNKNOWN')
            THEN NULL
            WHEN cp ~ '^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$'
            THEN CAST(cp AS NUMERIC)
        END AS c_p,
        CASE
            WHEN TRIM(cd) IN ('', 'na', 'n/a', 'null', 'none', 'unknown')
            THEN NULL
            WHEN TRIM(REPLACE(cd, ',', ''))
                 ~ '^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$'
            THEN CASE
                WHEN CAST(TRIM(REPLACE(cd, ',', '')) AS NUMERIC) < 0
                THEN NULL
                WHEN CAST(TRIM(REPLACE(cd, ',', '')) AS NUMERIC) <= 1
                THEN CAST(TRIM(REPLACE(cd, ',', '')) AS NUMERIC)
                ELSE CAST(TRIM(REPLACE(cd, ',', '')) AS NUMERIC) / 100
            END
        END AS c_d
    FROM strings
),

rows_calc AS (
    SELECT
        keep_rn,
        status_key,
        city_std,
        category_std,
        order_month,
        val_q,
        val_p,
        CASE
            WHEN r_q IS NULL OR r_p IS NULL THEN 0
            ELSE ROUND(r_q * r_p * (1 - COALESCE(r_d, 0)), 2)
        END AS lv_raw,
        CASE
            WHEN c_q IS NULL OR c_p IS NULL THEN 0
            ELSE ROUND(c_q * c_p * (1 - COALESCE(c_d, 0)), 2)
        END AS lv_clean
    FROM calc
),

metrics AS (
    SELECT
        COUNT(*) FILTER (WHERE status_key = 'delivered') AS del_before,
        COUNT(*) FILTER (WHERE status_key = 'delivered'
                           AND keep_rn = 1) AS del_after,
        COALESCE(SUM(CASE WHEN status_key = 'delivered'
            THEN CASE WHEN val_q IS NULL OR val_p IS NULL THEN 0
                      ELSE val_q * val_p END END), 0) AS val_before,
        COALESCE(SUM(CASE WHEN status_key = 'delivered' AND keep_rn = 1
            THEN CASE WHEN val_q IS NULL OR val_p IS NULL THEN 0
                      ELSE val_q * val_p END END), 0) AS val_after,
        COUNT(*) AS orders_before,
        COUNT(*) FILTER (WHERE keep_rn = 1) AS orders_after,
        COALESCE(SUM(ROUND(lv_raw * 0.08, 2)), 0) AS comm_before,
        COALESCE(SUM(CASE WHEN keep_rn = 1
            THEN ROUND(lv_clean * 0.08, 2) END), 0) AS comm_after
    FROM rows_calc
),

dim_rows AS (
    SELECT
        1 AS dim_ord, 'cities' AS dim_name,
        COALESCE(city_std, '(null)') AS dim_val, keep_rn, status_key,
        CASE WHEN val_q IS NULL OR val_p IS NULL THEN 0
             ELSE val_q * val_p END AS v
    FROM rows_calc
    UNION ALL
    SELECT
        2, 'categories', COALESCE(category_std, '(null)'), keep_rn,
        status_key,
        CASE WHEN val_q IS NULL OR val_p IS NULL THEN 0
             ELSE val_q * val_p END
    FROM rows_calc
    UNION ALL
    SELECT
        3, 'months', COALESCE(order_month, '(null)'), keep_rn, status_key,
        CASE WHEN val_q IS NULL OR val_p IS NULL THEN 0
             ELSE val_q * val_p END
    FROM rows_calc
),

dim_sums AS (
    SELECT
        dim_ord, dim_name, dim_val,
        COALESCE(SUM(v) FILTER (WHERE status_key = 'delivered'), 0)
            AS v_before,
        COALESCE(SUM(v) FILTER (WHERE status_key = 'delivered'
                                AND keep_rn = 1), 0) AS v_after
    FROM dim_rows
    GROUP BY dim_ord, dim_name, dim_val
),

ranked AS (
    SELECT
        dim_ord, dim_name, dim_val,
        ROW_NUMBER() OVER (
            PARTITION BY dim_ord
            ORDER BY v_before DESC, dim_val COLLATE "C"
        ) AS rn_before,
        ROW_NUMBER() OVER (
            PARTITION BY dim_ord
            ORDER BY v_after DESC, dim_val COLLATE "C"
        ) AS rn_after
    FROM dim_sums
),

rank_changes AS (
    SELECT
        rb.dim_ord, rb.dim_name,
        COUNT(*) FILTER (WHERE rb.dim_val IS DISTINCT FROM ra.dim_val)
            AS changed
    FROM ranked AS rb
    JOIN ranked AS ra
      ON ra.dim_ord = rb.dim_ord AND ra.rn_after = rb.rn_before
    WHERE rb.rn_before <= 3
    GROUP BY rb.dim_ord, rb.dim_name
)

SELECT scope, measure, row_count
FROM (
    SELECT 'delivered rows' AS scope, 'before dedup' AS measure,
           del_before AS row_count, 1 AS scope_ord, 1 AS sort_key
    FROM metrics
    UNION ALL
    SELECT 'delivered rows', 'after dedup', del_after, 1, 2 FROM metrics
    UNION ALL
    SELECT 'delivered rows', 'removed by D01',
           del_before - del_after, 1, 3
    FROM metrics
    UNION ALL
    SELECT 'delivered value', 'before dedup', val_before, 2, 1
    FROM metrics
    UNION ALL
    SELECT 'delivered value', 'after dedup', val_after, 2, 2
    FROM metrics
    UNION ALL
    SELECT 'delivered value', 'removed by D01',
           val_before - val_after, 2, 3
    FROM metrics
    UNION ALL
    SELECT 'commission', 'before dedup', comm_before, 3, 1 FROM metrics
    UNION ALL
    SELECT 'commission', 'after dedup', comm_after, 3, 2 FROM metrics
    UNION ALL
    SELECT 'commission', 'leakage', comm_before - comm_after, 3, 3
    FROM metrics
    UNION ALL
    SELECT 'reconciliation', 'orders before', orders_before, 4, 1
    FROM metrics
    UNION ALL
    SELECT 'reconciliation', 'orders after', orders_after, 4, 2
    FROM metrics
    UNION ALL
    SELECT 'reconciliation', 'removed by D01',
           orders_before - orders_after, 4, 3
    FROM metrics
    UNION ALL
    SELECT 'top-3 rank changes', dim_name, changed, 5, dim_ord
    FROM rank_changes
) AS t
ORDER BY scope_ord, sort_key, measure;
