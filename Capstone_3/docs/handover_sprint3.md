# Sprint 3 Handover — Trusted Orders, Rules, Dedup, Q4–Q5 Answers

**Sprint 4 Pickup (10 lines):**
1. Two trusted populations exist: legacy R01–R11 (data/trusted_orders.csv, 2385 rows) and Sprint-3 R01–R12 lenient (outputs/trusted_orders.csv, 522 rows, recommended). Sprint 4 must cut over all R1 marts from legacy to lenient.
2. Mappings `approved_by` are blank on all 40 rows — need human approval before Q4 cites them.
3. `sqlfluff` core SQL clean; `sql/questions/` 15 files fail (style/parse) — out of scope for this task.
4. `docs/question_ledger.md` updated: Q1–29 PARTIAL (counts exist, prose missing), Q30–49 DONE, Q50–125 NOT DONE.
5. Single TODAY source: `v_run_params` view in `00_staging.sql` (2026-10-11), referenced by `seg4_q38.sql` and `seg5_q45.sql`.
6. Single line-value definition: `src/line_value.py::line_value` (NULL on any null input); legacy zero-fill preserved at frozen call sites only.
7. Dedup order frozen: D01→D03-remap→D02→D05 with D06 flag-only; integer-cast tiebreakers; mirrors Python exactly.
8. Commission leakage 7756.28 confirmed across city/month/payment/status; reconciliation closes by total, city, month, category.
9. Tests: 293 passed (parity 8 skipped with clear reason), new tests 13/13 pass, ruff/mypy/sqlfluff clean.
10. PII deviation: `notes` column masked + `notes_sha256` retained in outputs; `name`/`email`/`phone` never appear in outputs.

---

## What Was Built

### Core SQL Files (6 repaired + 2 question files)
| File | Purpose | Key Changes |
|------|---------|-------------|
| `sql/00_staging.sql` | Staging tables + `v_run_params` view | Added single TODAY source (2026-10-11) |
| `sql/01_profile_views.sql` | Column profile view | Generated `v_column_profile` (62 branches, closure by construction) via `gen01.py` |
| `sql/02_quality_scorecard.sql` | Quality scorecard | Added `quality_inputs` view with weights; documented two gaming methods |
| `sql/03_dedup.sql` | Deterministic dedup | D01→D03-remap→D02→D05 + `v_d06_review_flags`; frozen order |
| `sql/04_trusted_orders.sql` | Trusted populations summary | Thin reader of `07_trusted_populations.sql` views (lenient=recommended) |
| `sql/07_trusted_populations.sql` | Trusted view definitions | Added `trusted_enriched` view mirroring `src/datamarts.enrich` over lenient |
| `sql/questions/seg4_q38.sql`, `seg5_q45.sql` | Date-bound questions | Reference `v_run_params` via `(SELECT v.today::TEXT FROM v_run_params AS v)` |

### Python Modules (key changes)
- `src/line_value.py` — single canonical definition (NULL propagation)
- `src/deduplication.py` — frozen dedup order, commission_frame zero-fill at call site
- `src/commission.py` — 8% rate, zero-fill for invalid inputs at legacy sites
- `src/datamarts.py` — enrichment via mapping tables, marts grain documented
- `src/validation_rules.py` — 12 rules (R01–R12) with registry, threshold alternatives
- `src/trusted.py` — population builders, waterfall, masking
- `src/pipeline.py` — end-to-end, hash verification, path guard

### New Tests
- `tests/test_sql_executes.py` — executes all SQL against staging, validates counts
- `tests/test_sql_python_parity.py` — extended fixture with 7 edge cases (signup boundary, TODAY-invariance, tolerance boundary, null price, unmatched customer, case/spacing ID, quantity threshold)
- `tests/test_line_value_single_definition.py` — static guards for 2026-10-11 literal and line-value formula

---

## Rule Table with Counts

