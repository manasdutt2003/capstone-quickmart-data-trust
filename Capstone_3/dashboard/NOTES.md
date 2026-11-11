# NOTES.md — QuickMart Dashboard Rebuild

Date: 2026-10-17 · Scope: `dashboard/` rebuild for `uvicorn main:app --reload`

## 1. What I read, and what it says

### dashboard/ (as found)
- `index.html` — 320 KB machine-generated single-file page written by `src/dashboard.py`
  (one inline `<script>` block plus embedded JSON, typographic characters `·` `—` in text).
- `data.json` — pipeline payload: 23 acceptance criteria, 5 capstone problems, 125 data
  questions (125 DONE), validations, rubric (self-assessed 75), insights,
  provenance hashes, series (monthly 36, payment_mix 241, top_customers 10, delivery 35).
- `charts.js` — a small Chart.js add-on I had appended earlier (now replaced).
- `main.py` — FastAPI host previously serving the legacy page (now rebuilt).
- `requirements.txt` — unpinned (now pinned in this rebuild).

### charts/monthly_sales.png (visual reference)
Matplotlib bar chart: title "Delivered sales by month (trusted orders)", y-axis "Rs",
x-axis = order_month (rotated 90°), single steel-blue series (`#1f77b4`), tall spike at
2026-07 (~Rs 510 K). The new dashboard's monthly chart mirrors this: vertical bars, same
single-series style, Rs axis, rotated month labels, same palette accent `#1f77b4`.

### data/ (source of truth for marts)
- `sales_datamart.csv` 450 rows (month × city × category). Grand total **Rs 2,309,394.00**,
  799 delivered orders — reconciles to `report_validation.csv`.
- `payment_datamart.csv` (month × city × payment), total Rs 7,983,286.25 (all statuses).
- `customer_value_datamart.csv` 333 rows; top customer Rs 244,965.00 (raw id masked here).
- `cohort_datamart.csv` 616 rows (signup_month × order_month), total Rs 2,309,394.00.
- `delivery_datamart.csv` city × category: orders, avg/median days, impossible/negative/
  over-30/missing counts.
- `quality_datamart.csv` 6,103 rows × 48 cols incl. 14 `flag_QC_*` booleans + `n_issues`.
- `quality_scorecard.csv` customers 98.07 %, products 96.46 %, orders 96.80 %.
- `profile.csv` (22 column profiles), `issue_registry.csv` (12 QC rules), `duplicate_registry.csv`.
- `commission_datamart.csv` + 8 commission cut files (before/after, by city/month/payment/status).
- `rule_failure_log.csv` (per-order R01–R11 booleans), `validation_datamart.csv` (same shape).
- `raw_manifest.json` (extract SHA-256, row counts: customers 520, products 30, orders 6,103).
- `report_validation.csv` — 4 PASS figures: Rs 2,309,394.00; Bengaluru Rs 737,658.25;
  Grocery Rs 960,025.25; 799 delivered orders.

### outputs/ (current sprint populations — used by the trust panels)
- `lenient_trusted_orders.csv` **522 rows / Rs 455,160.75** (FAIL excluded, WARNING kept).
- `trusted_orders.csv` identical copy; `strict_trusted_orders.csv` **115 rows / Rs 79,738.50**.
- `rejected_orders.csv` 5,478 rows. Waterfall: raw 6,103 → clean 6,000 (=522+5,478).
- `rule_failure_log.csv` 15,103 rows (rule × order × FAIL/WARNING): R01 198, R02 159,
  R03 1,851, R04 833, R05 718, R06 4,636 F + 814 W, R07 561, R08 623, R10 75, R12 175;
  R09/R11 only WARNINGs. Rule names from the legacy page: R01 Customer Exists … R12
  Cross-field Business Rule.

### sql/
- Core pipeline scripts `00_staging.sql` … `08_rule_views.sql`, `v_line_value.sql`
  (single line-value definition — criterion 12).
- `sql/questions/seg*_q*.sql`: one file per data question (~100 files). Saved ASCII results
  for Q50–Q125 live in `data/SQL_OUTPUTS/` (and `data/output/`): exposed per-question via
  `/api/sql-file/{qid}` and the Questions explorer.

### Capstone 2 (QuickMart_Mock_Project.html)
Business: ~500 customers, 30 products, 3 messy extracts, "today" = 2026-10-11. Five
problems: Q1 trust/where-it-breaks · Q2 commission on orders that never happened ·
Q3 which orders can be signed off · Q4 what to tell leadership · Q5 weekly refresh +
LLM report. 23 acceptance criteria, 5-area rubric (score 75 = all Working). 125 data
questions in 9 segments (A loading → I expert SQL).

## 2. Root cause of the reported VS Code problems (one line)
The legacy `dashboard/index.html` is a machine-generated single-file page whose huge
inline `<script>` block mixes raw JS with HTML-escaped JSON and typographic characters
(`·`, `—`), so VS Code's JavaScript parsing of the embedded script reports "Invalid
character" / "')' expected" at the reported positions — fixed here by rebuilding the UI
from scratch with **zero inline JavaScript** (all JS lives in `/static/*.js` files).

