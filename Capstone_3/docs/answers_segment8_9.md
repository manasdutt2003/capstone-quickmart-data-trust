# Answers Segment 8–9 (Q76–Q125)

## Shared definitions (named once, used consistently)

- **completed** = `status_std = 'Delivered'` AND `line_value IS NOT NULL`
  on `trusted_enriched` (Sprint-3 lenient population, 522 rows).
- **trusted (any-status)** = lenient set without the status filter; used
  only where the question needs sequencing/identity (Q79, Q80, Q83, Q93,
  Q94-ordering, Q98, Q101, Q102, Q108, Q110, Q117, Q119): stated per
  question below.
- **Ties** break by `order_id COLLATE "C"` (ascending unless stated).
- **Months** are `YYYY-MM` text; money is 2 dp; NULL means "no value",
  never 0, unless stated.
- No PII in outputs/docs: ids only, notes never printed, no
  name/email/phone.

## Segment 8 — Expert SQL engineering

### Q76 — LATERAL latest-payment vs window/DISTINCT ON under ties
PROOF BY COUNTEREXAMPLE on a crafted tied pair
(`O-TIE`, `2024-01-01`, UPI vs COD): DISTINCT ON
(`ORDER BY payment_mode`) and `ROW_NUMBER` (same ordering) both pick COD
deterministically and agree. A `LATERAL ... LIMIT 1` with no `ORDER BY`
is arbitrary on the tie, so the rewrite is NOT equivalent under ties.
Equivalent iff the ordering is total (unique key last). Past the size
threshold the planner switches the LATERAL to a hashed/merged per-group
scan, which surfaces the arbitrariness as a plan change.

### Q77 — Float money sums in two accumulation orders
Per city, `SUM(line_value::float8 ORDER BY order_id)` ascending vs
descending: 7 cities, all diffs 0.00 — no cent-level difference on this
data at these magnitudes. Mechanism proven by crafted counterexample:
`(0.1+0.2)+0.3 = 0.6000000000000001` vs `0.1+(0.2+0.3) = 0.6`
(addition is commutative, not associative). Order-independence via
NUMERIC accumulation, a pre-sort, or `math.fsum`; costs are sort time,
slower exact arithmetic, and still-binary output respectively.

## Segment 9 — Expert SQL on the QuickMart data

### Q78 — Monthly completed value per city + MoM
97 city-months. `LAG` over each city's own months; a missing prior month
yields NULL, never 0. Each city's first month is NULL by construction.

### Q79 — Median gap between consecutive orders
292 customers on trusted (any-status) sequencing; 159 single-order
customers carry NULL `median_gap_days` (no gap exists). 0 would claim
same-day reordering and corrupt medians.

### Q80 — Three most recent orders all non-Delivered
20 customers under `ROW_NUMBER (order_date DESC, order_id DESC)`;
date-only ordering also gives 20 — the tie rule changes 0 customers
here (ties exist but not inside any top-3 window that flips the verdict).

### Q81 — Top-NTILE(10%) share per category
6 categories (Beverages 84.62%, Dairy & Eggs 78.31%, Grocery 75.98%,
Household 100.00% single product, Snacks 20.87%, UNKNOWN 41.39%).
NTILE assigns by row position, so tied values split across bucket edges
and the top share depends on the product_id tiebreak; <10-product
categories get fewer effective buckets.

### Q82 — Longest zero-order run
576 days, 2022-06-06 to 2024-01-02. Recursive calendar left-joined to
daily counts; a run is a maximal zero-count block, bounded where the
count returns to >=1. The gap is real sparsity, not missing data.

### Q83 — Jan–Jun 2026 but not Jul–Oct 2026 (EXCEPT vs NOT EXISTS)
89 customers under both methods (178 rows with method labels; empty
customer_ids excluded both sides). EXCEPT dedups and treats NULLs as
equal; NOT EXISTS correlates with `=` (NULL never matches, so a NULL id
is kept by NOT EXISTS but collapsed by EXCEPT). No NULL ids here, so
both agree; with a NULL present, NOT IN would empty the answer while
NOT EXISTS stays correct.

### Q84 — Second-highest completed order value per city
7 cities (e.g. Bengaluru 5700.00, Chennai 1920.00), 1 order each at the
value. DENSE_RANK DESC rank 2 shares across duplicates; ROW_NUMBER would
pick one arbitrary order at that value. No duplicates here, so both agree.

### Q85 — Discount-implied price gaps, top 5
Bare numbers read as fractions, `%` forms as hundredths; blanks and
unparseable discounts excluded. Top: O00661/P16 and O01766/P21 (implied
1333.33 vs 1200.00, gap 133.33). Under the percent reading
(0.1 = 0.1%) implied prices collapse onto paid and the top-5 reshuffles
toward high-discount lines.

