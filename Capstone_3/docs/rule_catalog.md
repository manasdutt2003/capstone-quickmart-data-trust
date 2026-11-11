# Rule catalog (generated — do not edit by hand)

Generated from `src.validation_rules.REGISTRY` by `python -m src.gen_rule_catalog` over 6000 cleaned order lines.

| rule_id | name | predicate | fields | files joined | severity | treatment | rationale | failing count |
|---|---|---|---|---|---|---|---|---|
| R01 | Customer Exists | customer_id exists in the customer master | customer_id | orders, customers | FAIL | set_aside | Unmatched customer ids cannot attribute value to anyone. | 198 (matched_exact:5530, matched_normalised:272, unmatched_after_normalisation:198) |
| R02 | Product Exists | product_id exists in the product master | product_id | orders, products | FAIL | set_aside | Unmatched product ids cannot attribute value to anything. | 159 (matched_exact:5551, matched_normalised:290, unmatched_after_normalisation:159) |
| R03 | Customer Signup Before Order | customer signup_date <= order_date | customer_id, signup_date, order_date | orders, customers | FAIL | set_aside | Orders before signup imply a wrong date on one side. Rows whose customer is unmatched are NOT evaluated here: they return PASS with failing_detail='skipped_due_to_R01' (NOT_EVALUATED is forbidden) and are counted. Duplicate customer rows resolve to the Sprint 2 D03 survivor (earliest signup). Same-day orders pass. | 1851 (signup_ok:3951, order_before_signup:1312, unparseable_order_date:277) |
| R04 | Valid Order Date | order_date is parseable and not after TODAY | order_date | orders | FAIL | set_aside | Future dates are typing errors, scheduled orders or wrong years. Upper bound is TODAY (2026-10-11, inclusive); lower bound is the earliest signup_date in the customer master (no order predates the business's first signup), inclusive, derived per input. | 833 (ok:5167, after_today:457, unparseable_order_date:286) |
| R05 | Valid Quantity | quantity is a positive whole number | quantity | orders | FAIL | set_aside | Zero, negative or fractional quantities cannot ship. Bad values are classified separately (word/decimal/empty/zero/negative) via the raw_quantity mirror. Implausible highs use an IQR fence (Q3 + 3*IQR, computed on the input; value equal to the fence passes); the 99th percentile was rejected as it collapses onto the pathological 500-spike and flags nothing. | 718 (ok:5282, not_positive:zero:247, invalid:empty:168) |
| R06 | Valid Price | unit_price_paid is positive and near the catalogue price | product_id, unit_price_paid, discount | orders, products | FAIL | set_aside | Net paid (price*(1-discount)) must be within 10% of catalogue (R06_PRICE_TOLERANCE; 5% run rejected: inside discount-rounding and catalogue-staleness noise yet still nukes the headline). No catalogue price means UNVERIFIABLE, hence WARNING, not FAIL. | 5450 (outside_tolerance:4374, unverifiable:no_catalogue_price:814, within_tolerance:550) |
| R07 | Valid Discount | discount parses to a fraction in 0..1 | discount | orders | WARNING | flag | Fraction-vs-percent rule finalised here: (0,1] fractions (bare 1 counts separately), (1,100] percentages, else FAIL. Severity stays WARNING (treatment flag-for-correction); only truly unusable discounts FAIL the check outcome. | 561 (fraction:zero:2231, percentage:2142, invalid:unparseable:561) |
| R08 | Valid Status | order_status is not MISSING or UNMAPPED | order_status | orders | FAIL | set_aside | Unknown status cannot decide revenue membership. | 623 (ok:5377, missing_status:623) |
| R09 | Valid Payment | payment_mode passes the mapping gate | payment_mode | orders | WARNING | flag | Unknown payment does not invalidate the order event (customer, product, date and value stay verifiable); it only limits payment-behaviour answers, so WARNING not FAIL. FAIL alternative would set aside every UNMAPPED/MISSING-payment row from Q4. | 1198 (ok:4802, unmapped_payment:640, missing_payment:558) |
| R10 | Valid Delivery Days | delivery_days is an integer in 0..30 for Delivered | order_status, delivery_days | orders | WARNING | flag | Upper bound 30: brief-stated and data-consistent (genuine values all <= 7; only the planted 45-spike exceeds it). Cancelled rows with positive days are WARNING (suspicious metadata, but the cancellation itself stands). | 1623 (no_delivery_rule_for_status:2433, ok:1944, cancelled_with_delivery_days:1548) |
| R11 | Inventory Feasibility | quantity does not exceed recorded stock_qty | product_id, quantity | orders, products | WARNING | flag | Stock is a point-in-time snapshot that cannot be time-aligned to order dates, so it can never hard-gate: WARNING only. Products with unusable stock are skipped with a count, not failed. | 185 (skipped_unusable_stock:3015, ok:2669, insufficient_stock:185) |
| R12 | Cross-field Business Rule | delivered/cancelled/signup invariants hold together | order_status, order_date, delivery_days, signup_date, customer_id | orders, customers | FAIL | set_aside | Sub-conditions R12a (delivered not future), R12b (delivered has days), R12c (cancelled has no positive days), R12d (signup not after TODAY), each counted. R12c-only violations stay WARNING for consistency with R10-cancelled. | 1704 (ok:4296, R12c:cancelled_positive_days:1529, R12a:future_delivered_date:121) |

## Thresholds and alternatives (quantified)

### R05 implausible-high threshold

Chosen: IQR fence Q3+3*IQR = 13, flagging 76 rows (the 500-quantity spike). Alternative: 99th percentile (500), flagging 0 rows — it collapses onto the spike value itself and discriminates nothing. IQR wins.

### R06 price tolerance

Chosen: 10% -> {'FAIL': 4636, 'WARNING': 814, 'PASS': 550}; line value kept Rs 1,696,401.5. Alternative 5% -> {'FAIL': 4766, 'WARNING': 814, 'PASS': 420}; kept Rs 1,554,650.0. 5% sits inside discount-rounding and catalogue-staleness noise yet still nukes the headline, so 10% is recommended.

### R07 fraction-vs-percent rule

Canonical (0,1]-fraction/(1,100]-percent: 2753 fraction rows, 2142 percent rows; line-value sum Rs 14,677,735.25. Swapped rule sum Rs -64,263,229.3 (percent rows go negative) — the opposite rule destroys value accounting, so canonical stands.

### R10 delivery upper bound

Chosen: 30 days (brief-stated and data-consistent: genuine values all <= 7, only an 18-row spike at 45 exceeds it; p99 33.6). Alternative no-cap (data max 45): 0 rows flagged vs 18 at the cap. The cap stands.

### R12c cancelled-positive-days consequence

Chosen: R12c-only violations stay WARNING (1529 rows, consistent with R10-cancelled). Alternative FAIL would set aside those rows from trusted orders entirely.