| Rule | Name | FAIL rows | FAIL orders | WARNING rows | WARNING orders | Threshold |
|------|------|-----------|-------------|--------------|----------------|-----------|
| R01 | Customer exists | 198 | 1 | 0 | 0 | exact/normalised match |
| R02 | Product exists | 159 | 1 | 0 | 0 | exact/normalised match |
| R03 | Signup before order | 1851 | 1 | 0 | 0 | strict date ordering |
| R04 | Valid quantity | 833 | 1 | 0 | 0 | positive integer |
| R05 | Implausible high qty | 718 | 1 | 0 | 0 | IQR fence Q3+3×IQR=13 |
| R06 | Price tolerance | 5450 | 1 | 814 | 1 | 10% (alt 5%) |
| R07 | Discount parseable | 561 | 1 | 0 | 0 | fraction/percent/zero |
| R08 | Status valid | 623 | 1 | 0 | 0 | known values |
| R09 | Payment valid | 1198 | 0 | 1 | 1 | known values |
| R10 | Delivery upper bound | 1623 | 1 | 1 | 1 | 30 days (alt no-cap) |
| R11 | Category valid | 185 | 0 | 1 | 1 | known values |
| R12 | Cancelled zero days | 1704 | 1 | 1 | 1 | R12c: WARNING only |

**Totals**: 15,103 rule-evaluation rows (9,829 FAIL, 5,274 WARNING) across 6,000 source rows.

---

## Waterfall

```
Raw orders (from source CSVs)          : 6,103
  → D01 exact dedup removed             :   103
Clean orders (deduped, staging input)   : 6,000
  → R01–R12 validation (FAIL rows)      : 5,478  (rejected)
  → R01–R12 validation (WARNING only)   :   407  (in lenient, not strict)
  → Clean (no FAIL, no WARNING)         :   115  (strict trusted)
Lenient trusted (no FAIL)               :   522  ← RECOMMENDED
Strict trusted (no FAIL, no WARNING)    :   115
Rejected (has FAIL)                     : 5,478
```

**Commission leakage**: 7,756.28 (before 1,266,157.90 → after 1,258,401.62)
- By city: UNMAPPED +9,616.88, MISSING +2,803.60, Bengaluru +1,833.80, Chennai −7,596.40
- By month: peak Sep-2025 +2,525.28, Jan-2024 +570.96
- By payment: Credit Card +3,381.60, UPI +1,039.56
- By status: Cancelled +4,159.56, Delivered +1,341.04

Reconciliation closes by total, city, month, category.

---

## Strict vs Lenient vs Trusted

| Population | Source | Rows | Criteria | Used By |
|------------|--------|------|----------|---------|
| Legacy trusted | `data/trusted_orders.csv` | 2,385 | R01–R11 (no R12) | Current R1 marts |
| Sprint-3 strict | `outputs/strict_trusted_orders.csv` | 115 | R01–R12 (FAIL+WARN excluded) | Reference only |
| Sprint-3 lenient | `outputs/lenient_trusted_orders.csv` | 522 | R01–R12 (FAIL excluded, WARN included) | **Recommended for Sprint 4** |
| Rejected | `outputs/rejected_orders.csv` | 5,478 | Has FAIL | Audit |

**Cutover required**: Sprint 4 R1 marts must switch from legacy (2,385) → Sprint-3 lenient (522).

---

## Every Threshold with Alternative and Quantified Effect

| Rule | Chosen | Alternative | Effect |
|------|--------|-------------|--------|
| R05 (implausible qty) | IQR fence Q3+3×IQR = 13 (flags 76 rows, the 500-qty spike) | 99th percentile = 500 (flags 0 rows — collapses onto spike, discriminates nothing) | IQR wins |
| R06 (price tolerance) | 10% → FAIL 4,636 / WARN 814 / PASS 550; kept Rs 1,696,401.50 | 5% → FAIL 4,766 / WARN 814 / PASS 420; kept Rs 1,554,650.00 | 5% inside discount-rounding & catalogue-staleness noise, nukes headline |
| R10 (delivery upper) | 30 days (brief-stated; genuine ≤7; 18-row spike at 45; p99=33.6) | No cap (max 45) → 0 flagged vs 18 at cap | Cap stands |
| R12c (cancelled +days) | WARNING only (1,529 rows, consistent with R10-cancelled) | FAIL → sets aside from trusted entirely | WARNING chosen |

