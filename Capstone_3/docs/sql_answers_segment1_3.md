# SQL answers: Segments 1-3 (loading & shape, completeness, identity & duplicates)

Short plain-English answers for the SQL artifacts backing Q1-Q29. Each entry
names the query (`sql/questions/segN_qNN.sql`), the saved result
(`data/SQL_OUTPUTS/qNN.csv`, mirrored in `data/output/`) and the headline
number(s). Numbers are recomputed independently in pandas from the same
source files before an entry is written; nothing is estimated or typed by
hand. Saved results render NULL/NaN as empty cells and are masked
(customer ids -> `C-<sha1:6>`; emails never output).

Where a check is a file/loader-level property that the SQL layer cannot
see, the entry is marked **BLOCKED** with the exact reason and no SQL file
or dump is created (never a faked query).

## Segment 1 - Loading and shape (Q1-Q9)

### Q1 - Rows per extract vs rows loaded
`seg1_q1.sql` -> `q1.csv`. The cleaned frames hold **520 customers, 30
products and 6,103 order lines** - identical to `rows_in_file` in
`data/raw_manifest.json`, so no loaded row was dropped (the blank-line
filter never fired).

### Q2 - Column names kept verbatim
`seg1_q2.sql` -> `q2.csv`. Loaded columns match the expected header spec in
both name and order for all three tables: **6/6 customers, 5/5 products,
11/11 orders, 0 mismatches** - source headers are used verbatim at load.

### Q3 - Text that a typed read would mangle
`seg1_q3.sql` -> `q3.csv`. All values stay text. Quantity keeps `-2` (111
rows), `0` (251), `2.5` (62), `three` (57), `500` (77) and blanks (170);
discount keeps 8 raw forms (`NA` 576, `5%` 557, `20 percent` 539, `10%`
531, `0.1` 529, `0` 2,271, blanks 551); product `unit_price` keeps rupee
forms ₹210/₹60, `1,200`, `210.00` and `NA`. Full inventory: 32
forms in `q3.csv`.

### Q4 - Row-length audit - **BLOCKED** (loader-level)
Field count per row is a parsing-time property; the SQL layer sees parsed
columns only, so there is deliberately no SQL file or dump for Q4. The
audit lives in `data/raw_manifest.json`: `row_length_dist` =
`{6: 520, 5: 30, 11: 6,103}` (zero short or long rows), produced by
`src/data_loader.py::row_length_audit`. Re-checked: the manifest counts
equal the loaded counts.

### Q5 - Leading zeros and id variants
`seg1_q5.sql` -> `q5.csv`. Odd spellings survive load and collapse
losslessly through `norm_id`. Customers: 8 trailing-space, 19 lower-case, 4
dashed ids (500 distinct spellings -> 500 distinct ids). Orders: 94 spaced,
476 lower-case, 38 dashed customer ids (693 -> 482 distinct); 1,019
`P-21`-form + 38 `P--10`-form + 178 lower-case product ids (1,235 rows
rewritten); `order_id` itself shows zero variants - all `O0####`, leading
zeros kept. 19-row table in `q5.csv`.

### Q6 - Date values changed on load
`seg1_q6.sql` -> `q6.csv`. Shapes are classified in the loader's format
order (ISO first, then day-first `DD/MM/YYYY` before month-first).
Orders: 1,151 already ISO, 4,662 changed (`DD/MM/YYYY` 2,290,
`DD.MM.YYYY` 1,237, `DD-Mon-YY` 1,135 with all 12 month tokens present,
64-116 each), 290 unparseable (180 blank + 110 `unknown`). Customers:
108 already ISO, 387 changed (`DD/MM/YYYY` 194, `DD.MM.YYYY` 82,
`DD-Mon-YY` 111), 25 unparseable (11 blank + 14 `unknown`). One day-first
read is visible end to end: raw `01/11/2026` -> `2026-11-01` (order
O00004). 10-row table in `q6.csv`.

### Q7 - Encoding and non-ASCII characters
`seg1_q7.sql` -> `q7.csv`. The decoded content carries exactly one
non-ASCII character, the rupee sign, and nothing else: orders 125
occurrences in 125 rows (all in `unit_price_paid`), products 3
(`unit_price`), customers 0. Encoding detection (all three files decode
as UTF-8, no BOM) and the cp1252 misread demo are loader-level and stay
outside SQL. 3-row table in `q7.csv`.