### Q86 — Three most recent completed orders per customer as an array
126 customers; 1 has a same-date tie inside its top-3 window, resolved
by order_id DESC. Without the tiebreak the third slot is arbitrary and
reruns can differ.

### Q87 — GROUPING SETS city/category/grand
32 cells, grand 118820.50; city subtotals, category subtotals and grand
reconcile. `GROUPING() = 1` marks subtotal rows vs true NULLs (0).

### Q88 — Products above own median monthly qty every active month
47 products evaluated, 0 satisfy it (every product has at least one
month at/below its own median — expected: the median splits each
product's months). A global median would compare bulk staples against
slow movers and flip the list.

### Q89 — Rolling 90-day distinct customers per city
486 city-date rows with exact distinct counts plus the RANGE row-count
diagnostic. RANGE frames the right day span but `COUNT(*)` counts rows,
not customers; ROWS would count fixed row offsets regardless of date
gaps and differs on sparse cities.

### Q90 — First-order-month cohorts, 6-month retention
86 cohort-offset rows; late cohorts are right-censored (fewer offsets,
e.g. 2026-10 shows offset 0 only). Shares divide by the full cohort.

### Q91 — Orders above city p95 delivery_days
City p95 flags 4 orders (O02735/Pune 45d, O03699/UNMAPPED 45d,
O03499/O04095/UNKNOWN 6-7d); global p95 flags 2; 2 orders change.
Delivery managers use the city bar (local reality), not the global one.

### Q92 — Duplicate customers by normalised email
0 pairs share an email — empty is the correct answer (no normalised
email repeats). Same phone with different emails would still not be
merge-safe: phones are shared/reused (family, typos) and prove nothing
without name+signup agreement.

### Q93 — Distinct categories in the last 180 data days
100 customers; window [2026-04-14, 2026-10-11] inclusive both ends;
boundary-day orders count.

### Q94 — Herfindahl of category shares per city
Bengaluru 0.3012 … UNMAPPED 0.4164 (highest concentration); smallest
city by value is UNMAPPED. Dropping it changes no other city's HHI
(each is computed within-city); it only removes its row.

### Q95 — Monthly count rising in 4 consecutive months
0 customers — empty is the correct answer (no 3-rise streak exists).
LAG month counts with gaps-and-islands over qualifying months is
required; pairwise-only comparison flags any single rise, not a
sustained 4-month run.

### Q96 — Paid >10% above catalogue (correlated subquery)
7 orders (e.g. O03157/P08 150.00 vs 120.00). One catalogue price per
order via scalar subquery; a plain join would double-count if products
held duplicate product_id rows (none do; guarded by dedup-first).

### Q97 — Monthly value + 3M MA + YoY per category
90 rows. Self-join on month minus 12; the first 12 months show NULL YoY
(no prior year exists), never 0.

### Q98 — Latest order of a product used a new payment_mode
495 pairs across 290 customers under (order_date, order_id) ordering;
order_id-only tiebreak gives 494 — differs for 1 pair.

### Q99 — Top two DENSE_RANKs per city with ties
14 rows; every city returns exactly 2 here (no rank-1/2 ties in this
data). Tied ranks would share and push a city over two.

### Q100 — Two same-category products, same customer+date
0 pairs — empty is the correct answer (no such basket in completed
orders). Canonical ordering (a < b) counts each pair once. Genuine
baskets would show distinct products/quantities; duplicates would show
identical rows (see D01/D02) or empty notes.

### Q101 — Mean delivery_days by payment x status
20 cells; NULLs excluded from both mean and count (AVG skips NULLs).
Highest-mean cell: UNMAPPED/UNMAPPED at 4.32 days (n=59).

### Q102 — First customers to a 10th trusted order
0 — empty is the correct answer (nobody reaches 10 trusted orders).
`earlier_n = 9` via ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING;
ties break by customer_id then order_id.

### Q103 — Products never in a completed order (NOT IN vs NOT EXISTS)
P-10, P02, P19 under both methods (6 rows with labels). NOT IN is
poisoned by a NULL in the set (demo branch with one injected NULL
returns 0 rows); NOT EXISTS stays correct. No NULL product_ids in the
data, so both agree.

### Q104 — Notes mentioning delivery problems vs late share
7 cities (e.g. Bengaluru 11.00% mention / 40.00% late, median 4.0d).
Late = strictly above the city median (the median itself is on-time).
Mention = case-insensitive delay|late|damage|broken|wrong|missing|never|
not deliver.

### Q105 — Most expensive product per customer (LATERAL vs FIRST_VALUE)
126 customers; lateral and FIRST_VALUE agree on all rows given the
shared (price DESC, product_id ASC) tiebreak. Without it both are
arbitrary among equal prices.

### Q106 — One completed CTE, three aggregates, reconciled
Grand 118820.50 = city sum = category sum (reconciled = 1). A
later-edited view would silently fork the three cuts with no failing
join to catch it.

### Q107 — First month above own average monthly count
47 products; 41 never exceed their own average (flat sellers whose
counts never clear the mean).

### Q108 — Same-customer orders in prior 30d, both engines
522 orders; correlated [d-30, d] counts equal the RANGE frame minus
self on every row. Naive variants disagree on boundary days: `< d`
drops same-day peers, `<= d-30` vs `< d-30` flips the 30th day.

### Q109 — Customer avg qty beyond 2 SD of customer averages
0 outliers before and 0 after excluding out-of-range quantities (table
has both stage rows). STDDEV_POP; exclusion shrinks SD, so borderline
customers can flip either way.

### Q110 — Normalised ids in one source only
21 rows split by direction (orders_only / customers_only). orders_only
ids have no city (city lives in customers), so city-level answers
silently drop them; customers_only ids never ordered.

### Q111 — Category share shift >5pp between range halves
Split at the midpoint of [min, max] date (second half takes the odd
day). Movers: UNKNOWN +12.31pp, Grocery −12.11pp.

### Q112 — Top-5 product pairs, same customer+date
1 pair: P08 × P17 (n=1). Canonical ordering (a < b) counts each
unordered pair once; without it every pair double-counts.

### Q113 — Above-p90 cancel/return rate, min 5 orders
1 customer (C0196, n=5, rate 0.80; p90 = 0.66). Minimum-5 filter first:
filtering after would let 1-order 100%-cancel customers set the bar.

### Q114 — Units per product per month via SUM(quantity)
383 rows. SUM never expands rows; recursive unit-row expansion is
O(units) memory for an identical total and can only differ through
float rounding or bad-quantity handling.

### Q115 — Months with fewer distinct completed cities than prior
12 months. COUNT(DISTINCT) cannot sit in a window frame portably, so
the distinct count is a subquery and LAG runs over its months.

### Q116 — Gini of completed value per city
Bengaluru 0.6328 (most unequal) … Hyderabad 0.3335. Assumes
non-negative values, one observation per customer. Near 1 = one
customer takes nearly everything: target them, diversify the rest.

### Q117 — Most-frequent vs most-recent payment_mode
51 differ under (count DESC, payment ASC); reversed name tiebreak gives
47 — differs for 4 customers.

### Q118 — Delivery_days bands per city + shares
26 city-band rows. NULL, negative and >7 values sit in
outside_or_invalid (counted, never averaged away).

### Q119 — Signup-month cohort with shortest median lag
2024-08 at 54.0 days (34 cohorts). Negative lags (first order before
signup) excluded from medians and counted.

### Q120 — Completed-values view with no raw columns
View `v_completed_line_values` projects 10 allowed columns only; the
parity test asserts no query over it returns raw unit_price_paid text.
It cannot prove the base table is protected (grants, replicas, logs
still expose it).

### Q121 — City × category combos with no completed orders
10 combos. Missing cells are zero, not absent. Structural vs data gap:
a combo present in all-status orders but absent in completed is a
fulfilment gap; absent everywhere is structural/assortment.

### Q122 — Rank-1 monthly qty within category, ≥3 months
10 products (P-30 ×16 … P29 ×3). DENSE_RANK ties share rank 1, so tied
months add every tied product; ROW_NUMBER would keep one and shrink
the list.

### Q123 — Customers buying every catalogue category
0 — empty is the correct answer (nobody covers all categories) under
both NOT EXISTS division and HAVING COUNT(DISTINCT). Blank/UNMAPPED
categories are ignored by division but can corrupt the HAVING total;
no blanks here, so both agree.

### Q124 — Monthly >5% off-catalogue share; doubling flagged
55 month-category rows. Lines with no catalogue price excluded from the
rate. Doubling = share ≥ 2× prior month; NULL prior never flags (note:
0→0 months flag degenerately since 0 ≥ 2×0 — read them as flat, not
spikes).

### Q125 — Top-3 cities + top category + shares (mega query)
Bengaluru 54365.75 (UNKNOWN 42.04%), Pune 18233.25 (Dairy & Eggs
38.12%), Chennai 16758.50 (Grocery 42.05%). 4 CTEs + window rank +
LATERAL top category + GROUPING SETS subtotals + rejected-ids
anti-join. At 10× rows the per-city sort spills past work_mem first,
then the self-join.
