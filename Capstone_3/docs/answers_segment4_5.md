# Answers: Segment 4 (Across the Three Extracts) & Segment 5 (Values and Meaning)

## Q30 — Unmatched customer ids

**Method (2 sentences):**  
Compared two match rules against the customer master: (a) exact stripped match, (b) normalised match (trim, UPPER, remove spaces and dashes via `norm_id`). The rule output distinguishes `matched_exact`, `matched_normalised`, and `unmatched_after_normalisation` so both counts and rescued rows are directly observable.

**Decision & reason:**  
Adopted rule (b). Case and dash variants (e.g., `c-001` vs `C001`) are entry noise; normalisation rescues 279 order lines without inventing customers. The 204 rows unmatched even after normalisation cannot be attributed to anyone and are quarantined.

**Code:** `src/questions/seg4_cross_file.py::q30_unmatched_customers`, `sql/questions/seg4_q30.sql`

**Result:** exact_matched=5620, rescued_by_normalisation=279, unmatched=204, top_unmatched=C9999 (144 rows)

---

## Q31 — Unmatched product ids

**Method (2 sentences):**  
Ran R02 (product exists) with the same exact/normalised two-count design. Unmatched non-empty values were classified as *typing variants* if their normalised form shares a substring (≥2 chars) either way with a real product norm_id; otherwise *nonexistent*. Empty product_ids are counted separately as nonexistent.

**Decision & reason:**  
Only substring-overlap variants could ever be remapped without guessing; P99 (109 rows) and 54 empty strings have no overlap with any P01–P30 norm_id, so both are nonexistent. Typing variants = 0.

**Code:** `src/questions/seg4_cross_file.py::q31_unmatched_products`, `sql/questions/seg4_q31.sql`

**Result:** unmatched=163, typing_variants=0, nonexistent=163 (P99=109, empty=54)

---

## Q32 — Ghost customer value

**Method (2 sentences):**  
Identified orders whose customer_id fails R01 even after normalisation (the same 204 rows from Q30). Summed their line values using the single `row_line_value` definition (qty × net_price_paid).

**Decision & reason:**  
Ghost value (₹671,492) is excluded from all revenue answers because it cannot be attributed to any known person; including it would let unknown buyers inflate city and customer cuts. The amount sits in quarantine until ids are resolved.

**Code:** `src/questions/seg4_cross_file.py::q32_ghost_customer_value`, `sql/questions/seg4_q32.sql`

**Result:** ghost_customers=2, ghost_orders=204, ghost_value=671491.75

---

## Q33 — Products never ordered

**Method (2 sentences):**  
Built the set of normalised product_ids appearing in any order line. Products absent from that set are "never ordered"; for each, checked stock usability (numeric ≥0) and price usability (non-empty, non-NA) as observable evidence.

**Decision & reason:**  
All 30 products appear in orders after normalisation, so the result is empty. The data cannot distinguish "inactive" from "unpopular" without product launch dates, which the extracts lack.

**Code:** `src/questions/seg4_cross_file.py::q33_never_ordered_products`, `sql/questions/seg4_q33.sql`

**Result:** 0 products never ordered (empty DataFrame)

---

## Q34 — Catalogue vs paid price gap per product

**Method (2 sentences):**  
For each product with a valid catalogue price, computed the median net paid (unit_price_paid × (1−discount)) across its order lines. Gap = median_net_paid − catalogue_price; systematic if ≥80% of lines deviate the same way with median |gap_pct| > 10%.

**Decision & reason:**  
Median resists the 500-quantity spikes; percent gap uses catalogue as denominator. Four products (P16, P21, P22, P24, P29) show systematic gaps >10%, suggesting catalogue staleness or systematic discounting rather than noise.

**Code:** `src/questions/seg4_cross_file.py::q34_price_gap_per_product`, `sql/questions/seg4_q34.sql`

**Result:** 28 products with gaps; 5 systematic (P16, P21, P22, P24, P29)

---