### Q8 - Quotes and commas inside notes
`seg1_q8.sql` -> `q8.csv`. Standard CSV quoting kept embedded specials
inside the field: 2,265 notes are empty, 2,141 contain a comma, 545 a
double quote, and 0 both - and none split a row (loader-level field-count
audit: 0 short/long rows). 4-row table in `q8.csv`.

### Q9 - Double load / SHA determinism - **BLOCKED** (loader-level)
Double-load determinism and source-file SHA-256 hashes are file-level
properties; the SQL layer sees only loaded rows, so there is deliberately
no SQL file or dump for Q9. Evidence lives in `data/raw_manifest.json`:
each extract's recorded `sha256` matches a fresh hash of the raw file
(customers `fce10dec...`, products `a0878195...`, orders `03a9482a...`),
`encoding` is `utf-8` for all three, and `rows_in_file` == `rows_loaded`
(520 / 30 / 6,103) - re-loading the same bytes yields the same tables.
Re-checked on every batch-2 verification run.

## Segment 2 - Completeness (Q10-Q19)

### Q10 - Empty vs placeholder cells per customer column
`seg2_q10.sql` -> `q10.csv`. Using the 16-token placeholder set from
`src/quality_checks.py::PLACEHOLDERS` (empty and placeholder both count as
missing): customer_id 0/0 (0 missing); customer_name 20/0 (20); email
32/10 (42, matches `profile.csv`); city 39/0 (39); phone 109/0 (109);
signup_date 11/14 (25). The only placeholder tokens present are `N/A`
(10, email) and `unknown` (14, signup_date). 6-row table in `q10.csv`.

### Q11 - Placeholders per orders column and their clustering
`seg2_q11.sql` -> `q11.csv`. Placeholders exist in only three columns:
discount 576, order_date 110, unit_price_paid 68. Missing totals: notes
2,265; discount 1,127 (551 empty + 576 placeholder); order_status 629;
payment_mode 564; order_date 290 (180 + 110); unit_price_paid 267
(199 + 68); quantity 170; delivery_days 142; customer_id 60; product_id
54; order_id 0. Missingness is spread across the timeline (rows without
a usable date fall in a `(no date)` bucket): the worst month bucket
holds 4.4-6.3% of the missing total for the six big columns, and 5.9-9.3%
for the three small ones - no process-fault window, so it reads as
sporadic entry omission. order_date itself has no usable month, so it
cannot be bucketed. 11-row table in `q11.csv`.

### Q12 - Most-empty orders column; notes vs status
`seg2_q12.sql` -> `q12.csv`. `notes` is the most-empty orders column:
2,265 rows (37.11%), ahead of discount 1,127 (18.47%), order_status 629
(10.31%), payment_mode 564 (9.24%), order_date 290 (4.75%),
unit_price_paid 267 (4.37%), quantity 170 (2.79%), delivery_days 142
(2.33%), customer_id 60 (0.98%), product_id 54 (0.88%), order_id 0
(0.00%). Empty notes are uniform across statuses - Delivered 655/1,803
(36.3%), Cancelled 709/1,828 (38.8%), In Transit 223/602 (37.0%),
Pending 237/623 (38.0%), Returned 220/618 (35.6%), blank status 221/629
(35.1%) - so `notes` is an optional free-text field, not a workflow
signal; KPI scope simply excludes missing cells and reports coverage.
17-row table in `q12.csv`.

### Q13 - Empty prices by month and product
`seg2_q13.sql` -> `q13.csv`. 267 empty prices (4.37% of 6,103) spread
thinly: worst month 2024-11 with 12 (4.5%), worst product P25 with 14
(5.2%), near the uniform expectation of ~8.9 per product - no month or
product carries an unusual share. 11 of the empties sit on rows whose
order_date is itself unusable (`(no date)`). 89-row table in `q13.csv`.

### Q14 - Missing and malformed emails
`seg2_q14.sql` -> `q14.csv`. Of 520 email cells: 32 empty + 10
placeholder (`N/A`) = 42 missing; 15 malformed rows (14 distinct
spellings, e.g. `arjunshettymail.com` without `@`); flagged total 57 =
QC_CUST_EMAIL_INVALID; 463 usable. Placeholders are excluded from
contactability rather than imputed, and malformed addresses are
quarantined - no email is guessed. 5-row table in `q14.csv`.

