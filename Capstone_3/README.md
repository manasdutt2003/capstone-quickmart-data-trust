# QuickMart — Manas Dutt (Week 3, GGTP BLR)

Grocery delivery across four cities. Three messy extracts, no clean version of the truth. This repo takes the files exactly as received and delivers numbers the room will not argue with: every order excluded, changed or questioned is counted, explained, and traceable back to a received row. Rerunning on the same files gives the same answer.

## The business and who is waiting

| Stakeholder | Needs |
|---|---|
| Neha, Operations Manager | Numbers for leadership next Monday that reconcile every way they are cut |
| Arjun, Finance Lead | A checked order count before paying delivery-partner commission |
| Priya, Warehouse Lead | Orders the warehouse actually shipped, not inflated reports |
| Customers | No duplicate orders in the app, correct delivery estimates |

## Ground rules (from the brief, enforced in code)

1. The files are the source of truth — never edited by hand; everything traces to a received row.
2. Every excluded/changed/questioned order is counted and explained.
3. No cleaner version exists to compare against; "correct" is decided and justified per problem.
4. SQL, Python or both — everything repeatable: same files, same answer.
5. "Today" is **11 October 2026** everywhere (single constant).

## What arrived on Monday (`Resources/.../Capstone 2/data`, read-only)

| Extract | Rows | Columns |
|---|---|---|
| `customers.csv` | 520 | customer_id, customer_name, email, city, phone, signup_date |
| `products.csv` | 30 | product_id, product_name, category, unit_price, stock_qty |
| `orders.csv` | 6103 | order_id, customer_id, product_id, order_date, quantity, unit_price_paid, discount, payment_mode, order_status, delivery_days, notes |

Three systems, hand-typed fields, never reconciled. Load keeps every raw value as text (`src/data_loader.py`).

## The five problems — question, approach, result, decision

**Q1 — Can we trust any of this, and where does it break?** Profiled all 22 columns; counted empties, placeholders and unusable values; cut by city, month, category and payment; mapped which problems travel together. Result: breakage concentrates (not scatters); fit-to-report judgement per business area. Decision: quarantine weak areas visibly instead of one global score that would hide the concentration.

**Q2 — Paying commission on orders that never happened.** Separated whole-row copies (D01), conflicting repeats (D02), same-person customers (D03) and product repeats (D04); reconciled by id, by line and by customer/product/date. Result: 6,103 rows in, 6,000 clean; commission leakage Rs 7,756.28 priced before/after each rule. Decision: dedup order D01>D03-remap>D02>D05, D06 flag-only — blanket-deleting repeats would erase genuine repeat purchases.

**Q3 — Which orders can I put my name to?** Twelve checks R01–R12 across customer, product, price, date, quantity and status; each check's removals counted by city/month/category; strict vs lenient populations compared. Result: lenient 522 rows, strict 115, rejected 5,478 (of which 407 are WARNING-only). Decision: lenient (FAIL excluded, WARNING kept) feeds every Q4 answer — strict drops valid delivered orders, legacy R01–R11 keeps R12 failures.

**Q4 — What do I tell leadership?** Trusted delivered orders only, one line-value definition, cuts by month/city/category/payment/tenure. Result: delivered sales Rs 2,309,394.00 across 799 orders, identical by city, category and month; ties flagged not hidden; impossible delivery days set aside and counted. Decision: delivered-only revenue with DENSE_RANK tops and city-level delivery bars — all-status figures would smuggle cancelled value back in.

**Q5 — Every Monday, written for people who will not read a table.** Five datamarts at stated grains with a no-code-change refresh contract; leadership prose drafted by an open-weights model given only aggregated mart JSON; every drafted figure verified against a mart. Result: 8/8 rule-based insights VERIFIED; model drafts verify-or-reject the same way (temperature 0, seed 42, recorded model/version/settings/prompt). Decision: ship the rule-based set, verify model drafts before they reach anyone — unchecked drafts invent figures (the test suite plants Rs 9,999,999.99 and the verifier catches it).

## Pipeline and architecture

```
extracts ──▶ load (text-preserving) ──▶ clean ──▶ dedup D01>D03>D02>D05 ──▶ R01–R12 validate ──▶ trusted
   │                                                                                                  │
   │                                                                                                  ▼
   │                                                                               enrich ──▶ 5 marts ──▶ LLM insights + reports + dashboard
```

Full diagram: [`data/architecture.svg`](data/architecture.svg). Row ledger: 6,103 raw → 6,000 clean (= 522 lenient + 5,478 rejected); 115 strict + 407 warnings. See `docs/waterfall.md`.

## Repository map

`src/` pipeline + rules + marts + question modules (`src/questions/seg4…seg9*`) · `sql/` staging/dedup/trusted/marts + 96 question files (`sql/questions/`) · `tests/` full suite incl. SQL↔Python parity · `data/` pipeline outputs · `outputs/` trusted populations · `mappings/proposed/` value mappings (40 rows — human sign-off pending) · `reports/` human reports + LLM records · `dashboard/` offline presentation (`index.html`, one file, no network) · `docs/` answers, ledger, judgement calls, presentation script · `prompts/` fixed model prompts · `config/` settings + rubric self-assessment.

## Run it

```powershell
python -m src.pipeline            # one command, deterministic
python -m src.pipeline --verify-hashes
python -m pytest tests -q         # 398 passed
ruff check src tests; python -m mypy src
python -m src.criteria_check --write-cache   # live 23-criteria verification
python -m src.dashboard_data; python -m src.dashboard
```

Open `dashboard/index.html` (present with arrow keys) for the 10-minute walkthrough; talk track in `docs/presentation_script.md`.

## Acceptance criteria — honest scorecard

23 criteria, verified live (`python -m src.criteria_check`): **20 PASS, 2 PARTIAL, 1 FAIL**, rubric self-score 75.0. Not fully met: **#11 FAIL** — all 40 mapping rows still lack `approved_by` (needed before Q4 cites them); **#22 PARTIAL** — marts reconcile, but `src/refresh.py` is not written yet; **#4 PARTIAL** — tests collect and run, but PR gating and main-branch protection are GitHub-side settings. No secrets committed (`.env` is gitignored and untracked).

## Evidence index

Pipeline + hashes: `src/pipeline.py`, `reference/output_hashes.json` · extracts: `reference/extract_manifest.json` · rules: `src/validation_rules.py`, `docs/rule_catalog.md` · issues: `data/issue_registry.csv` · dedup: `reports/deduplication_report.md` · trusted: `docs/waterfall.md`, `docs/trusted_order_framework.md` · questions: `docs/answers_segment1_3.md`, `docs/answers_segment4_5.md`, `docs/answers_segment6_7.md`, `docs/answers_segment8_9.md`, `docs/question_ledger.md` (Q1–125 DONE) · decisions: `docs/judgement_calls.md` (13 calls, each with alternative + quantified effect) · LLM: `src/llm_insights.py`, `reports/llm_insights.json`, `reports/llm_run_record.json` · dashboard: `dashboard/index.html`, `specs.md`, `project-plan.md`.

## Walkthrough — the number I am least sure of

The 407 WARNING-only rows behind the lenient-vs-strict delta: each is individually defensible, but as a group they move leadership value. I defend it with the waterfall (every row traced to `rule_failure_log`) and the R12c WARNING-only rule — re-running the strict-vs-lenient split on any new extract reproduces it exactly. Three things this data cannot tell Neha: stock availability, true delivery promises, ghost-customer identity.
