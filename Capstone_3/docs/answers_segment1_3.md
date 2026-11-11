# Answers: Segments 1-3 (Loading and Shape / Completeness / Identity and Duplicates)

These 29 answers supply the ledger's missing sub-parts (`reason: ... prose not
written` in `docs/question_ledger.md`). Every count below is read from the
current files (raw extracts, cleaning outputs, quality registry, dedup registry,
reports); nothing is estimated. Ledger status flips and dashboard result
payloads are a separate step and are not made by this document.

Source extracts (pinned in `data/raw_manifest.json`):
`Resources/Capstone Questions/Capstone 2/data/{customers,products,orders}.csv`.

---

## Segment 1 — Loading and shape (Q1–9)

### Q1 — Rows per extract vs rows loaded

**Method (2 sentences):**
`load_raw` parses every file with `csv.reader` and returns `(header, rows)`;
`write_manifest` records `rows_in_file` and `rows_loaded` from that same pass,
so the comparison is like-for-like per table.

**Decision & reason:**
No data row is dropped — the only filter removes fully blank lines, and none
exist; the header is validated, not counted as data. The difference is 0 for all
three extracts, and the manifest keeps both numbers so a future drop cannot go
unnoticed.

**Code:** `src/data_loader.py::load_raw`, `write_manifest`; `data/raw_manifest.json`; `data/profile.csv`

**Result:** customers 520 = 520; products 30 = 30; orders 6,103 = 6,103;
blank lines skipped 0; rows delivered to cleaning 6,103.

---

### Q2 — Odd column names kept verbatim

**Method (2 sentences):**
`load_raw` compares each file header to `EXPECTED_HEADERS[table]` and raises
`ValueError` on mismatch; `write_manifest` stores the header verbatim for audit.

**Decision & reason:**
Column names are kept exactly as the extract writes them — no rename at load. A
mismatch is fail-fast, never a silent mapping, so if a source renames a column
the pipeline stops instead of guessing at the data.

**Code:** `src/data_loader.py::EXPECTED_HEADERS`, `load_raw`

**Result:** headers match exactly 3/3 — customers (6 columns), products (5),
orders (11); odd names found: none; each header recorded verbatim in the
manifest.

---

### Q3 — Numeric-looking text columns

**Method (2 sentences):**
The loader keeps every cell as text (csv module, list-of-dicts;
`dtype=str, keep_default_na=False` when profiling), so no type inference happens
at load; a typed read was compared column-by-column on the raw forms to list
where inference would disagree.

**Decision & reason:**
Text is the preservation layer and coercion happens only in the normalisation
helpers (`parse_float`, `parse_int`, `parse_date`, `parse_discount_frac`), so
leading zeros, currency symbols, '%' and mixed date formats can never be mangled
by dtype guessing. Disagreeing columns (a naive typed read would change them):
orders — `order_id` (leading zeros `O00007`), `customer_id`/`product_id`
(case/dash/space variants), `order_date` (mixed formats), `quantity`
(`-2`, `''`, `2.5`), `unit_price_paid` (rupee-symbol forms, `NA`), `discount`
(`10%`, `15`, `20 percent`, `NA`), `delivery_days`, `payment_mode`,
`order_status`; customers — `customer_id`, `phone` (111 values start with `0`),
`signup_date`; products — `product_id`, `unit_price` (`₹60`, `1,200`, `NA`),
`stock_qty` (`NA`).

**Code:** `src/data_loader.py` (module docstring, `load_raw`); `src/normalise.py` parsers

**Result:** quantity texts: `-2` x111, `0` x251, `2.5` x62, blank x170;
discount has 7 distinct forms (`0`, `NA`, `5%`, `15`, `20 percent`, `10%`,
`0.1`); rupee sign x128 across files (125 order prices, 3 product prices);
phone leading zeros preserved x111; all values survive load unchanged.

---

### Q4 — Short/long order rows

**Method (2 sentences):**
`row_length_audit` counts fields per parsed row and the manifest stores the
distribution per table; a row broken by quoting would show a length different
from its header.

**Decision & reason:**
No short or long rows exist — the standard CSV quoting rules inside
`csv.reader` keep every logical row intact. The audit is a permanent guard: a
malformed row cannot pass unnoticed in future loads.

**Code:** `src/data_loader.py::row_length_audit`; `data/raw_manifest.json::row_length_dist`

**Result:** customers {6: 520}, products {5: 30}, orders {11: 6,103};
short rows 0, long rows 0; quoting-caused splits 0.

---

### Q5 — Leading zeros and spaces in ids

**Method (2 sentences):**
Id values carrying spaces, lower case or dashes are counted per column;
`norm_id` (strip, UPPER, remove spaces/dashes) shows the canonical form. One
example per class demonstrates preservation at load and canonicalisation at join
time.

**Decision & reason:**
Raw ids stay verbatim in the extracts (audit trail) and joins use `norm_id` —
variants like `C-0176` and `c0010` resolve without editing the source. Leading
zeros survive because values are text; nothing is integerised.

**Code:** `src/data_loader.py` (text load); `src/normalise.py::norm_id`

**Result (customers):** trailing-space ids 8 (`C0032 `, `C0140 `, `C0203 `),
lower-case ids 19 (`c0010`), dash ids 4 (`C-0176`, `C-0197`, `C-0308`,
`C-0445`), rows changed by normalisation 23, distinct ids 500 before = 500
after. (Orders): `customer_id` — 94 rows with spaces (`C0140 `), 476 lower case
(`c0108`), 38 dashed; `product_id` — 1,019 dashed (`P-21`), 178 lower case
(`p09`); `order_id` — 0 variants (all `O0####`, leading zeros kept). Examples:
`norm_id('C-0176') = 'C0176'`; `norm_id(' p09 ') = 'P09'`.

