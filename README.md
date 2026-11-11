# QuickMart — Data Trust Pipeline

Three messy extracts, no clean version of the truth, and a leadership deck due Monday.
This pipeline takes the files **exactly as received** and produces numbers the room will not
argue with: every order excluded, changed or questioned is counted, explained and traceable
back to a received row. Same files in, same answer out, every time.

> Week 3 individual capstone · Perficient Global AI First Academy · Author: **Manas Dutt**

## Results

| | |
|---|---|
| Raw orders ingested | **6,103** → 6,000 clean |
| Validation rules | **12** (R01–R12) |
| Tests passing | **398** |
| Commission leakage priced | **₹7,756.28** |
| Delivered sales reconciled | **₹2,309,394.00** across 799 orders |
| Acceptance criteria | 23 verified live — **20 PASS, 2 PARTIAL, 1 FAIL** |

## The business

A grocery delivery business across four cities, with three systems that were never reconciled.

| Stakeholder | Needs |
|---|---|
| Operations Manager | Numbers for leadership that reconcile every way they are cut |
| Finance Lead | A checked order count before paying delivery-partner commission |
| Warehouse Lead | Orders the warehouse actually shipped, not inflated reports |
| Customers | No duplicate orders in the app, correct delivery estimates |

**Ground rules, enforced in code:** the files are the source of truth and are never edited by
hand; every excluded or changed order is counted and explained; "correct" is decided and
justified per problem; everything is repeatable — same files, same answer.

## The five questions

1. **Can we trust any of this?** All 22 columns profiled; breakage is shown to *concentrate*
   rather than scatter, so weak areas are quarantined visibly instead of hidden behind one
   global score.
2. **Are we paying commission on orders that never happened?** Whole-row copies, conflicting
   repeats, same-person customers and product repeats separated into four classes and applied
   in a defended order, so genuine repeat purchases survive.
3. **Which orders can I put my name to?** Twelve checks across customer, product, price, date,
   quantity and status; strict vs lenient populations compared and the delta defended row by row.
4. **What do I tell leadership?** Delivered-only revenue, one line-value definition, identical
   by city, category and month; ties flagged rather than hidden.
5. **How does this run every Monday?** Five datamarts with a no-code-change refresh contract,
   and leadership prose drafted by a model **then verified figure by figure** against a mart.

## Pipeline

```
extracts ──▶ load (text-preserving) ──▶ clean ──▶ dedup ──▶ R01–R12 validate ──▶ trusted
   │                                                                               │
   │                                                                               ▼
   └──────────────────────────────────▶ enrich ──▶ 5 marts ──▶ LLM insights + reports + dashboard
```

Row ledger: 6,103 raw → 6,000 clean (= 522 lenient + 5,478 rejected); 115 strict + 407 warnings.

## LLM insights, verified not trusted

Leadership prose is drafted from aggregated mart JSON at temperature 0 / seed 42, with the
model, version, settings and prompt all recorded. **Every drafted figure is then checked against
a mart.** The test suite plants a fake `₹9,999,999.99` and the verifier catches it. Rule-based
insights ship; model drafts verify-or-reject the same way.

## Run it

```bash
cd Capstone_3
python -m src.pipeline                        # one command, deterministic
python -m src.pipeline --verify-hashes
python -m pytest tests -q                     # 398 passed
ruff check src tests && python -m mypy src
python -m src.criteria_check --write-cache    # live 23-criteria verification
python -m src.dashboard_data && python -m src.dashboard
```

Open `Capstone_3/dashboard/index.html` (arrow keys) for the walkthrough.

## Honest scorecard

Not everything is done, and the repo says so. **#11 FAIL** — all 40 mapping rows still lack
`approved_by`. **#22 PARTIAL** — marts reconcile but `src/refresh.py` is not written.
**#4 PARTIAL** — tests run, but PR gating is a GitHub-side setting.

## Layout

`src/` pipeline, rules, marts · `sql/` staging/dedup/trusted/marts + 96 question files ·
`tests/` full suite incl. SQL↔Python parity · `data/` outputs · `reports/` human reports and
LLM records · `dashboard/` offline presentation · `docs/` answers, ledger, judgement calls

Full detail: [`Capstone_3/README.md`](Capstone_3/README.md)

> **Note:** the datasets here are course-provided sample data for a fictional retail scenario.
