-- Q14: Missing and malformed customer emails
-- Requires: customers_loaded (staging).
-- Mirrors src/normalise.py::valid_email + src/quality_checks.py:PLACEHOLDERS:
-- empty or placeholder tokens are 'missing'; non-empty non-placeholder
-- addresses failing the EMAIL_RE shape are 'malformed' (quarantined, never
-- imputed); the flagged row cross-checks QC_CUST_EMAIL_INVALID (57).
-- Expected reading: 42 missing (32 empty + 10 placeholder) + 15 malformed
-- = 57 flagged; 463 usable.

WITH tokens (token) AS (
    VALUES ('NA'), ('N/A'), ('na'), ('n/a'), ('-'), ('--'), ('unknown'),
           ('UNKNOWN'), ('Unknown'), ('null'), ('NULL'), ('None'),
           ('none'), ('?'), ('MISSING'), ('missing')
),

classified (email_class) AS (
    SELECT
        CASE
            WHEN COALESCE(TRIM(raw_email), '') = '' THEN 'empty'
            WHEN TRIM(raw_email) IN (SELECT token FROM tokens)
                THEN 'placeholder'
            WHEN TRIM(raw_email)
                 ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'
                THEN 'usable'
            ELSE 'malformed'
        END
    FROM customers_loaded
)

SELECT email_class, row_count
FROM (
    SELECT
        email_class,
        COUNT(*) AS row_count,
        CASE email_class
            WHEN 'empty' THEN 1
            WHEN 'placeholder' THEN 2
            WHEN 'malformed' THEN 3
            ELSE 5
        END AS sort_key
    FROM classified
    GROUP BY email_class
    UNION ALL
    SELECT 'flagged (QC email invalid)',
           COUNT(*) FILTER (WHERE email_class <> 'usable'),
           4
    FROM classified
) AS t
ORDER BY sort_key;