## Q35 — Price closeness (R06 tolerance)

**Method (2 sentences):**  
Reused R06_VALID_PRICE which flags lines where |net_paid − catalogue| / catalogue > 10%. Counted lines within/outside tolerance, non-positive prices, and unverifiable (no catalogue price).

**Decision & reason:**  
10% tolerance sits outside discount-rounding and catalogue-staleness noise (5% is inside). "Far" values can mean stacked discounts, stale catalogue, bulk pricing, or data error — the rule flags, the business decides.

**Code:** `src/questions/seg4_cross_file.py::q35_price_closeness`, `sql/questions/seg4_q35.sql`

**Result:** within=558, outside=4453, non_positive=267, unverifiable=825

---

## Q36 — Fuzzy-attributed orders

**Method (2 sentences):**  
From R01 detail, isolated orders matched only via normalised customer_id (279 rows). Computed their share of total order value using the single `row_line_value` definition.

**Decision & reason:**  
Fuzzy rows carry the wrong spelling of who bought. Any answer keyed by customer identity (top customers, cohorts, tenure, concentration) is held back for them, while city/month totals keep them — a wrong city is a smaller error than a wrong person.

**Code:** `src/questions/seg4_cross_file.py::q36_fuzzy_attribution`, `sql/questions/seg4_q36.sql`

**Result:** fuzzy_orders=279, fuzzy_value_share_pct=13.49%, held_back=["top customers","cohorts","tenure","customer concentration"]

---

## Q37 — Every-month vs one-month customers

**Method (2 sentences):**  
Parsed all order_dates to YYYY-MM via `parse_date` (handles 4 formats). A customer is "every-month" if their order months cover all 87 months in the data; "one-month" if exactly 1. Described each group by city and signup span from the customer master.

**Decision & reason:**  
Zero customers appear in all 87 months (every_month=0). 161 customers are one-month buyers; their cities are empty because all 161 are ghost customers (unmatched). This reveals the one-month tail is partly a data problem (ghost ids), not just a real long tail.

**Code:** `src/questions/seg4_cross_file.py::q37_every_month_vs_one_month`, `sql/questions/seg4_q37.sql`

**Result:** months=87, every_month=0, one_month=161, one_month_unmatched=0 (ghosts excluded from city lookup)

---

## Q38 — Orders before signup

**Method (2 sentences):**  
Ran R03 (signup ≤ order) which evaluates only R01-matched customers. Counted flagged orders and distinct customers, plus future signups (>TODAY) in master and future orders (>TODAY) in orders.

**Decision & reason:**  
1,338 orders from 319 customers predate signup. Signup dates reach past TODAY (110 future) while most flagged orders sit in plausible past months, so the signup side is likelier wrong (default/placeholder future dates). R03 sets these rows aside either way.

**Code:** `src/questions/seg4_cross_file.py::q38_orders_before_signup`, `sql/questions/seg4_q38.sql`

**Result:** orders=1338, customers=319, future_signups=110, future_orders=1381

---

## Q39 — Join row losses

**Method (2 sentences):**  
Counted rows kept by five sequential joins: customers (exact), customers (normalised), products (exact), products (normalised), city attribution. The drop at each step is `before − kept`.

**Decision & reason:**  
The customer join drops the most rows (483 exact → 204 normalised), and it changes business answers: dropped rows vanish from city and customer cuts by construction (see reconcile join log). Product join drops fewer (456 → 163).

**Code:** `src/questions/seg4_cross_file.py::q39_join_losses`, `sql/questions/seg4_q39.sql`

**Result:** 
- orders-customers exact: kept 5620, dropped 483
- orders-customers normalised: kept 5899, dropped 204
- orders-products exact: kept 5647, dropped 456
- orders-products normalised: kept 5940, dropped 163
- orders-city attribution: kept 5899, dropped 204

---

## Q40 — Payment spellings