---

### Q6 — Dates changed on load

**Method (2 sentences):**
`parse_date` tries the ordered 8-format list and then an ISO fallback; counts
compare raw strings against their parsed ISO form to separate changed values
from unparseable ones.

**Decision & reason:**
Day-first conventions are tried before month-first (`%d/%m/%Y` precedes
`%m/%d/%Y`), so ambiguous strings follow the Indian convention — raw
`01/11/2026` is read day-first as 1 Nov 2026 (visible in `quality_datamart`
row O00004).
Unparseable dates are quarantined, never guessed.

**Code:** `src/normalise.py::parse_date`, `DATE_FORMATS`; `data/quality_datamart.csv`

**Result (orders, 6,103):** already ISO 1,151; changed 4,662; unparseable 290
(QC_ORD_DATE_INVALID). Main changed families: DD/MM/YYYY 2,290, DD.MM.YYYY
1,237, DD-Mon-YY (98–116 per month token, all 12 present). (customers, 520):
already ISO 108; changed 387; unparseable 25 (QC_CUST_SIGNUP_UNPARSEABLE).

---

### Q7 — File encodings

**Method (2 sentences):**
`detect_encoding` checks a UTF-8 BOM, then strict UTF-8, falling back to cp1252;
a byte-level scan lists every non-ASCII character per file, and a misread test
decodes bytes as cp1252.

**Decision & reason:**
UTF-8 is tried before cp1252, so the rupee sign decodes correctly; cp1252 stays
only as a legacy fallback. No accent misreads are possible here (none exist),
and `parse_float` defensively strips the rupee sign and commas so decoded symbol
forms still parse.

**Code:** `src/data_loader.py::detect_encoding`; `data/raw_manifest.json::encoding`

**Result:** all three files decode as plain UTF-8 (no BOM); non-ASCII:
customers 0, products 3 x `₹`, orders 125 x `₹` (all in `unit_price_paid`);
accents 0. Misread test: read as cp1252, each `₹` (3 UTF-8 bytes) becomes
`â‚¹` mojibake — 125 garbled prices in orders.csv; the UTF-8-first policy
prevents that.

---

### Q8 — Quotes inside notes

**Method (2 sentences):**
`csv.reader` handles quoting; the check counts notes containing commas or double
quotes and re-audits row lengths — a quoting failure shows up as a wrong field
count.

**Decision & reason:**
Embedded commas and quotes are handled by standard CSV quoting (`""` escaping)
rather than custom splitting, and the row-length audit proves no affected row
misaligned.

**Code:** `src/data_loader.py::load_raw`, `row_length_audit`