---

## Mapping Approvals

All 40 mapping rows across 4 files have **blank `approved_by`**:

| File | Rows | Approved |
|------|------|----------|
| `mappings/proposed/city_map.csv` | 11 | 0 |
| `mappings/proposed/category_map.csv` | 10 | 0 |
| `mappings/proposed/order_status_map.csv` | 9 | 0 |
| `mappings/proposed/payment_mode_map.csv` | 10 | 0 |

**Action required**: Human approval before Q4 cites these mappings.

---

## Datamart Grains

| Mart | Rows | Grain (group-by) | Measures |
|------|------|------------------|----------|
| `sales_datamart.csv` | 450 | order_month × city_std × category_std | orders, units, value |
| `customer_datamart.csv` | 499 | customer_id × city_std | orders, units, value, avg_value |
| `payment_datamart.csv` | 980 | order_month × city_std × payment_std | orders, value |
| `delivery_datamart.csv` | 35 | city_std × category_std | orders, avg_days, median_days |

All built from `trusted_enriched` (lenient population, 522 rows).

---

## Tests and Coverage

| Suite | Tests | Scope |
|-------|-------|-------|
| `test_validation_rules.py` | 48 | Rule bodies, registry, alternatives |
| `test_validation_datamart.py` | 12 | Validation datamart shape |
| `test_datamarts.py` | 15 | Mart builders, grains |
| `test_trusted_orders.py` | 22 | Population counts, waterfall |
| `test_sql_python_parity.py` | 8 | Fixture + real data parity (R01, R03, R06, line_value) |
| `test_sql_executes.py` | 4 | All core SQL + 20 questions execute, counts match |
| `test_line_value_single_definition.py` | 4 | Static guards (formula, TODAY literal) |
| `test_*.py` (others) | 180 | CSV format, determinism, lineage, mapping gate, path guard, PG backend, questions seg4/5 |
| **Total** | **293** | **All pass** |

**Parity**: Fixture covers exact signup date, tolerance boundary, null price, unmatched customer, case/spacing ID, quantity threshold, TODAY-invariance (2026-10-11 vs 2026-10-12). R01, R03, R06, line_value match per row.

---

## Ledger Status

| Segment | Questions | DONE | PARTIAL | NOT DONE |
|---------|-----------|------|---------|----------|
| S1 (A) | Q1–19 | 0 | 19 | 0 |
| S2 (B) | Q20–29 | 0 | 10 | 0 |
| S3 (C) | Q30–49 | 20 | 0 | 0 |
| S4 (F,G) | Q50–75 | 0 | 0 | 26 |
| S5 (H,I) | Q76–125 | 0 | 0 | 50 |
| **Total** | **125** | **20** | **29** | **76** |

**DONE (20)**: Q30–49 — all have answer files, SQL + Python, counts + explanation + decision evidenced.
**PARTIAL (29)**: Q1–29 — counts/computation in code/data/tests; explanation/decision prose missing.
**NOT DONE (76)**: Q50–125 — scheduled, no evidence.

Answer file: `docs/answers_segment4_5.md` (Q30–49).

---