**Method (2 sentences):**  
Counted every raw `payment_mode` spelling pre-grouping (case-sensitive). Applied the proposed payment mapping to show standard value and whether assignable (not UNMAPPED/UNMAPPED_).

**Decision & reason:**  
Unassignable spellings (e.g., `cod` 650 rows) stay visible as UNMAPPED, never forced into a group. Each mapping decision lives in `mappings/proposed` with rationale.

**Code:** `src/questions/seg5_values.py::q40_payment_spellings`, `sql/questions/seg5_q40.sql`

**Result:** 10 spellings; `cod` (650) and empty (564) are unassignable; `COD` (603), `Credit Card` (637+615), `UPI` (606+568), `NetBanking` (652), `Debit Card` (637), `Cash on delivery` (555) map cleanly.

---

## Q41 — Status spellings

**Method (2 sentences):**  
Counted every raw `order_status` variant separately (pre-grouping). Noted that only `Delivered`/`delivered` (case-folded) means a completed sale; Returned, Cancelled, Pending, In Transit, MISSING are excluded from revenue.

**Decision & reason:**  
Nothing except Delivered certifies money changed hands and goods arrived. Returned/Cancelled reverse the sale; Pending/In Transit are incomplete; MISSING/UNMAPPED are unknown.

**Code:** `src/questions/seg5_values.py::q41_status_spellings`, `sql/questions/seg5_q41.sql`

**Result:** 10 variants; Delivered/delivered = 1,186 completed; Cancelled/cancelled = 1,226; Returned=618; In transit=602; Pending=623; empty=629.

---

## Q42 — Category merge/separate decisions

**Method (2 sentences):**  
Listed observed categories with product counts. Applied word-sharing rule: pairs sharing a word (case-insensitive) are merge candidates; decided per pair using case-only, suffix-only, and served-list evidence.

**Decision & reason:**  
- GROCERY/Grocery/grocery → merge (case only)  
- Snacks/snacks → merge (case only)  
- Dairy → Dairy & Eggs (suffix only; served list recognises Dairy & Eggs; product names scrambled so names decide nothing)  
- Beverages, Household → keep (singletons, no word-sharing rival)

**Code:** `src/questions/seg5_values.py::q42_category_pairs`, `sql/questions/seg5_q42.sql`

**Result:** 10 observed categories; 3 merge decisions, 2 keep decisions.

---

## Q43 — Quantity kinds

**Method (2 sentences):**  
Reused R05 classification (word, decimal, zero, negative, empty) via `_classify_bad_quantity`. Reported counts and share of the 651 bad rows.

**Decision & reason:**  
Words look typed, decimals look weighed/measured, zeros look like placeholders/cancelled remnants, negatives like returns/credits — all guesses, so none can be corrected without inventing data. Parseable wholes (e.g., 2.0) were already canonicalised at cleaning.

**Code:** `src/questions/seg5_values.py::q43_quantity_kinds`, `sql/questions/seg5_q43.sql`

**Result:** words=57, decimals=62, zero=251, negative=111, empty=170, bad_total=651

---

## Q44 — High quantities

**Method (2 sentences):**  
Computed data-driven "usual range" via IQR fence (Q3 + 3×IQR) on parseable quantities. Flagged rows above fence; all 77 flagged rows sit at exactly 500 with no gradation.

**Decision & reason:**  
Fence = 10.0 (data-derived, not guessed). 500 is a generator fault, not bulk buying (bulk would vary). Excluded from quantity-sensitive answers, kept in record.

**Code:** `src/questions/seg5_values.py::q44_high_quantities`, `sql/questions/seg5_q44.sql`

**Result:** fence=10.0, flagged_rows=77, flagged_values=[500], verdict=error

---

## Q45 — Future dates

**Method (2 sentences):**  
R04 flags order_date > TODAY (2026-10-11). Clustered the 467 future rows by parsed month to show the wrong-year-edit pattern (day/month plausible, year wrong).

**Decision & reason:**  
Future dates cluster in late 2026 and across 2027 with valid day/month but wrong years — the wrong-year-edit pattern, not scheduled orders (no schedule field) and not pure typos (day/month stay plausible).