**Result:** notes with commas 2,141; notes with double quotes 545; notes empty
2,265; rows with a wrong field count 0 (all 6,103 rows exactly 11 fields) — no
row split or merged by quoting.

---

### Q9 — Loading the same file twice

**Method (2 sentences):**
`load_raw` was run twice per extract and `sha256_of` twice per file in one
session; row counts and hashes were compared (live demonstration, not a
by-construction claim).

**Decision & reason:**
Extracts are immutable, content-addressed inputs: the manifest pins file,
SHA-256, encoding, header and row counts, and reloading is idempotent — same
bytes give same rows and same hash. Reruns therefore reproduce identical state;
there is no sampling or randomness anywhere in loading.

**Code:** `src/data_loader.py::load_raw`, `sha256_of`, `write_manifest`

**Result:** load1 == load2 rows: 520 / 30 / 6,103; SHA-256 stable: customers
`fce10dec...`, products `a0878195...`, orders `03a9482a...` (full hashes in
`data/raw_manifest.json`).

---

## Segment 2 — Completeness (Q10–19)

### Q10 — Empty vs placeholder cells per customer column

**Method (2 sentences):**
`is_missing_or_placeholder` separates empty cells from the 16-token placeholder
set (`NA`, `N/A`, `-`, `--`, `unknown`, `null`, `None`, `?`, `MISSING` and case
variants); counts are produced per customer column.

**Decision & reason (placeholder-definition statement):**
A placeholder is not a value — it is treated exactly like an empty cell by every
downstream rule and profile, and only its count is kept so a badly supplied
column stays visible. "Missing" means empty + placeholder everywhere in this
project.

**Code:** `src/quality_checks.py::PLACEHOLDERS`, `is_missing_or_placeholder`; `data/issue_registry.csv`

**Result (empty / placeholder):** customer_id 0/0; customer_name 20/0; email
32/10 (=42 missing, matches `profile.csv`); city 39/0; phone 109/0;
signup_date 11/14 (=25). QC cross-checks: name 20, email 57 invalid
(incl. malformed), city 39, signup 25, id duplicates 40 rows.

---

### Q11 — Placeholders in orders and their clustering

**Method (2 sentences):**
Per-column empty vs placeholder counts come from the raw extract; missing values
are then bucketed by order month and the worst month's share of each column's
missing total is measured.

