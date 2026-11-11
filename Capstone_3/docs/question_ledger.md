# Question Ledger — 125 brief questions (rewritten with evidence + git state)

Allocation: A=Q1–9, B=Q10–19, C=Q20–29, D=Q30–39, E=Q40–49, F=Q50–67, G=Q68–75, H=Q76–77, I=Q78–125.
Rule: DONE only with an opened evidence file and every sub-part answered.
No answers are written here — ledger only. HTML brief never copied in.

Status key: DONE = counts + explanation + decision all evidenced in an opened
file. NOT DONE = scheduled or missing its explanation prose (reason stated).
No PARTIAL rows remain: computation-only rows are NOT DONE with the reason.

Git key: tracked+M = tracked and modified in working tree; tracked = clean;
untracked = new file/dir not in HEAD. (`data/`, `docs/`, `outputs/`,
`reports/` are untracked as a whole.)

| id | seg | status | answer file | function/section | git | missing sub-part |
|---|---|---|---|---|---|---|
| Q1 | A | DONE | `docs/answers_segment1_3.md` + `src/data_loader.py::load_raw` + `data/raw_manifest.json` | rows in file = loaded: 520/30/6103; blank-line filter never fired; nothing dropped | untracked | — |
| Q2 | A | DONE | `docs/answers_segment1_3.md` + `src/data_loader.py::EXPECTED_HEADERS` + `data/raw_manifest.json` | headers match expected 3/3, kept verbatim in manifest; mismatch would raise (none found) | untracked | — |
| Q3 | A | DONE | `docs/answers_segment1_3.md` + `src/data_loader.py` + `src/normalise.py` | all-text load; typed read would change listed columns; qty -2×111 / 2.5×62; Rs-symbol ×128; discount 7 forms | untracked | — |
| Q4 | A | DONE | `docs/answers_segment1_3.md` + `src/data_loader.py::row_length_audit` + `data/raw_manifest.json` | row_length_dist {6:520} {5:30} {11:6103}; short 0 / long 0; quoting-caused splits 0 | untracked | — |
| Q5 | A | DONE | `docs/answers_segment1_3.md` + `src/normalise.py::norm_id` + `src/data_loader.py` | customer ids: trailing-space 8 / lower 19 / dash 4; rows changed by norm 23; 500 = 500 distinct | untracked | — |
| Q6 | A | DONE | `docs/answers_segment1_3.md` + `src/normalise.py::parse_date` | orders already-ISO 1,151 / changed 4,662 / unparseable 290; customers 108 / 387 / 25; day-first rule | untracked | — |
| Q7 | A | DONE | `docs/answers_segment1_3.md` + `src/data_loader.py::detect_encoding` | all 3 files utf-8 (no BOM); non-ASCII = rupee sign only (125+3); cp1252 misread demo'd | untracked | — |
| Q8 | A | DONE | `docs/answers_segment1_3.md` + `src/data_loader.py::load_raw` | notes with commas 2,141 / double quotes 545; 0 wrong field counts (11 fields × 6,103 rows) | untracked | — |
| Q9 | A | DONE | `docs/answers_segment1_3.md` + `src/data_loader.py::sha256_of`, `write_manifest` | double-load identical 520/30/6103; SHA-256 stable (fce10dec/a0878195/03a9482a prefixes) | untracked | — |
| Q10 | B | DONE | `docs/answers_segment1_3.md` + `src/quality_checks.py::PLACEHOLDERS` + `data/issue_registry.csv` | empty/placeholder by column: name 20/0, email 32/10, city 39/0, phone 109/0, signup 11/14 | untracked | — |
| Q11 | B | DONE | `docs/answers_segment1_3.md` + `src/quality_checks.py` + `data/quality_datamart.csv` | placeholders in 3 columns only: discount 576, order_date 110, unit_price_paid 68; ≤6.3% → no fault window | untracked | — |
| Q12 | B | DONE | `docs/answers_segment1_3.md` + `data/profile.csv` + `data/quality_datamart.csv` | notes most-empty 37.11%; uniform across statuses (35–39%); delivery_days 2–4% flat | untracked | — |
| Q13 | B | DONE | `docs/answers_segment1_3.md` + `data/quality_datamart.csv` | 267 empty prices; worst month 12, worst product 14 (5.2%); no-date 11; near uniform → no unusual share | untracked | — |
| Q14 | B | DONE | `docs/answers_segment1_3.md` + `src/quality_checks.py` (QC 57) | missing 42 (32 empty + 10 placeholder) + malformed 15 = 57 flagged; usable 463 | untracked | — |
| Q15 | B | DONE | `docs/answers_segment1_3.md` + `src/quality_checks.py` (QC 2) + `src/normalise.py::parse_float` | non-numeric texts 6 = text forms 4 (Rs 60, Rs 210×2, 1,200) + unusable 2 (NA); QC 2 | untracked | — |
| Q16 | B | DONE | `docs/answers_segment1_3.md` + `data/profile.csv` | never-empty: ids + product_name; >10% empty: stock 40.00, notes 37.11, phone 20.96, discount 18.47, status 10.31 | untracked | — |
| Q17 | B | DONE | `docs/answers_segment1_3.md` + `data/quality_datamart.csv` | 142 empties (2.33%) every status 1.75–3.85% incl. Delivered; delivery metrics over 5,961 rows | untracked | — |
| Q18 | B | DONE | `docs/answers_segment1_3.md` + `data/quality_datamart.csv` | top pairs: discount+notes 408, order_status+notes 221, payment_mode+notes 218; optional-field cause | untracked | — |
| Q19 | B | DONE | `docs/answers_segment1_3.md` + `src/quality_checks.py` (QC 14) | stock unusable 14/30 (12 missing + 2 bad); Beverages 0/3; publish coverage, not totals | untracked | — |
| Q20 | C | DONE | `docs/answers_segment1_3.md` + `src/deduplication.py` + `data/duplicate_registry.csv` | repeated order_ids 103 / rows 206; conflicting groups 0; all copies exact; statuses spread | untracked | — |
| Q21 | C | DONE | `docs/answers_segment1_3.md` + `src/deduplication.py::BUSINESS_COLS` | distinct values per group: 0 differing columns in all 103 groups; double-writes, not corrections | untracked | — |
| Q22 | C | DONE | `docs/answers_segment1_3.md` + `src/deduplication.py::build_customer_master` | D03 merges 21 = 20 same-id + 1 cross-id; same normalised email = same person; 520 → 499 | untracked | — |
| Q23 | C | DONE | `docs/answers_segment1_3.md` + `src/normalise.py::norm_id` | rows changed by norm 23; distinct ids 500 = 500 (no double count); orders 693 spellings → 482 ids | untracked | — |
| Q24 | C | DONE | `docs/answers_segment1_3.md` + `data/customer_master.csv` | master 499: 479 with orders / 20 without; unmatched C9999×144, C0242×14 (remapped), blank 60 | untracked | — |
| Q25 | C | DONE | `docs/answers_segment1_3.md` + `src/deduplication.py` (D03) | shared-email groups 21; placeholder emails excluded 42; D03 runs before order dedup | untracked | — |
| Q26 | C | DONE | `docs/answers_segment1_3.md` + `src/deduplication.py::deduplicate_products` | 0 shared product names (30 distinct); D04 collisions 0 | untracked | — |
| Q27 | C | DONE | `docs/answers_segment1_3.md` + `data/duplicate_registry.csv` | repeated product_ids 0; D04 merges 0 / CONFLICT 0; norm variants 5; 30 → 30 | untracked | — |
| Q28 | C | DONE | `docs/answers_segment1_3.md` + `data/customer_master.csv` | 18/21 merges differ on city; survivor city trusted; dropped (Pune 5, Bengaluru 4, …); 5 cities intact | untracked | — |
| Q29 | C | DONE | `docs/answers_segment1_3.md` + `reports/deduplication_report.md` + `data/duplicate_registry.csv` | delivered 1,803 → 1,769; value Δ 17,760 (0.39%); commission leakage 7,756.28 (0.61%); top-3 unchanged | untracked | — |
| Q30 | D | DONE | `docs/answers_segment4_5.md` + `src/questions/seg4_cross_file.py::q30_unmatched_customers` + `sql/questions/seg4_q30.sql` | R01 exact 5620 / rescued 279 / unmatched 204 (top C9999×144); normalised rule adopted | untracked | — |
| Q31 | D | DONE | `docs/answers_segment4_5.md` + `src/questions/seg4_cross_file.py::q31_unmatched_products` + `sql/questions/seg4_q31.sql` | R02 unmatched 163; typing 0 / nonexistent 163 (P99×109, empty 54) | untracked | — |
| Q32 | D | DONE | `docs/answers_segment4_5.md` + `src/questions/seg4_cross_file.py::q32_ghost_customer_value` + `sql/questions/seg4_q32.sql` | 2 ghost customers, 204 orders, Rs 671,491.75 quarantined | untracked | — |
| Q33 | D | DONE | `docs/answers_segment4_5.md` + `src/questions/seg4_cross_file.py::q33_never_ordered_products` + `sql/questions/seg4_q33.sql` | 0 never-ordered; inactive-vs-unpopular declared unanswerable | untracked | — |
| Q34 | D | DONE | `docs/answers_segment4_5.md` + `src/questions/seg4_cross_file.py::q34_price_gap_per_product` + `sql/questions/seg4_q34.sql` | 28 gaps; 5 systematic (P16,P21,P22,P24,P29) | untracked | — |
| Q35 | D | DONE | `docs/answers_segment4_5.md` + `src/questions/seg4_cross_file.py::q35_price_closeness` + `sql/questions/seg4_q35.sql` | R06 within 558 / outside 4453 / non-positive 267 / unverifiable 825 | untracked | — |
| Q36 | D | DONE | `docs/answers_segment4_5.md` + `src/questions/seg4_cross_file.py::q36_fuzzy_attribution` + `sql/questions/seg4_q36.sql` | 279 fuzzy orders, 13.49% value; held-back list stated | untracked | — |
| Q37 | D | DONE | `docs/answers_segment4_5.md` + `src/questions/seg4_cross_file.py::q37_every_month_vs_one_month` + `sql/questions/seg4_q37.sql` | 87 months; every-month 0, one-month 161 (ghosts) | untracked | — |
| Q38 | D | DONE | `docs/answers_segment4_5.md` + `src/questions/seg4_cross_file.py::q38_orders_before_signup` + `sql/questions/seg4_q38.sql` | 1338 orders / 319 customers; signup side likelier wrong | untracked | — |
| Q39 | D | DONE | `docs/answers_segment4_5.md` + `src/questions/seg4_cross_file.py::q39_join_losses` + `sql/questions/seg4_q39.sql` | customer join drops most (483→204); per-join kept/dropped | untracked | — |
| Q40 | E | DONE | `docs/answers_segment4_5.md` + `src/questions/seg5_values.py::q40_payment_spellings` + `sql/questions/seg5_q40.sql` | 10 spellings; `cod` unassignable; mapping decisions in `mappings/proposed/` | untracked | — |
| Q41 | E | DONE | `docs/answers_segment4_5.md` + `src/questions/seg5_values.py::q41_status_spellings` + `sql/questions/seg5_q41.sql` | 10 variants; only Delivered = completed (1803) | untracked | — |
| Q42 | E | DONE | `docs/answers_segment4_5.md` + `src/questions/seg5_values.py::q42_category_pairs` + `sql/questions/seg5_q42.sql` | 3 merges, 2 keeps with reasons | untracked | — |
| Q43 | E | DONE | `docs/answers_segment4_5.md` + `src/questions/seg5_values.py::q43_quantity_kinds` + `sql/questions/seg5_q43.sql` | bad 651 (words 57, decimals 62, zero 251, neg 111, empty 170); none fixable | untracked | — |
| Q44 | E | DONE | `docs/answers_segment4_5.md` + `src/questions/seg5_values.py::q44_high_quantities` + `sql/questions/seg5_q44.sql` | fence 10.0; 77 rows at 500 = generator fault | untracked | — |
| Q45 | E | DONE | `docs/answers_segment4_5.md` + `src/questions/seg5_values.py::q45_future_dates` + `sql/questions/seg5_q45.sql` | 467 future rows, 2026-11…2027-06 wrong-year pattern | untracked | — |
| Q46 | E | DONE | `docs/answers_segment4_5.md` + `src/questions/seg5_values.py::q46_discount_forms` + `sql/questions/seg5_q46.sql` | fraction 529 / percent 2176 / zero 2271 / empty 551 / unparseable 576 | untracked | — |
| Q47 | E | DONE | `docs/answers_segment4_5.md` + `src/questions/seg5_values.py::q47_delivery_extremes` + `sql/questions/seg5_q47.sql` | Delivered neg 9 / >30 12 / missing 24; cancelled-with-days 602 | untracked | — |
| Q48 | E | DONE | `docs/answers_segment4_5.md` + `src/questions/seg5_values.py::q48_outside_cities` + `sql/questions/seg5_q48.sql` | 8 outside values; 3521 orders; Mysuru verdict deferred to business | untracked | — |
| Q49 | E | DONE | `docs/answers_segment4_5.md` + `src/questions/seg5_values.py::q49_three_unknowns` + `sql/questions/seg5_q49.sql` | 3 unknowns with column, rows (2610/142/483), masked example, unsafe decision | untracked | — |
| Q50 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q50_running_total_cross_10k` + `sql/questions/seg6_q50.sql` | running total per customer; 0 cross 10000 (empty is correct; max 9930) | untracked | — |
| Q51 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q51_avg_paid_20pct_above_catalogue` + `sql/questions/seg6_q51.sql` | correlated + join versions agree; join trusted | untracked | — |
| Q52 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q52_cte_chain_counts` + `sql/questions/seg6_q52.sql` | raw 6103 / deduped 6000 / completed 168; log-joined chain | untracked | — |
| Q53 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q53_quantity_range_check` + `sql/questions/seg6_q53.sql` | range 1–10; trigger chosen; 7 crafted rows incl boundary | untracked | — |
| Q54 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q54_rank_disagreements` + `sql/questions/seg6_q54.sql` | RANK/DENSE_RANK/ROW_NUMBER disagreements; DENSE_RANK for top-5 | untracked | — |
| Q55 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q55_new_payment_mode` + `sql/questions/seg6_q55.sql` | most-recent new payment mode; earlier = date + order_id | untracked | — |
| Q56 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q56_moving_avg_direction` + `sql/questions/seg6_q56.sql` | 3M moving avg per category + direction changes | untracked | — |
| Q57 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q57_calendar_zero_cells` + `sql/questions/seg6_q57.sql` | recursive month×category calendar; zero-filled cells counted | untracked | — |
| Q58 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q58_city_top_bottom_product` + `sql/questions/seg6_q58.sql` | FIRST/LAST_VALUE per city; alpha tiebreak | untracked | — |
| Q59 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q59_city_share_over_25pct` + `sql/questions/seg6_q59.sql` | city denominator first; >25% customers listed | untracked | — |
| Q60 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q60_dedup_determinism` + `sql/questions/seg6_q60.sql` | ROW_NUMBER dedup; shuffled rerun matches (6000) | untracked | — |
| Q61 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q61_no_recent_month_multi_category` + `sql/questions/seg6_q61.sql` | EXISTS null-safe vs IN; recent-month rule | untracked | — |
| Q62 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q62_median_delivery_percentile_vs_rank` + `sql/questions/seg6_q62.sql` | percentile_cont vs manual median; cont used | untracked | — |
| Q63 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q63_spike_detection` + `sql/questions/seg6_q63.sql` | 3x trailing spikes; 0 customers (empty correct) | untracked | — |
| Q64 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q64_function_tests` + `sql/questions/seg6_q64.sql` | stored-function normal/early/inverted behaviour | untracked | — |
| Q65 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q65_longest_active_run` + `sql/questions/seg6_q65.sql` | longest active-month run per customer (135 rows) | untracked | — |
| Q66 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q66_grouping_sets` + `sql/questions/seg6_q66.sql` | GROUPING SETS; GROUPING() labels; grand reconciles | untracked | — |
| Q67 | F | DONE | `docs/answers_segment6_7.md` + `src/questions/seg6_advanced_sql.py::q67_missing_delivery_customers` + `sql/questions/seg6_q67.sql` | delivered customers missing all delivery_days: 0 (empty correct) | untracked | — |
| Q68 | G | DONE | `docs/answers_segment6_7.md` + `src/questions/seg7_professional_sql.py::q68_sessions` + `sql/questions/seg7_q68.sql` | 30-min sessions analogue (no intra-day timestamps; date-level) | untracked | — |
| Q69 | G | DONE | `docs/answers_segment6_7.md` + `src/questions/seg7_professional_sql.py::q69_plan_analysis` + `sql/questions/seg7_q69.sql` | live EXPLAIN join type + monthly partition/index proposal + tradeoff | untracked | — |
| Q70 | G | DONE | `docs/answers_segment6_7.md` + `src/questions/seg7_professional_sql.py::q70_referral_depth` + `sql/questions/seg7_q70.sql` | referral analogue (referral_id absent): 499 customers, 0 chains | untracked | — |
| Q71 | G | DONE | `docs/answers_segment6_7.md` + `src/questions/seg7_professional_sql.py::q71_p95_exact_vs_approx` + `sql/questions/seg7_q71.sql` | exact vs 1-in-10 subsample p95; board needs exact | untracked | — |
| Q72 | G | DONE | `docs/answers_segment6_7.md` + `src/questions/seg7_professional_sql.py::q72_lateral_rule_strings` + `sql/questions/seg7_q72.sql` | LATERAL rule strings on source_row_number (168 rows) | untracked | — |
| Q73 | G | DONE | `docs/answers_segment6_7.md` + `src/questions/seg7_professional_sql.py::q73_funnel` + `sql/questions/seg7_q73.sql` | funnel analogue (no browse events; 14d windows) | untracked | — |
| Q74 | G | DONE | `docs/answers_segment6_7.md` + `src/questions/seg7_professional_sql.py::q74_transition_classes` + `sql/questions/seg7_q74.sql` | snapshot classification analogue (no transition log) | untracked | — |
| Q75 | G | DONE | `docs/answers_segment6_7.md` + `src/questions/seg7_professional_sql.py::q75_scorecard` + `sql/questions/seg7_q75.sql` | scorecard 0–100 (30/20/30/20 weights; gaming notes) | untracked | — |
| Q76 | H | DONE | `docs/answers_segment8_9.md` + `src/questions/seg8_expert_sql.py::q76_lateral_equivalence` + `sql/questions/seg8_q76.sql` | counterexample: tie breaks LATERAL≡window; total ordering restores it | untracked | — |
| Q77 | H | DONE | `docs/answers_segment8_9.md` + `src/questions/seg8_expert_sql.py::q77_float_sum_order` + `sql/questions/seg8_q77.sql` | 7 cities, no cent diffs on data; (0.1+0.2)+0.3 proof; NUMERIC fix + costs | untracked | — |
| Q78 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q78_mom_by_city` + `sql/questions/seg9_q78.sql` | 97 city-months; MoM NULL (never 0); first month NULL | untracked | — |
| Q79 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q79_median_gap` + `sql/questions/seg9_q79.sql` | 292 customers; 159 single-order → NULL (never 0) | untracked | — |
| Q80 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q80_three_recent_nondelivered` + `sql/questions/seg9_q80.sql` | 20 customers; date-only tiebreak also 20 (0 change) | untracked | — |
| Q81 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q81_top10pct_share` + `sql/questions/seg9_q81.sql` | 6 categories; NTILE splits ties via product_id | untracked | — |
| Q82 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q82_longest_zero_run` + `sql/questions/seg9_q82.sql` | 576 days (2022-06-06→2024-01-02); island boundaries | untracked | — |
| Q83 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q83_except_vs_not_exists` + `sql/questions/seg9_q83.sql` | 89 customers both methods; NULL semantics explained | untracked | — |
| Q84 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q84_second_highest` + `sql/questions/seg9_q84.sql` | 7 cities rank-2 values; DENSE vs ROW_NUMBER rule | untracked | — |
| Q85 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q85_discount_implied_gap` + `sql/questions/seg9_q85.sql` | top-5 gaps (O00661/P16 133.33); fraction reading; percent alt noted | untracked | — |
| Q86 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q86_latest_three_array` + `sql/questions/seg9_q86.sql` | 126 customers; 1 top-3 date tie; order_id rule | untracked | — |
| Q87 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9c_expert_data.py::q87_grouping_sets` + `sql/questions/seg9_q87.sql` | 32 cells; grand 118820.50 reconciles; GROUPING() labels | untracked | — |
| Q88 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9c_expert_data.py::q88_median_monthly_qty` + `sql/questions/seg9_q88.sql` | 47 products, 0 all-above; global-median contrast | untracked | — |
| Q89 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9c_expert_data.py::q89_range_90d` + `sql/questions/seg9_q89.sql` | 486 city-dates; RANGE frames span, DISTINCT exact; ROWS contrast | untracked | — |
| Q90 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9c_expert_data.py::q90_cohort` + `sql/questions/seg9_q90.sql` | 86 cohort-offsets; right-censoring rule | untracked | — |
| Q91 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9c_expert_data.py::q91_p95_flags` + `sql/questions/seg9_q91.sql` | city flags 4, global 2, changed 2; city bar for managers | untracked | — |
| Q92 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9c_expert_data.py::q92_dup_email_pairs` + `sql/questions/seg9_q92.sql` | 0 pairs (empty correct); phone-insufficiency rule | untracked | — |
| Q93 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9c_expert_data.py::q93_180d_categories` + `sql/questions/seg9_q93.sql` | 100 customers; [2026-04-14, 2026-10-11] inclusive | untracked | — |
| Q94 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9c_expert_data.py::q94_herfindahl` + `sql/questions/seg9_q94.sql` | 7 HHIs; dropping smallest city changes nothing else | untracked | — |
| Q95 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q95_four_rising_months` + `sql/questions/seg9_q95.sql` | 0 customers (empty correct); islands-required rule | untracked | — |
| Q96 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q96_paid_over_catalogue` + `sql/questions/seg9_q96.sql` | 7 orders; scalar subquery; dup-guard (none exist) | untracked | — |
| Q97 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q97_ma_yoy` + `sql/questions/seg9_q97.sql` | 90 rows; 3M MA + month-12 YoY; first 12 NULL | untracked | — |
| Q98 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q98_latest_payment_switch` + `sql/questions/seg9_q98.sql` | 495 pairs / 290 customers; alt tiebreak 494 (1 change) | untracked | — |
| Q99 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q99_top2_ranks_city` + `sql/questions/seg9_q99.sql` | 14 rows; all cities return exactly 2 (no ties) | untracked | — |
| Q100 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q100_same_day_pairs` + `sql/questions/seg9_q100.sql` | 0 pairs (empty correct); canonical a<b; basket evidence rule | untracked | — |
| Q101 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q101_delivery_pivot` + `sql/questions/seg9_q101.sql` | 20 cells; NULLs excluded; top UNMAPPED/UNMAPPED 4.32d | untracked | — |
| Q102 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q102_tenth_order` + `sql/questions/seg9_q102.sql` | 0 (empty correct); earlier_n=9; id tiebreak | untracked | — |
| Q103 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q103_never_completed` + `sql/questions/seg9_q103.sql` | P-10/P02/P19 both methods; NULL-poison demo branch | untracked | — |
| Q104 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q104_notes_vs_late` + `sql/questions/seg9_q104.sql` | 7 cities; late = above city median; pattern stated | untracked | — |
| Q105 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q105_top_product_lateral` + `sql/questions/seg9_q105.sql` | 126 customers; lateral≡FIRST_VALUE on shared tiebreak | untracked | — |
| Q106 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q106_cte_reconcile` + `sql/questions/seg9_q106.sql` | grand 118820.50 = city = category; view-edit risk | untracked | — |
| Q107 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q107_first_above_avg` + `sql/questions/seg9_q107.sql` | 47 products; 41 never above own average | untracked | — |
| Q108 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q108_orders_prior_30d` + `sql/questions/seg9_q108.sql` | 522 orders; engines agree all rows; boundary-day rules | untracked | — |
| Q109 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9a_expert_data.py::q109_qty_outliers` + `sql/questions/seg9_q109.sql` | 0 before / 0 after; STDDEV_POP; exclusion-flip rule | untracked | — |
| Q110 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9c_expert_data.py::q110_id_mismatches` + `sql/questions/seg9_q110.sql` | 21 ids by direction; city-blindness of orders_only | untracked | — |
| Q111 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9c_expert_data.py::q111_share_shift` + `sql/questions/seg9_q111.sql` | movers UNKNOWN +12.31pp / Grocery −12.11pp; midpoint rule | untracked | — |
| Q112 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9c_expert_data.py::q112_pairs_top5` + `sql/questions/seg9_q112.sql` | P08×P17 n=1; canonical a<b avoids doubling | untracked | — |
| Q113 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9b_expert_data.py::q113_cancel_rate_p90` + `sql/questions/seg9_q113.sql` | C0196 0.80 > p90 0.66; filter-before-percentile rule | untracked | — |
| Q114 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9b_expert_data.py::q114_units_per_product_month` + `sql/questions/seg9_q114.sql` | 383 rows via SUM(qty); expansion-inefficiency rule | untracked | — |
| Q115 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9b_expert_data.py::q115_city_count_drops` + `sql/questions/seg9_q115.sql` | 12 drop months; subquery-then-LAG workaround | untracked | — |
| Q116 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9b_expert_data.py::q116_gini_by_city` + `sql/questions/seg9_q116.sql` | Bengaluru 0.6328 … Hyderabad 0.3335; formula + targeting | untracked | — |
| Q117 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9b_expert_data.py::q117_mode_vs_recent` + `sql/questions/seg9_q117.sql` | 51 differ; reversed tiebreak 47 (4 change) | untracked | — |
| Q118 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9b_expert_data.py::q118_delivery_bands` + `sql/questions/seg9_q118.sql` | 26 city-bands; outside_or_invalid rule for NULL/neg/>7 | untracked | — |
| Q119 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9b_expert_data.py::q119_signup_cohort_speed` + `sql/questions/seg9_q119.sql` | 34 cohorts; best 2024-08 (54.0d); negatives excluded+counted | untracked | — |
| Q120 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9b_expert_data.py::q120_completed_view_check` + `sql/questions/seg9_q120.sql` | `v_completed_line_values` 10 cols; no raw text; limits stated | untracked | — |
| Q121 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9b_expert_data.py::q121_empty_city_category` + `sql/questions/seg9_q121.sql` | 10 zero combos; structural-vs-data test stated | untracked | — |
| Q122 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9b_expert_data.py::q122_rank1_three_months` + `sql/questions/seg9_q122.sql` | 10 products (P-30×16 …); tie-inflation rule | untracked | — |
| Q123 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9b_expert_data.py::q123_division_all_categories` + `sql/questions/seg9_q123.sql` | 0 (empty correct); blank-category divergence rule | untracked | — |
| Q124 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9b_expert_data.py::q124_price_mismatch_spikes` + `sql/questions/seg9_q124.sql` | 55 rows; no-catalogue exclusion; 0→0 degenerate flags noted | untracked | — |
| Q125 | I | DONE | `docs/answers_segment8_9.md` + `src/questions/seg9b_expert_data.py::q125_mega_top3` + `sql/questions/seg9_q125.sql` | Bengaluru/Pune/Chennai + top cats + shares; 10x failure = sort spill | untracked | — |

Total: DONE 125 (Q1–125) · NOT DONE 0. Q1–29 flipped on 2026-10-17 after `docs/answers_segment1_3.md` supplied the 29 missing prose answers.