**Code:** `src/questions/seg5_values.py::q45_future_dates`, `sql/questions/seg5_q45.sql`

**Result:** future_rows=467; months shows heavy clustering in 2026-11 through 2027-06.

---

## Q46 — Discount forms

**Method (2 sentences):**  
Classified each discount cell: fraction (0<x≤1, no %), percentage (x% or 1<x≤100), zero, empty, unparseable, out_of_range. Bare `0.1` is fraction (no %, in (0,1]); bare `15` is percentage (in (1,100]).

**Decision & reason:**  
The sign carries meaning; range check catches the rest. Bare `1` counted separately (could be 1% or 100% fraction). No out-of-range values found.

**Code:** `src/questions/seg5_values.py::q46_discount_forms`, `sql/questions/seg5_q46.sql`

**Result:** fraction=529, percentage=2176, zero=2271, empty=551, unparseable=576, out_of_range=0, bare_one=0

---

## Q47 — Delivery extremes

**Method (2 sentences):**  
R10 classifies delivery_days per status: Delivered → missing/negative/0-30/>30; Cancelled → ok if 0/empty, else anomaly. Counted each status×detail combination.

**Decision & reason:**  
Negative days are impossible (data error); 45-day values are the planted spike. Rows stay in record; day values excluded from speed answers via R10 (Delivered problems FAIL, cancelled anomalies WARNING).

**Code:** `src/questions/seg5_values.py::q47_delivery_extremes`, `sql/questions/seg5_q47.sql`

**Result:** See `by_status_detail` dict; key anomalies: Delivered negative=5+4, Delivered >30=3+9, Cancelled with days=521+81.

---

## Q48 — Outside served cities

**Method (2 sentences):**  
Joined orders to customers for city, compared against served list [Bengaluru, Chennai, Hyderabad, Pune]. Counted outside orders, value, customers, and distinct outside city values.

**Decision & reason:**  
Mysuru is a real city (data or expansion, not typo); MISSING, BLR, Bangalore, Madras, bengaluru, chennai are data errors/typos. Verdict: mixed — ask business whether Mysuru is served (brief error if yes, data error if no) and whether to add it.

**Code:** `src/questions/seg5_values.py::q48_outside_cities`, `sql/questions/seg5_q48.sql`

**Result:** served=4, outside_values=8 (['', 'BLR', 'Bangalore', 'Madras', 'Mysuru', 'UNMATCHED', 'bengaluru', 'chennai']), outside_orders=3521, outside_value=11356541.0, outside_customers=270

---

## Q49 — Three things the data cannot tell Neha

**Method (2 sentences):**  
Each unknown names its responsible column/missing field, counts affected rows, shows one masked customer example (first char + asterisks), and names the unsafe decision.

**Decision & reason:**  
Kept for Sprint 4 Q4 report. No PII in outputs (masking enforced).

**Code:** `src/questions/seg5_values.py::q49_three_unknowns`, `sql/questions/seg5_q49.sql`

**Result:**  

1. **True stock availability at order time**  
   - Responsible: `stock_qty` (point-in-time snapshot, no history)  
   - Rows affected: 2,610 order lines  
   - Example customer: `C****`  
   - Unsafe decision: Purchase/stock planning per product  

2. **Actual delivery performance where days are missing**  
   - Responsible: `delivery_days` (empty values carry no time)  
   - Rows affected: 142 order lines  
   - Example customer: `C****`  
   - Unsafe decision: Promising SLA timelines to leadership  

3. **True identity behind unmatched customer ids**  
   - Responsible: `customer_id` (no master row; no second identifier)  
   - Rows affected: 483 order lines  
   - Example customer: `c****`  
   - Unsafe decision: Customer-level targeting and revenue attribution

---

*All answers derived from Sprint 3 trusted artifacts. No PII in this document (regex scan: `^[A-Z]\*+$` pattern only).*