**Decision & reason (most-column + clustering + process fault):**
Placeholders exist in only three columns — `discount` 576, `order_date` 110,
`unit_price_paid` 68 — and missingness is spread across the whole timeline (no
month holds more than 6.3% of any column's missing values). There is no
process-fault window; this reads as sporadic entry omission, handled per column
with reported coverage, not by excluding months.

**Code:** `src/quality_checks.py`; `data/quality_datamart.csv`; `data/profile.csv`

**Result:** order_date 180 empty + 110 placeholder (=290); unit_price_paid
199+68 (=267); discount 551+576 (=1,127); payment_mode 564 empty; order_status
629; delivery_days 142; notes 2,265; customer_id 60; product_id 54; quantity
170. Clustering (missing, month-buckets, worst month): unit_price_paid 267 over
49, max 12 (4.5%); discount 1,127 over 62, max 60 (5.3%); payment_mode 564 over
53, max 28 (5.0%); order_status 629 over 52, max 32 (5.1%); delivery_days 142
over 40, max 9 (6.3%); notes 2,265 over 76, max 99 (4.4%); order_date — 290
unparseable, so no month bucket is possible.

---

### Q12 — Most-empty orders column

**Method (2 sentences):**
Missing share per orders column is read from `profile.csv`; the two plausibly
workflow-driven columns (`notes`, `delivery_days`) are then compared across
statuses as within-status shares.

**Decision & reason (share + status-dependence finding):**
`notes` is the most-empty column at 37.11%, but its emptiness is uniform across
statuses (35–39% each) — it is an optional free-text field, not a workflow
signal. `delivery_days` is equally status-independent (missing in Delivered rows
too), so KPI scope simply excludes missing cells and reports coverage.

**Code:** `data/profile.csv`; `data/quality_datamart.csv`

**Result:** notes 2,265 (37.11%) > discount 1,127 (18.47%) > order_status 629
(10.31%) > payment_mode 564 (9.24%) > order_date 290 (4.75%) > unit_price_paid
267 (4.37%) > quantity 170 (2.79%) > delivery_days 142 (2.33%) >
customer_id 60 (0.98%) > product_id 54 (0.88%) > order_id 0. Notes-empty by
status: Delivered 655/1,803 (36.3%), Cancelled 709/1,828 (38.8%), In transit
223/602 (37.0%), Pending 237/623 (38.0%), Returned 220/618 (35.6%), blank
status 221/629 (35.1%).

---

### Q13 — Empty prices by month/product

**Method (2 sentences):**
The 267 empty `unit_price_paid` cells are bucketed by order month and by
product_id to see how the empties spread across the calendar and catalogue.

**Decision & reason (month/product comparison + unusual-share note):**
No month or product carries an unusual share — the worst month holds 12 (4.5%)
and the worst product 14 (5.2%) of the 267 empties, near the uniform expectation
(~8.9 per product). The one pattern worth noting: 11 empties sit in rows whose
order_date is also unusable — both fields absent together.

**Code:** `data/quality_datamart.csv`; `data/profile.csv`

**Result:** total 267 (4.37% of 6,103). By month: 2024-11 12, 2024-04 11,
no-date 11, 2024-02 10, 2024-07 10, 2025-03 10. By product: P25 14, P29 13,
P-26 12, P01 12, P-10 12, P12 12.

---

### Q14 — Missing and placeholder emails

**Method (2 sentences):**
Emails are split into two groups — missing/placeholder (empty or a placeholder
token) and format-invalid (non-empty, non-placeholder, failing the `@` rule) —
and reconciled against the QC count.

**Decision & reason (two-group + placeholder rule):**
The 57 flagged rows are 42 missing/placeholder plus 15 malformed. Placeholders
are excluded from contactability rather than imputed, and malformed addresses
are quarantined — no email is guessed or derived; normalised email (lower,
strip) is used only for D03 identity matching.

**Code:** `src/quality_checks.py` (QC_CUST_EMAIL_INVALID 57); `src/normalise.py::valid_email`, `norm_email`

**Result:** missing 42 (32 empty + 10 placeholder, e.g. `N/A`); malformed 15
(e.g. `arjunshettymail.com` without `@`); flagged total 57; usable 463;
placeholder share of flagged 10.

---

### Q15 — Missing and text prices

**Method (2 sentences):**
The 30 catalogue `unit_price` values are classified as plain number,
numeric-with-text-form (rupee sign or thousands separator), or unusable
(`NA`/blank); QC_PROD_PRICE_INVALID is the cross-check.

**Decision & reason (text-price forms list):**
Four prices are written in text form — `₹60` (P-10), `₹210` (P13, P25),
`1,200` (P21) — and all parse once the symbol/comma is stripped, so they are
usable. The two `NA` values stay null and are the only QC failures; price
comparisons run on the 28 parseable prices with coverage noted.

**Code:** `src/quality_checks.py` (QC_PROD_PRICE_INVALID 2); `src/normalise.py::parse_float`

**Result:** non-numeric texts 6 = text forms 4 (`₹60`, `₹210`, `₹210`,
`1,200`) + unusable 2 (`NA`: P-26 Apple Juice 1L, P-30 Honey 500g); QC
failures 2; pass 28.

---

### Q16 — Never-empty vs >10% empty columns

**Method (2 sentences):**
`profile.csv` missing shares are scanned for columns at exactly 0% and above
10%, across all three tables.

**Decision & reason (meaning for analysis):**
Identifier columns are complete, so joins and row counts are safe. Each >10%
column limits one specific analysis — phone (contactability), stock_qty
(stock reports), discount (read as "no discount"), order_status (segment
coverage), notes (free text) — and must be scoped to non-missing cells with
coverage stated, never silently defaulted.

**Code:** `data/profile.csv`; `data/quality_datamart.csv`

**Result:** never-empty — orders.order_id (6,103), customers.customer_id (520),
products.product_id and products.product_name (30). Above 10% missing —
stock_qty 40.00%, notes 37.11%, phone 20.96%, discount 18.47%, order_status
10.31% (payment_mode 9.24% just below; order_date 4.75%).

---

### Q17 — Empty delivery days by status

**Method (2 sentences):**
Empty `delivery_days` values are grouped by order_status (raw spellings) and
converted to within-status shares so statuses of different sizes compare
fairly.

**Decision & reason (share comparison + matter decision + meaning):**
The 142 empties (2.33%) are spread evenly — every status sits between 1.8% and
3.9%, including `Delivered` — so no status explains them and nothing is learnt
from status. Delivery-time metrics use the 5,961 rows with a value; the pattern
says entry omission, not a workflow rule (cancelled orders are not the cause).

**Code:** `data/quality_datamart.csv`; `data/profile.csv`

**Result:** total 142: Delivered 39/1,803 (2.16%), Cancelled 37/1,828 (2.02%),
In transit 18/602 (2.99%), Pending 24/623 (3.85%), Returned 13/618 (2.10%),
blank status 11/629 (1.75%).

---

### Q18 — Co-empty column pairs

**Method (2 sentences):**
Pair-wise co-emptiness is counted over all order columns (missing = empty or
placeholder) and ranked by pair count.

**Decision & reason (top pairs + single-cause judgement):**
The strongest pairs all involve optional fields (discount, notes, status,
payment) going missing together, and required fields never co-miss in a
material pair — one cause explains the tail: rows captured with minimal
information leave optional cells blank together. No systemic capture fault needs
modelling.

**Code:** `data/quality_datamart.csv`

**Result:** top pairs — discount+notes 408, order_status+notes 221,
payment_mode+notes 218, discount+order_status 128, discount+payment_mode 104,
notes+order_date 99, unit_price_paid+notes 88, discount+order_date 60
(single-column totals: notes 2,265; discount 1,127; status 629; payment 564).

---

### Q19 — Unusable stock per category

**Method (2 sentences):**
`stock_qty` is classified per product (usable number vs missing vs
negative/non-integer) and rolled up per category with spelling variants grouped;
QC_PROD_STOCK_INVALID is the cross-check.

**Decision & reason (per-category shares + stock-report implication):**
14 of 30 products (46.7%) lack usable stock, so a stock report covers only 16
products; category roll-ups are partial (Beverages 0/3 usable) and must publish
coverage — an overall stock total would understate and should not be produced.

**Code:** `src/quality_checks.py` (QC_PROD_STOCK_INVALID 14); `data/quality_datamart.csv`

**Result:** usable 16, unusable 14 (missing 12 + negative/non-integer 2). Per
category: Grocery 7/10 usable (3 missing), Snacks 4/9 (4 missing, 1 bad),
Beverages 0/3 (2 missing, 1 bad), Dairy & Eggs 2/4, Dairy 1/2, Household 1/1,
missing category 1/1.

---

## Segment 3 — Identity and duplicates (Q20–29)

### Q20 — Repeated order_ids

**Method (2 sentences):**
Order-id repeats are counted on the raw extract; each repeat group is tested for
conflicting business values (the D02 case), and the duplicate registry shows
what the pipeline removed (D01).

**Decision & reason (reviewer explanation for non-exact copies):**
Every repeat is an exact copy on all business columns — there are no non-exact
copies to review (conflicts 0). The D02 reviewer path exists (priority survivor:
Delivered > In Transit > Pending > Returned > Cancelled > missing) but is
unexercised; repeats span all statuses, marking them as system double-writes
rather than one workflow stage.

**Code:** `src/deduplication.py::deduplicate_orders` (D01/D02); `data/duplicate_registry.csv`

**Result:** repeated order_ids 103; rows involved 206; conflicting groups 0;
D01 removals 103; QC_ORD_ID_DUP flags 206 rows; removed-copy statuses
(cleaned): Delivered 34, Cancelled 30, Pending 14, Returned 10, In Transit 9,
MISSING 6 (the cleaned marker for a blank raw status).

---

### Q21 — Which columns differ across copies

**Method (2 sentences):**
Within each of the 103 duplicate groups, the number of distinct values is
counted per column (all business columns and order_id), so any differing column
would appear with a non-zero frequency.

**Decision & reason (pattern + corrections-vs-errors judgement):**
No column differs — not even order_id or notes — so the duplicates are
byte-identical copies (capture errors/double-writes). A correction would appear
as one order_id with differing values (D02); there are none, so keep-first
removal never discards edited data.

**Code:** `src/deduplication.py::BUSINESS_COLS` (D01/D02); `data/duplicate_registry.csv`

**Result:** per-column difference frequencies — order_id 0; customer_id 0;
product_id 0; order_date 0; quantity 0; unit_price_paid 0; discount 0;
payment_mode 0; order_status 0; delivery_days 0; notes 0.

---

### Q22 — Repeated customers: same person?

**Method (2 sentences):**
D03 groups customers by normalised email (lower, strip; placeholders never
merge), keeps the earliest signup as survivor, and records every loser with its
evidence; counts are rebuilt from the registry.

**Decision & reason (written rule + kept-count):**
Same normalised email = same person even when id/case/spacing differ; survivor =
earliest signup_date (tie: lower customer_id), and loser ids remap in orders
before order-level dedup. Kept: 520 rows → 499 master rows (21 merged away).

**Code:** `src/deduplication.py::build_customer_master` (D03); `deduplicate_orders` id remap

**Result:** merges 21 = 20 same-id repeat registrations + 1 cross-id merge
(C0242 → C0196, `shared email meenareddymail.com`); master rows 499; every
loser evidenced by shared email in the registry.

---

### Q23 — Case/spacing/dash customer variants

**Method (2 sentences):**
`norm_id` is applied to customer ids; distinct counts and changed-row counts are
compared raw vs normalised, and order-side spellings are counted the same way.

**Decision & reason (rule statement + no-double-count proof):**
The join key is `norm_id` = strip + UPPER + remove spaces/dashes. Normalisation
changes 23 customer rows' form but distinct ids stay 500 before and after — no
customer is double-counted by spelling; the order side's 693 spellings collapse
to 482 ids (variants of the same people). The only count reduction (520 rows →
499) comes from D03 email merges, not from id normalisation.

**Code:** `src/normalise.py::norm_id`; `src/deduplication.py::count_before_after_normalising`

**Result:** customer rows changed by normalisation 23 (`C0032 `→`C0032`,
`c0010`→`C0010`, `C-0176`→`C0176`); distinct raw 500 = distinct normalised
500; order-side customer_id: 693 raw spellings → 482 normalised ids.

---

### Q24 — Customers with and without orders

**Method (2 sentences):**
Master ids are matched against distinct customer ids in the raw orders with both
sides normalised; order-side id groups with no master match are counted with
their row volumes.

**Decision & reason (gap explanation):**
The gap has three parts: 20 customers registered but never ordered (master
without orders); 3 unmatched order-side groups — C9999 (144 rows, unknown id →
quarantined by R01), 14 rows under loser id C0242 (remapped to C0196 by D03 in
the clean layer — 0 remain), and 60 rows with no customer id at all. Nothing
else is unresolved.

**Code:** `src/deduplication.py` (D03 remap); `data/customer_master.csv`; `data/quality_datamart.csv`

**Result:** master 499; with orders 479; without orders 20; order-side ids 482
(479 matched); unmatched — C9999 144 rows, C0242 14 rows (remapped), blank 60
rows.

---

### Q25 — Shared email addresses

**Method (2 sentences):**
Customers are grouped by lowercased email with placeholders excluded; every
group larger than one is a merge decision, and D03's evidence strings
cross-check the same groups.

**Decision & reason (pairs-needing-decision + dependency):**
All 21 groups required a decision and were resolved by the same email rule;
excluding placeholder emails (42) prevents false merges, since many customers
legitimately share `NA`/blank. Dependency: D03 must run before order-level dedup
because remapped ids change D01/D02/D05 matching — rule order is load-bearing.

**Code:** `src/deduplication.py::build_customer_master` (D03); `deduplicate_orders`

**Result:** shared-email groups 21; extra rows merged 21; 20 same-id / 1
cross-id (C0242/C0196); placeholder emails excluded 42 (32 empty + 10
placeholder); example group: `anita.gowda218@mail.com` → C0218 (Bengaluru) +
C0218 (Pune).

---

### Q26 — Shared product names

**Method (2 sentences):**
Product names are compared case-insensitively across rows; D04's comparison
(name + category + price) only activates when normalized ids collide.

**Decision & reason (duplicate-vs-distinct + evidence):**
No two product rows share a name (or a normalised id), so nothing needs merging;
the evidence for the 30 products is 30 distinct names — duplicate-name handling
is a non-issue in this catalogue.

**Code:** `src/deduplication.py::deduplicate_products` (D04)

**Result:** names appearing on more than one row: none; 30 rows, 30 distinct
names; D04 collisions 0.

---

### Q27 — Repeated product_ids

**Method (2 sentences):**
Repeated product_id rows are counted, `norm_id` variants are listed, and the D04
registry is checked for merges or CONFLICT rows.

**Decision & reason (per-repeat action + product-count effect):**
No id repeats, so no per-repeat action was needed; five ids are formatting
variants (`p09`, `P-10`, `P-20`, `P-26`, `P-30`) that normalise to ids not
otherwise present, so they neither merge nor conflict. Product count is
unchanged: 30 → 30.

**Code:** `src/deduplication.py::deduplicate_products` (D04); `data/duplicate_registry.csv`

**Result:** repeated product_ids 0; D04 registry rows 0 (merges 0, CONFLICT 0);
normalised variants 5 (`p09`→P09, `P-10`→P10, `P-20`→P20, `P-26`→P26,
`P-30`→P30); products 30 → 30.

---

### Q28 — Customers with several cities

**Method (2 sentences):**
Shared-email groups are compared on city, loser-city occurrences are counted,
and the master's city values are compared against the raw spelling set.

**Decision & reason (trusted-city decision + city-count effect):**
The survivor's city is trusted (earliest signup) and the loser's city is dropped
— 18 of 21 merges had differing cities, and merged-away occurrences are single
digits per city (Pune 5, Bengaluru 4, chennai 2, BLR 2, Mysuru 2, Madras 1,
bengaluru 1, Hyderabad 1), so no city disappears. Raw spelling variety (8
distinct case-folded spellings: BLR/Bangalore/Bengaluru, Madras/Chennai, ...)
is handled at the standardised layer (`city_std`); the master keeps one city per
survivor.

**Code:** `src/deduplication.py::build_customer_master`; `data/customer_master.csv`

**Result:** groups with differing cities 18/21; dropped occurrences 18; master
cities: Bengaluru 195, Chennai 106, Pune 80, Hyderabad 47, Mysuru 34, MISSING
37 (total 499).

---

### Q29 — Delivered left after dedup

**Method (2 sentences):**
Delivered rows and delivered value (quantity x unit_price_paid, missing → 0)
are recomputed before and after the D01 removal (6,103 → 6,000), and the
commission figures come from the deduplication report.

**Decision & reason (small-amount judgement + conclusion-change statement):**
Removing 103 duplicates takes 34 delivered rows and ₹17,760 of delivered value
(0.39%) plus ₹7,756.28 of commission (0.61%) — below any practical materiality,
so the duplicates are removed without adjusting conclusions. The top three
cities, categories and months by delivered value keep the same order before and
after, so the conclusion-change statement is: none.

**Code:** `src/deduplication.py` (D01); `data/duplicate_registry.csv`; `reports/deduplication_report.md`; `data/quality_datamart.csv`

**Result:** delivered 1,803 → 1,769 rows; delivered value 4,542,010 →
4,524,250 (Δ 17,760); commission 1,266,157.90 → 1,258,401.62 (leakage
7,756.28); reconciliation 6,103 = 6,000 + 103. Top-3 order unchanged (cities:
Bengaluru 1,147,810 > Chennai 873,575 > UNMAPPED 856,790; categories: Grocery
2,054,860 > Snacks 886,690 > Dairy & Eggs 530,115; months: 2025-06 636,250 >
2026-07 510,850 > INVALID 306,675).

---

*Prepared from the current working tree (regeneration is deterministic; the
dashboard payload `dashboard/data.json` is rebuilt by `python -m
src.dashboard_data`). Ledger status flips for Q1–29 happen only after this
document is reviewed.*