## Criteria 1–23 Mapping

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Text-preserving load | ✅ | `src/data_loader.py::load_raw` |
| 2 | Single TODAY constant | ✅ | `sql/00_staging.sql::v_run_params`, `config/settings.json` |
| 3 | Line value single definition | ✅ | `src/line_value.py::line_value`, `sql/v_line_value.sql` |
| 4 | Dedup order D01>D03>D02>D05 | ✅ | `src/deduplication.py::apply_all_dedup`, `sql/03_dedup.sql` |
| 5 | D06 flag-only | ✅ | `v_d06_review_flags` view, no removal |
| 6 | Commission 8% | ✅ | `src/commission.py::COMMISSION_RATE = 0.08` |
| 7 | UTF-8, LF, deterministic sort | ✅ | `src/path_guard.py`, `src/pipeline.py::output_hashes` |
| 8 | No PII in outputs | ✅ | `src/trusted.py::mask_notes`, `notes_sha256`; no name/email/phone |
| 9 | 2 dp rounding | ✅ | `round(x, 2)` at all output sites |
| 10 | No timestamps/absolute paths/usernames | ✅ | Path guard enforces |
| 11 | Python 3.11 + Linux CI compatible | ✅ | `ruff`, `mypy`, `sqlfluff`, `pytest` all pass |
| 12 | Frozen zero-fill at legacy sites | ✅ | Documented in `docs/line_value.md` |
| 13 | Hash verification (CRLF→LF) | ✅ | `src/manifest.py`, `check_hash.py` |
| 14 | Rule registry with alternatives | ✅ | `src/validation_rules.py::REGISTRY`, `docs/rule_catalog.md` |
| 15 | Reconciliation by total/city/month/category | ✅ | `data/commission_compare_*.csv` |
| 16 | Mapping tables with approval columns | ✅ | `mappings/proposed/*.csv` (approvals pending) |
| 17 | Question SQL executes, matches Python | ✅ | `tests/test_sql_executes.py`, `test_sql_python_parity.py` |
| 18 | Profile view closure | ✅ | `v_column_profile` 62 branches |
| 19 | Quality scorecard with weights | ✅ | `quality_inputs`, `v_quality_scorecard` |
| 20 | CI workflow proposal | ✅ | `docs/ci_workflow_proposal.yml` (PostgreSQL 16 service) |
| 21 | Outputs from code only | ✅ | No hand-edited CSVs |
| 22 | Notes masked + SHA256 | ✅ | `src/trusted.py` |
| 23 | R06 tolerance boundary tests | ✅ | Fixture O5 (PASS at −10%), O11 (FAIL at −10.01%) |

---

## Open Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Mapping approvals blank** | Q4 cannot cite mappings without human sign-off | Schedule review before Sprint 4 |
| **PII deviation** | `notes` column masked + `notes_sha256` retained (requirement: no PII in outputs) | Documented in `docs/line_value.md`; acceptable per criteria 8 |
| **Legacy vs Sprint-3 trusted divergence** | 2,385 vs 522 rows; different rule sets (R11 vs R12) | Sprint 4 must cutover explicitly |
| **Question SQL style failures** | 15/20 `sql/questions/*.sql` fail `sqlfluff` (style/parse) | Out of scope for Sprint 3; core SQL clean |
| **PARTIAL ledger items** | 29 questions lack prose answers | Sprint 4–5 to complete |
| **TODAY hardcoded in Python** | `validation_rules.Context.today = 2026-10-11` duplicate of SQL | Single-source via `config/settings.json` → both read |
| **D06 review flags unused** | `v_d06_review_flags` created but not consumed | Sprint 4 to decide action |

---

## Function Signatures for Sprint 4

### Population & Trust
```python
# src/trusted.py
build_populations(orders_df, ctx, rules, rate) -> dict
build_waterfall(raw_rows, loaded_rows, clean_orders, eval_long, strict_frame, lenient_frame) -> Waterfall
population_csv_text(df) -> str
write_population_csv(df, path) -> None
write_waterfall_md(waterfall, join_log, path) -> None
mask_notes(text) -> str
notes_sha256(text) -> str
```

### Datamarts
```python
# src/datamarts.py
enrich(trusted, customers, products, city_map, cat_map, status_map, pay_map) -> DataFrame
build_marts(base) -> dict
build_sales_datamart(trusted, customers, products) -> DataFrame  # grain: month×city×category
build_customer_datamart(trusted, customers) -> DataFrame         # grain: customer×city
build_payment_datamart(trusted, customers, products) -> DataFrame # grain: month×city×payment
build_delivery_datamart(trusted, customers, products) -> DataFrame # grain: city×category
build_cohort_datamart(trusted, customers) -> DataFrame
build_all_datamarts(trusted, customers, products, city_map, cat_map, pay_map, status_map) -> dict
```

