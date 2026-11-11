-- Q92: customer pairs sharing normalised email + differing columns
-- Same phone with different emails is not merge-safe (shared/typo phones).

WITH normed AS (
    SELECT
        customer_id,
        customer_name,
        LOWER(TRIM(email)) AS email_n,
        city,
        phone,
        signup_date
    FROM customers_master
    WHERE TRIM(email) <> ''
)
SELECT
    a.customer_id AS customer_a,
    b.customer_id AS customer_b,
    a.email_n AS email,
    TRIM(
        CASE WHEN a.customer_name IS DISTINCT FROM b.customer_name
            THEN 'customer_name,' ELSE '' END
        || CASE WHEN a.city IS DISTINCT FROM b.city
            THEN 'city,' ELSE '' END
        || CASE WHEN a.phone IS DISTINCT FROM b.phone
            THEN 'phone,' ELSE '' END
        || CASE WHEN a.signup_date IS DISTINCT FROM b.signup_date
            THEN 'signup_date,' ELSE '' END,
        ','
    ) AS differs_on,
    (
        TRIM(a.phone) <> ''
        AND TRIM(a.phone) = TRIM(b.phone)
    ) AS same_phone,
    (TRIM(a.phone) <> TRIM(b.phone)) AS same_email_diff_phone
FROM normed AS a
JOIN normed AS b
    ON a.email_n = b.email_n
    AND a.customer_id < b.customer_id
ORDER BY customer_a, customer_b;