## 3. Rebuild — files
```
dashboard/
  main.py            FastAPI app (run: uvicorn main:app --reload)
  requirements.txt   pinned
  NOTES.md  README.md
  templates/index.html      clean shell (no inline JS, no CDN)
  static/styles.css         palette from monthly_sales.png + capstone colours
  static/charts.js          all Chart.js construction
  static/app.js             fetch/filter/tables/count-up/theme/CSV download
  static/vendor/chart.umd.min.js   Chart.js 4.4.1 vendored locally (offline)
  tests/                    smoke_api.py (TestClient) + live_check.py (live server)
  data.json                kept - source for /api/manifest, /api/questions, /api/capstone
  archive/                 legacy index.html + charts.js moved aside (kept for reference)
```

## 4. Question → panel → endpoint mapping

### Capstone business questions (Q1–Q5)
| Question | Panel | Endpoint |
|---|---|---|
| Q1 Can we trust the data / where does it break? | Trust waterfall · Quality scorecard · Rule failures · Issue heatmap city × month · Profiling table | `/api/trust`, `/api/quality/scorecard`, `/api/quality/rules`, `/api/quality/heatmap`, `/api/quality/profile` |
| Q2 Commission on orders that never happened | Trust waterfall · Duplicates & dedup · Commission before/after by city / payment / status | `/api/trust`, `/api/duplicates`, `/api/commission` |
| Q3 Which orders can I put my name to? | Waterfall (lenient vs strict vs rejected) · Rule-failure table by city/month/category (validation cuts) · Top-5 lenient/strict | `/api/trust`, `/api/quality/rules`, `/api/sql-file/…` (R-rule cuts) |
| Q4 What do I tell leadership? | KPIs · Monthly sales (reference style) · City & category cuts · Payment mix · Top customers · Cohort · Delivery performance | `/api/kpis`, `/api/monthly-sales`, `/api/sales-cuts`, `/api/payment-mix`, `/api/top-customers`, `/api/cohort`, `/api/delivery` |
| Q5 Every-Monday refresh + LLM report | Verification/criteria panel · Questions explorer · Insights (VERIFIED figures traced to marts) | `/api/manifest`, `/api/questions`, `/api/capstone` |

### 125 data questions (segments A–I)
| Segment (questions) | Dashboard panel | Endpoint |
|---|---|---|
| A Loading & shape (1–9) | Meta/freshness card + Profiling table | `/api/meta`, `/api/quality/profile` |
| B Completeness (10–19) | Profiling table (missing %) · Issue registry | `/api/quality/profile`, `/api/quality/issues` |
| C Identity & duplicates (20–29) | Duplicates & dedup panel | `/api/duplicates` |
| D Across extracts (30–39) | Trust waterfall · Rule failures · Cross-file notes in Capstone answers | `/api/trust`, `/api/quality/rules` |
| E Values & meaning (40–49) | Payment mix · Rule failures (status/payment labels) | `/api/payment-mix`, `/api/quality/rules` |
| F Advanced SQL (50–67) | Questions explorer (per-question answer + saved result) | `/api/questions`, `/api/sql-file/{qid}` |
| G Professional SQL (68–75) | Questions explorer (analogue rows flagged) | `/api/questions` |
| H Expert SQL (76–77) | Questions explorer | `/api/questions` |
| I Expert SQL on QuickMart (78–125) | Monthly/city/category sales · Cohort · Delivery · Top customers · Questions explorer | `/api/monthly-sales`, `/api/sales-cuts`, `/api/cohort`, `/api/delivery`, `/api/top-customers`, `/api/questions`, `/api/sql-file/{qid}` |

Every one of the 125 questions is listed in the Questions explorer with its status and
headline answer (`/api/questions`); all 125 are DONE in `docs/question_ledger.md` and
Q1-29 carry their Method and Result details from `docs/answers_segment1_3.md` (parsed
into the payload at build time). Statuses are read from that ledger: if a row were
marked NOT DONE again, its ledger reason would render as "Missing sub-part: ..." and
no invented numbers would be shown.

## 5. Figures shown as n/a (and why)
- **Weekly-refresh scheduling / LLM runtime** — `src/refresh.py` is absent and the LLM run
  is pending; the dashboard reports criterion 22/23 status honestly rather than a number.
- **Stock level reporting** — `products.stock_qty` unusable in every category (per pipeline
  notes), so no stock panel; flagged in Notes next-steps.
- **True delivery promises** — no promise timestamp exists in the extracts; only actual
  `delivery_days` is shown.
- **Post-2026-10 (future months)** — no orders; charts simply end at the data range.
- **Legacy 2,385-row trusted file** in `data/trusted_orders.csv` differs from the current
  sprint's 522-row lenient output; the dashboard uses `outputs/` for trust panels and the
  marts (`data/*.csv`) for leadership panels, keeping each number to its own source file.

## 6. Choices made
- Trust panels read `outputs/*.csv`; leadership/mart panels read `data/*.csv` — each number
  is quoted from exactly one committed file (no re-derivation drift).
- Customer ids masked everywhere: `#rank` labels or short SHA-1 hashes; no names, emails,
  phones or notes are served by any endpoint.
- All API payloads sanitised with `JsonSafe` (NaN/Inf → null, numpy scalars → Python).
- Chart.js 4.4.1 vendored at `/static/vendor/chart.umd.min.js`; the page works offline.
- Heatmap = % of orders with ≥1 quality issue per city × month (from `n_issues`).
