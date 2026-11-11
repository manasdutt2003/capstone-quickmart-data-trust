# QuickMart Resume Audit — Sprint 3 Entry (2026-10-13)

Scope: WRITE ROOT only. No files changed in this audit. No conflict markers found (`<<<<<<<`/`=======`/`>>>>>>>` absent). `git status` clean on branch `manas/sprint-2-rebuild`.

## 1. Inventory

### src/ (15 modules)
- `data_loader.py` — raw-preserving text load, SHA-256 manifest, encoding detect. Reuse: `load_raw`, `load_all_text`, `write_manifest`, `sha256_of`.
- `normalise.py` — single source of truth for parsing/mapping. Reuse: `load_mapping`, `standardise`, `norm_id`, `norm_email`, `parse_date`, `parse_float`, `parse_int`, `parse_discount_frac`, `valid_email`.
- `profiling.py` — one row per column. Reuse: `profile_table(df, table)`, `profile_all(customers, products, orders)`.
- `cleaning.py` — raw-text -> cleaned copies + `raw_*` + `_source_row` lineage. Reuse: `clean_all(...)`, `clean_customers`, `clean_products`, `clean_orders`.
- `quality_checks.py` — 22 QC rules, fail-mask dicts. Reuse: `run_all_checks(...)`, `quality_fail_masks(...)`, `RULE_CATALOG`.
- `issue_registry.py` — registry + quality mart + scorecard. Reuse: `build_issue_registry(checks, rules=None)`, `build_quality_datamart(orders, checks, customers, products, city_map, cat_map, pay_map, status_map)`, `build_quality_scorecard(...)`.
- `deduplication.py` — D01–D06 catalog. Reuse: `deduplicate_orders(orders, status_std, id_remap)`, `build_customer_master(customers)`, `apply_all_dedup(...)`, `commission_frame(...)`, `RULE_CATALOG`, `STATUS_PRIORITY`.
- `commission.py` — 8% commission + 13 breakdown tables. Reuse: `build_commission_datamart(raw_orders, clean_orders, customers, products, ...)`, `enrich_with_commission`, `standardize_dimensions`.
- `validation_rules.py` — R01–R11 trusted-order engine. Reuse: `validate_orders(...)`, `evaluate(...)`, `line_value_of(qty, price, disc_frac)`, `RULES`.
- `datamarts.py` — trusted-only marts. Reuse: `enrich(...)`, `build_marts(base)`, `build_*_datamart(...)`, `build_all_datamarts(...)`.
- `deduplication_report.py` — markdown report writer. Reuse: `generate_deduplication_report(...)`.
- `llm_reporting.py` — aggregates-only draft + PII guard. Reuse: `aggregate_inputs`, `draft_report`, `validate_report`, `assert_no_pii`, `MODEL_INFO`, `PROMPT_V1/V2`.
- `report_validation.py` — figure-to-mart checker. Reuse: `verify_all_claims`, `validate_report`, `generate_validation_report`.
- `pipeline.py` — one-command run: `main()`, `read_text_frames()`, paths `RAW_DIR/CONFIG/DATA/REPORTS/CHARTS`.
- `__init__.py` — empty.

Full signatures extracted via AST audit (see session log); key contracts above are what S3–S5 must reuse. Do not redefine `line_value` elsewhere.

### sql/ (6 files)
- `01_profile_views.sql` — profiling view (per column evidence).
- `02_quality_scorecard.sql` — scorecard aggregation.
- `03_dedup.sql` — deterministic survivor per order_id (status rank + completeness + row order).
- `04_trusted_orders.sql` — CTE chain dedup -> validated -> completed with per-stage counts.
- `05_marts.sql` — GROUPING SETS sales mart, reconciles to trusted delivered total.
- `06_segment6_9_answers.sql` — segment 6–9 answers.

### tests/ (12 files, ~129 tests)
`test_cleaning, test_commission, test_data_loader, test_datamarts, test_deduplication, test_issue_registry, test_llm_validation, test_profiling, test_quality_checks, test_reporting, test_trusted_orders, test_validation_rules`.

### config/
`settings.json` (today, commission_rate, thresholds), `city/payment/status/category_mapping.csv` (all rows carry `approved_by`), `requirements.txt` (pandas, pandas-stubs, matplotlib, pytest, pytest-cov, ruff, mypy, sqlfluff).

### outputs (generated, NOT committed)
`data/`, `reports/`, `charts/` absent locally (pipeline generates on CI). Do not hand-edit.

## 2. Public function signatures (S3–S5 reuse contract)
See §1. Frozen contracts: `clean_all(...)`, `run_all_checks(...)`, `build_issue_registry(checks, rules)`, `deduplicate_orders(...)`, `build_customer_master(...)`, `build_commission_datamart(...)`, `validate_orders(...)`, `evaluate(...)`, `line_value_of(...)`, `enrich(...)`, `build_marts(...)`, `aggregate_inputs/draft_report/validate_report/assert_no_pii`.

