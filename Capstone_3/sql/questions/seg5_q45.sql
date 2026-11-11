-- Q45: Future dates (post TODAY)
-- TODAY is read from v_run_params (single SQL home of the reference date).

WITH parsed AS (
    SELECT
        CASE
            WHEN order_date ~ '^\d{4}-\d{2}-\d{2}$' THEN order_date
            WHEN
                order_date ~ '^\d{2}/\d{2}/\d{4}$'
                THEN
                    substr(order_date, 7, 4)
                    || '-'
                    || substr(order_date, 1, 2)
                    || '-'
                    || substr(order_date, 4, 2)
            WHEN order_date ~ '^\d{2}-\w{3}-\d{2}$'
                THEN
                    '20' || substr(order_date, 8, 2) || '-'
                    || CASE substr(order_date, 4, 3)
                        WHEN 'Jan' THEN '01' WHEN 'Feb' THEN '02' WHEN
                            'Mar'
                            THEN '03'
                        WHEN 'Apr' THEN '04' WHEN 'May' THEN '05' WHEN
                            'Jun'
                            THEN '06'
                        WHEN 'Jul' THEN '07' WHEN 'Aug' THEN '08' WHEN
                            'Sep'
                            THEN '09'
                        WHEN 'Oct' THEN '10' WHEN 'Nov' THEN '11' WHEN
                            'Dec'
                            THEN '12'
                    END || '-' || substr(order_date, 1, 2)
            WHEN
                order_date ~ '^\d{2}\.\d{2}\.\d{4}$'
                THEN
                    substr(order_date, 7, 4)
                    || '-'
                    || substr(order_date, 4, 2)
                    || '-'
                    || substr(order_date, 1, 2)
        END AS dt
    FROM orders
    WHERE order_date <> ''
)

SELECT count(*) AS future_rows
FROM parsed
WHERE dt > (SELECT v.today::TEXT FROM v_run_params AS v);

-- Monthly clustering
WITH parsed AS (
    SELECT
        CASE
            WHEN
                order_date ~ '^\d{4}-\d{2}-\d{2}$'
                THEN substr(order_date, 1, 7)
            WHEN
                order_date ~ '^\d{2}/\d{2}/\d{4}$'
                THEN substr(order_date, 7, 4) || '-' || substr(order_date, 1, 2)
            WHEN order_date ~ '^\d{2}-\w{3}-\d{2}$'
                THEN
                    '20' || substr(order_date, 8, 2) || '-'
                    || CASE substr(order_date, 4, 3)
                        WHEN 'Jan' THEN '01' WHEN 'Feb' THEN '02' WHEN
                            'Mar'
                            THEN '03'
                        WHEN 'Apr' THEN '04' WHEN 'May' THEN '05' WHEN
                            'Jun'
                            THEN '06'
                        WHEN 'Jul' THEN '07' WHEN 'Aug' THEN '08' WHEN
                            'Sep'
                            THEN '09'
                        WHEN 'Oct' THEN '10' WHEN 'Nov' THEN '11' WHEN
                            'Dec'
                            THEN '12'
                    END
            WHEN
                order_date ~ '^\d{2}\.\d{2}\.\d{4}$'
                THEN substr(order_date, 7, 4) || '-' || substr(order_date, 4, 2)
        END AS ym
    FROM orders
    WHERE
        order_date <> ''
        AND (
            CASE
                WHEN order_date ~ '^\d{4}-\d{2}-\d{2}$' THEN order_date
                WHEN
                    order_date ~ '^\d{2}/\d{2}/\d{4}$'
                    THEN
                        substr(order_date, 7, 4)
                        || '-'
                        || substr(order_date, 1, 2)
                        || '-'
                        || substr(order_date, 4, 2)
                WHEN order_date ~ '^\d{2}-\w{3}-\d{2}$'
                    THEN
                        '20' || substr(order_date, 8, 2) || '-'
                        || CASE substr(order_date, 4, 3)
                            WHEN 'Jan' THEN '01' WHEN 'Feb' THEN '02' WHEN
                                'Mar'
                                THEN '03'
                            WHEN 'Apr' THEN '04' WHEN 'May' THEN '05' WHEN
                                'Jun'
                                THEN '06'
                            WHEN 'Jul' THEN '07' WHEN 'Aug' THEN '08' WHEN
                                'Sep'
                                THEN '09'
                            WHEN 'Oct' THEN '10' WHEN 'Nov' THEN '11' WHEN
                                'Dec'
                                THEN '12'
                        END || '-' || substr(order_date, 1, 2)
                WHEN
                    order_date ~ '^\d{2}\.\d{2}\.\d{4}$'
                    THEN
                        substr(order_date, 7, 4)
                        || '-'
                        || substr(order_date, 4, 2)
                        || '-'
                        || substr(order_date, 1, 2)
            END
        ) > (SELECT v.today::TEXT FROM v_run_params AS v)
)

SELECT
    ym,
    count(*) AS n
FROM parsed
GROUP BY ym
ORDER BY ym;