### Q15 - Missing and text prices
`seg2_q15.sql` -> `q15.csv`. Of the 30 catalogue prices: 24 plain
numbers; 4 written in text form that still parses once the symbol/comma
is stripped - `₹60` (P-10), `₹210` (P13, P25), `1,200` (P21); and 2
unusable `NA` (P-26, P-30) = QC_PROD_PRICE_INVALID (2). The 28 parseable
prices stay usable; the two `NA` prices stay null with coverage noted.
4-row table in `q15.csv`.

### Q16 - Never-empty columns vs columns above 10% missing
`seg2_q16.sql` -> `q16.csv`. Across the 22 audited columns (customers 6,
products 5, orders 11): four never empty - orders.order_id 0/6,103,
customers.customer_id 0/520, products.product_id and products.product_name
0/30. Five sit above 10% missing: stock_qty 12/30 (40.00%), notes
2,265/6,103 (37.11%), phone 109/520 (20.96%), discount 1,127/6,103
(18.47%), order_status 629/6,103 (10.31%) - payment_mode 9.24% just below.
Each gap limits one specific analysis (stock, notes, contactability,
discounting, status), so those metrics must publish coverage. 22-row table
in `q16.csv`.

### Q17 - Empty delivery_days by status
`seg2_q17.sql` -> `q17.csv`. 142 empty delivery_days cells (2.33% of 6,103)
are spread evenly across statuses: Delivered 39/1,803 (2.16%), Cancelled
37/1,828 (2.02%), In Transit 18/602 (2.99%), Pending 24/623 (3.85%),
Returned 13/618 (2.10%), blank status 11/629 (1.75%). Delivered sitting at
the same rate as every other status rules out a workflow rule (e.g. empties
only for undelivered orders) - it is entry omission; delivery metrics use
the 5,961 valued rows. 7-row table in `q17.csv`.

### Q18 - Co-empty column pairs
`seg2_q18.sql` -> `q18.csv`. 45 of the 55 order-column pairs co-miss at
least once; the strongest pairs all involve optional fields:
discount+notes 408, order_status+notes 221, payment_mode+notes 218,
discount+order_status 128, discount+payment_mode 104, order_date+notes 99,
unit_price_paid+notes 88, order_date+discount 60 - one cause explains the
tail (rows captured with minimal information leave optional cells blank
together; single-column totals: notes 2,265; discount 1,127; status 629;
payment 564). The required identity columns never co-miss materially
(order_id none; customer_id+product_id once), so no systemic capture fault
needs modelling. 45-row table in `q18.csv`.

### Q19 - Unusable stock per category
`seg2_q19.sql` -> `q19.csv`. 16 of 30 products have usable stock; 14
(46.7%) are unusable = 12 missing (empty/placeholder) + 2
parseable-but-invalid (negative or non-integer) - matching
QC_PROD_STOCK_INVALID 14. Per category (case/spacing variants grouped):
Grocery 7/10 usable (3 missing), Snacks 4/9 (4 missing, 1 bad), Dairy & Eggs
2/4 (2 missing), Beverages 0/3 (2 missing, 1 bad), Dairy 1/2 (1 missing),
Household 1/1, blank category 1/1. Category roll-ups are partial (Beverages
0/3) and must publish coverage; an overall stock total would understate and
is not produced. 8-row table in `q19.csv`.

## Segment 3 - Identity and duplicates (Q20-Q29)

### Q20 - Repeated order_ids
`seg3_q20.sql` -> `q20.csv`. 103 repeated order_ids cover 206 rows;
conflicting groups 0 - every repeat is an exact copy on all business
columns, so the D02 priority-survivor path (Delivered > In Transit > Pending
> Returned > Cancelled > blank) stays unexercised. D01 keep-first removes
103 copies; QC_ORD_ID_DUP flags 206 rows. Removed-copy statuses (cleaned):
Delivered 34, Cancelled 30, Pending 14, Returned 10, In Transit 9, blank
(cleaned marker `MISSING`) 6 - repeats span all statuses, marking system
double-writes rather than one workflow stage. 11-row table in `q20.csv`.

### Q21 - Which columns differ across duplicate copies
`seg3_q21.sql` -> `q21.csv`. Across the 103 repeated order_id groups,
every one of the 11 columns (order_id + the 10 business columns) shows 0
differing groups - not even order_id or notes. The copies are
byte-identical double-writes, so no corrections are hidden in the
duplicates and keep-first removal never discards edited data (the D02
priority path stays unexercised). 11-row table in `q21.csv`.