## 3. Sprint 1–2 outputs (regenerated 2026-10-13 via `python -m src.pipeline`)
- Raw (read-only, immutable; manifest MATCHES source CSVs): customers 520 rows (sha fce10decb8fa), products 30 rows (sha a08781950dc8), orders 6103 rows (sha 03a9482ac6ec).
- Cleaned (cleaning never drops rows; lineage via `raw_*` + `_source_row`): `customers_clean.csv` 520 rows (sha 93884a589970), `products_clean.csv` 30 rows (sha b6737cdcf296), `orders_clean.csv` 6103 rows (sha 6e8649574cd8).
- Quality: `profile.csv` 22 rows (sha 37bedc6cb7f9), `issue_registry.csv` 22 rows (sha 4286853acf12), `quality_datamart.csv` 6103 rows, 1 row/order + flags (sha c86e499f951d), `quality_scorecard.csv` 3 rows (sha 4de4120870f8).
- Dedup: `customer_master.csv` 499 rows (sha cac8d2e822b8), `clean_orders.csv` 6000 rows (sha 492c2009686e; 6103 − 103 removals; D06 review-only), `duplicate_registry.csv` 124 rows (sha 1c07c1533774), `commission_datamart.csv` 1 row (sha dacac62007d6) + 12 `commission_by_*/compare_*` breakdowns (see table below).
- Trusted: `trusted_orders.csv` 2385 rows (sha 5253f2186a4a), `rejected_orders.csv` 3615 rows (sha 311366165f7c); 2385 + 3615 = 6000 = clean ✓.
- Marts: `sales_datamart.csv` 457 rows, `customer_value_datamart.csv` 333 rows, `payment_datamart.csv` 994 rows, `delivery_datamart.csv` 35 rows, `cohort_datamart.csv` 616 rows.
- Reports/charts: `reports/` 8 md files + `charts/monthly_sales.png` regenerated; pipeline: `PIPELINE OK {raw: 6103, trusted: 2385, value: 2309394.0}`.
- Full per-file row counts + SHA-256 recorded in session log 2026-10-13 (table above is the committed summary; `data/raw_manifest.json` sha 84b7186eac50 holds runtime manifest).

## 4. Frozen definitions
- Load policy: every value as text (`dtype=str`, `keep_default_na=False`); BOM/encoding detected; reload idempotent (same bytes -> same rows + SHA-256); header must match expected.
- Normalisation: trim; `standardise()` idempotent; `norm_id`=upper+strip spaces/dashes; `norm_email`=lower+trim; dates to ISO via 8 formats + ISO fallback else ""; numbers strip commas/₹/? else ""; discounts to 0–1 fraction ("10%"->0.1).
- Duplicate rules: D01 exact business cols; D03 email-merge (earliest signup survives, remap first); D02 order_id priority Delivered>In Transit>Pending>Returned>Cancelled>MISSING/UNMAPPED then completeness; D05 line-key; D04 product-variant merge; D06 fuzzy flag-only, never removes.
- Commission: `line_value = qty * unit_price_paid * (1 - discount_frac)` (single def in `validation_rules.line_value_of`); `commission = round(0.08 * line_value, 2)`; leakage = before − after (reconciliation gate, not hardcoded).
- Reference date: TODAY=2026-10-11 everywhere; future dates quarantined.

## 5. Defects found after merge (all 5 FIXED 2026-10-13; see session log for diffs)
1. FIXED: `test_llm_validation` import shadowing resolved via `validate_llm_report` alias; `TestValidateReport` passes.
2. FIXED: dead manifest load removed from `test_trusted_reconciliation_on_generated_data`; single `trusted+rejected==clean` assertion kept.
3. FIXED: commission rate single-sourced to `config/settings.json: commission_rate`; `COMMISSION_RATE` mirrors it as default, pipeline threads `rate`; assumption recorded in `docs/assumptions.md` (brief states no rate).
4. FIXED: `tests/conftest.py` session fixture runs pipeline once iff artifacts missing; tests now fail only on logic.
5. FIXED: pipeline rerun OK (raw 6103, trusted 2385, value 2309394.0); outputs regenerated, §3 updated.

## 6. Acceptance criteria #1–23
| # | Status | Evidence |
|---|--------|----------|
| 1 | met | `python -m src.pipeline` one command; CI runs it |
| 2 | met | extracts immutable; `sha256_of` + manifest; never edited |
| 3 | met | `ruff`, `mypy` (15 files), `sqlfluff --dialect ansi` all pass |
| 4 | met | CI blocks on pytest; branch + PR workflow in use |
| 5 | met | secret scan step; no findings reported |
| 6 | met | text-preserving loader; leading zeros/currency/quotes kept |
| 7 | partial | reconciliation code present; full close needs pipeline run artifacts |
| 8 | met | `profile_table`: missing+usable=rows per column |
| 9 | met | 22 QC rules named/counted/treated; `RULE_CATALOG` |
| 10 | met | D01–D06 + before/after normalisation counts; removals reconcile |
| 11 | met | mappings complete; rows carry `approved_by` |
| 12 | met | single `line_value_of`; marts/trusted use it; no raw reads in Q4 path |
| 13 | partial | reconcile asserts in code; numeric close needs pipeline run |
| 14 | partial | boundary/tie handling in code; CI injection test not run locally |
| 15 | partial | chart generated from mart; match test needs artifacts |
| 16 | partial | SQL+Python parity intended; parity test needs artifacts |
| 17 | partial | alternatives noted (e.g. commission rate); quantified effect in report pending |
| 18 | partial | registry schema extract/column/count/treatment/reason; completeness review pending |
| 19 | not met | 5-page report (Q1–Q5) not yet written |
| 20 | met | PII guard `assert_no_pii` + regex scan; aggregates-only to model |
| 21 | partial | README complete + least-sure number (8%); walkthrough pending |
| 22 | partial | marts from trusted only in code; totals + no-code refresh need pipeline run |
| 23 | partial | grounded-report + model/prompt registry in code; end-to-end verify needs pipeline run |

## 7. Test/lint baseline (re-run 2026-10-13, post-fix)
- `pytest tests/ --cov=src`: **129 passed, 0 failed**; total coverage 64% (pipeline/dedup-report 0% by design — run, not imported).
- CI scope (5 files): 33 passed. Sprint-2 scope (dedup+commission): 35 passed.
- `ruff check src tests`: pass. `mypy src`: pass (15 files). `sqlfluff lint sql/ --dialect ansi`: pass.
