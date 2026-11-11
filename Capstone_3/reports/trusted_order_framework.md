# Trusted order framework

Rules:
- R01 (FAIL): customer_id exists in customer master
- R02 (FAIL): product_id exists in product master
- R03 (FAIL): customer signup_date <= order_date
- R04 (FAIL): order_date is parseable and not future
- R05 (FAIL): quantity is positive integer
- R06 (FAIL): unit_price_paid is non-negative
- R07 (WARNING): discount is parseable and 0-100%
- R08 (FAIL): order_status is not MISSING/UNMAPPED
- R09 (WARNING): delivery_days is 0-30 for Delivered, null/0 for Cancelled
- R10 (WARNING): unit_price_paid within 30% of catalogue price
- R11 (WARNING): payment_mode is not MISSING/UNMAPPED

Trusted=2385 Rejected=3615 Strict=2385