### Q22 - Repeated customers: same person?
`seg3_q22.sql` -> `q22.csv`. D03 groups customers by normalised email
(lower + strip; placeholder emails never merge) and keeps the earliest
signup_date (tie: lower id): 21 merges = 20 same-id repeat registrations
+ 1 cross-id merge (C0242 -> C0196, shared email), taking the register
from 520 rows to a 499-row master; every loser carries its shared-email
evidence in `duplicate_registry.csv`. 6-row table in `q22.csv`.

### Q23 - Case/spacing/dash customer id variants
`seg3_q23.sql` -> `q23.csv`. norm_id = strip + UPPER + remove spaces and
dashes. It changes 23 customer rows' form (19 lower-case ids `c00xx` +
4 dashed ids `C-01xx`; the 8 trailing-space ids were already trimmed in
the clean layer) while distinct ids stay 500 before and after - no
customer is double-counted by spelling; on the order side 693 raw
spellings collapse to 482 normalised ids. The only count reduction in the
register (520 -> 499) comes from D03 email merges, not normalisation.
5-row table in `q23.csv`.

### Q24 - Customers with and without orders
`seg3_q24.sql` -> `q24.csv`. Master ids are matched against normalised
order-side customer ids, with the cross-id D03 remap applied (same-id
remaps are identity): master 499 = 479 with orders + 20 without; 482
order-side ids, 5,899 order rows attach. The only unresolved rows: 144
unknown-id rows (C9999, quarantined by R01) + 60 blanks
(6,103 = 5,899 + 144 + 60) - nothing else is unresolved. 8-row table in
`q24.csv`.

### Q25 - Shared email addresses
`seg3_q25.sql` -> `q25.csv`. 21 shared-email groups each needed a merge
decision (21 extra rows merged); 42 emails were excluded from grouping
(32 empty + 10 placeholder `N/A`), which prevents false merges since many
customers legitimately share blank/sentinel values. Example group:
`anita.gowda218@mail.com` -> C0218 (Bengaluru) + C0218 (Pune); D03's
evidence strings cross-check the same 21 groups. 5-row table in
`q25.csv`.

### Q26 - Shared product names
`seg3_q26.sql` -> `q26.csv`. Product names are compared
case-insensitively across the 30 catalogue rows: 30 rows, 30 distinct
names, 0 names on more than one row - name-level duplicate handling is a
non-issue (D04's name+category+price comparison only activates on
normalised-id collisions). 3-row table in `q26.csv`.

### Q27 - Repeated product_ids
`seg3_q27.sql` -> `q27.csv`. No product_id repeats (0 repeated rows);
five ids are formatting variants (`p09`, `P-10`, `P-20`, `P-26`, `P-30`)
that normalise (strip/upper/drop `-` and spaces) to ids no other row
carries, so D04 never merges and the registry has 0 D04 rows (0 merges,
0 CONFLICT). Product count is unchanged: 30 distinct raw ids = 30
distinct normalised ids = 30 rows after D04. 7-row table in `q27.csv`.

### Q28 - Customers with several cities
`seg3_q28.sql` -> `q28.csv`. The 21 shared-email groups (case-folded
key, 9-token placeholder emails excluded) are compared on the raw city
spelling: 18 groups have differing cities, dropping 18 occurrences
across 8 case-insensitive raw spellings (Pune 5, Bengaluru 4, chennai 2,
BLR 2, Mysuru 2, Madras 1, bengaluru 1, Hyderabad 1) - single digits per
city, so no city disappears. The keeper (earliest raw signup_date, then
raw customer_id, then file order) keeps its city: master 499 = Bengaluru
195, Chennai 106, Pune 80, Hyderabad 47, MISSING 37, Mysuru 34. 19-row
table in `q28.csv`.

### Q29 - Delivered left after dedup
`seg3_q29.sql` -> `q29.csv`. Removing the 103 D01 duplicates takes 34
delivered rows and 17,760 of delivered value (quantity x
unit_price_paid, missing -> 0, cleaned basis: 4,542,010 -> 4,524,250,
0.39%), plus 7,756.28 of commission (1,266,157.90 -> 1,258,401.62,
0.61%; per-row round(line_value x 0.08, 2) with line_value =
round(qty x price x (1 - discount), 2) on the parsed raw vs cleaned
columns). Reconciliation: 6,103 = 6,000 + 103. The top-3 cities,
categories and months by delivered value keep the same order before and
after (rank changes 0/0/0), so the conclusion-change statement is: none.
15-row table in `q29.csv`.