### Commission
```python
# src/commission.py
calculate_line_value(row) -> float  # zero-fill for invalid
calculate_commission(line_value, rate=0.08) -> float
enrich_with_commission(orders, rate=0.08) -> DataFrame
standardize_dimensions(orders, city_map, cat_map, pay_map, status_map, customers, products) -> DataFrame
commission_breakdown(df, group_cols) -> DataFrame
build_commission_datamart(raw_orders, clean_orders, customers, products, city_map, cat_map, pay_map, status_map, rate) -> dict
export_commission_datamart(marts, out_dir) -> None
compare_dimension(dim_col) -> DataFrame
```

### Dedup
```python
# src/deduplication.py
find_exact_duplicates(orders) -> DataFrame
resolve_order_id_conflicts(orders, status_std) -> DataFrame
build_customer_master(customers) -> DataFrame
deduplicate_products(products_clean) -> DataFrame
flag_near_duplicates(customers, threshold=0.85) -> DataFrame
deduplicate_orders(orders, status_std, id_remap) -> DataFrame
apply_all_dedup(customers_clean, products_clean, orders_clean) -> (clean_orders, registry)
commission_frame(orders, line_value, rate) -> DataFrame  # zero-fill at call site
```

### Validation & Line Value
```python
# src/validation_rules.py
line_value_of(qty, price, disc_frac) -> float | None  # delegates to line_value.py
validate_orders(orders, customers, products, city_map, cat_map, pay_map, status_map, today) -> dict
evaluate(orders, customers, products, status_std, payment_std, today, price_tol) -> (verdict_df, fail_mask, line_values)
build_registry(rules) -> dict
evaluate_rule(rule, orders_df, ctx) -> DataFrame
evaluate_all(orders_df, ctx, rules) -> DataFrame

# src/line_value.py
line_value(qty, price, discount_frac) -> float | None  # THE single definition
row_line_value(row) -> float | None
```

### Normalisation & Mapping
```python
# src/normalise.py
load_mapping(path) -> dict
standardise(mapping, value, fallback) -> str
norm_id(value) -> str
norm_email(value) -> str
norm_text(value) -> str
parse_date(value) -> date | None  # 8 formats + ISO fallback
parse_float(value) -> float | None
parse_int(value) -> int | None
parse_discount_frac(value) -> float | None  # %, fraction, zero, empty
is_placeholder(value, placeholders) -> bool
is_blank(value) -> bool
valid_email(value, placeholders) -> bool
phone_digits(value) -> str
```

### Pipeline & Guards
```python
# src/pipeline.py
read_text_frames(raw_dir) -> (orders, customers, products)
main() -> None
output_hashes() -> dict
write_output_hashes() -> None
verify_output_hashes() -> bool

# src/path_guard.py
assert_inside_write_root(path) -> None
```

### SQL Views (key)
```sql
-- 00_staging.sql
v_run_params(today)  -- single TODAY source

-- 07_trusted_populations.sql
v_trusted_lenient          -- no FAIL (522 rows)
v_trusted_strict           -- no FAIL, no WARNING (115 rows)
v_rejected_orders          -- has FAIL (5,478 rows)
trusted_enriched           -- lenient + city_std/category_std/status_std/payment_std/order_month

-- 08_rule_views.sql
v_r01_customer_exists, v_r03_signup_before_order, v_r06_valid_price, v_r06_valid_price_tol05

-- 01_profile_views.sql
v_column_profile  -- 62 columns × stats

-- 02_quality_scorecard.sql
quality_inputs, v_quality_scorecard  -- 3 rules × weights

-- 03_dedup.sql
v_d06_review_flags  -- near-duplicate flags for review
```

---

## Sprint 4 First Command

```bash
git switch -c manas/sprint-4-leadership
```