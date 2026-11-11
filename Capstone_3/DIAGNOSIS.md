# DIAGNOSIS.md — Why Q1–29 show "NOT DONE" on the dashboard

Date: 2026-10-17 · Scope: read-only investigation of the question-status pipeline
(no code changed at investigation time). Evidence scripts left at project root:
`_diag_probe.py`, `_diag_probe2.py` (safe to delete after review).

**Update (later on 2026-10-17): Phase 1 fixes applied and verified — see section 8.**

---

## TL;DR

1. **Where the status comes from:** it is *not* computed from answers, SQL files or
   outputs. It is a **hand-maintained field in `docs/question_ledger.md`**, read by
   `src/dashboard_data.py`, written into `dashboard/data.json`, served by
   `dashboard/main.py` (`/api/questions`) and rendered by `dashboard/static/app.js`.
2. **The exact rule:** `ledger_rows()` parses each ledger row with
   `re.match(r"\| Q(\d+) \| (\S+) \| (\S+) \|", line)`. The status cell must be a
   **single token** (`(\S+)`). For Q1–29 the cell is the **two-word** "NOT DONE",
   which cannot match, so those ids are absent from the parsed ledger and the code
   falls through to its literal default:
   `ledger.get(num, {}).get("status", "NOT DONE")` — i.e. **Q1–29 display the
   fallback default, not the ledger value**. (The fallback happens to equal the
   intended status, so today's UI is coincidentally correct; a ledger edit for
   these rows can never influence the dashboard unless written as one word.)
3. **The human-meaningful reason (from the ledger itself):** the counts exist, but
   the **explanation prose / decision statements were never written** for these 29
   questions. The ledger's rule: *"DONE only with an opened evidence file and every
   sub-part answered"*; these rows say e.g. *"reason: row-by-row difference
   explanation prose not written"*. `docs/` contains answer prose only for segments
   4–9 (`answers_segment4_5.md`, `answers_segment6_7.md`, `answers_segment8_9.md`).
4. **None of the 29 is** "SQL exists but no output" or "output exists but the UI
   is not linked". There is **no SQL and no per-question function for Q1–29 at all**
   (segments 1–3 are file-only questions per the capstone brief), and the dashboard
   payload deliberately gives them a stub (`result.kind = "pending"`, empty
   `code`/`sql`, `parity_tested = false`).
5. **Extra cross-check finding (not the cause):** segment letters disagree between
   the dashboard payload and the ledger/capstone for Q10–29
   (dashboard: A=1–19, B=20–29, **no C**; ledger/brief: A=1–9, B=10–19, C=20–29).
   The dashboard's "C · Identity" filter therefore renders nothing.

---

## 1. Where the question list and its status come from

Chain, in order (verified end-to-end):

| Step | File / line | What happens |
|---|---|---|
| 1 | `docs/question_ledger.md` (rule on lines 4–9; the 29 rows on lines 17–45; totals line 143) | Authoritative, human-written table: `| id | seg | status | …`. Footer: *"Total: DONE 96 (Q30–125) · NOT DONE 29 (Q1–29, explanation prose missing)."* |
| 2 | `src/dashboard_data.py::ledger_rows()` (lines 266–275) | Reads the markdown, regex-parses rows, keeps `status`. |
| 3 | `src/dashboard_data.py::build_questions()` (lines 278–357) | Attaches `status`, `title`, `code`, `sql`, `result` per question. Q30–125 are computed by importing the `src/questions/seg4…seg9` modules (lines 319–341). Q1–29 are a separate loop (lines 342–356) emitting a **hard-coded "pending" stub**. |
| 4 | `src/dashboard_data.py::build()` / `__main__` (lines 626–632, 675–684) | Writes the payload to `dashboard/data.json`. |
| 5 | `dashboard/main.py` `/api/questions` (`_trim_question`) | Serves `status` (and everything else) verbatim; only trims the bulky result payload. |
| 6 | `dashboard/templates/index.html` + `static/app.js::renderQuestions()` | Renders the status badge (`DONE` / `NOT DONE`) and the headline. `charts.js` plays no role. |

Question **titles** come from `src/dashboard_data.py::QUESTION_TITLES`
(lines 45–111). The Capstone 2 brief itself only names the nine segments and the
count ("125 questions … in nine segments"); it does not enumerate the 125 texts.
Nothing is hard-coded in `index.html`/`charts.js` (the archived legacy page
embedded the same `data.json`).

## 2. The exact rule that sets "NOT DONE"

```python
# src/dashboard_data.py, lines 266–275
m = re.match(r"\| Q(\d+) \| (\S+) \| (\S+) \|", line)
if m:
    rows[int(m.group(1))] = {"seg": m.group(2), "status": m.group(3), ...}
```

```python
# line 333 (Q30–125) and line 348 (Q1–29) — same fallback string
"status": ledger.get(num, {}).get("status", "NOT DONE"),
```

Behaviour, proven by running the real function (`_diag_probe2.py`):

- `ledger_rows()` returns **exactly 96 ids, 30–125** — all single-word `DONE`.
- **Q1–29 do not parse**: `| Q1 | A | NOT DONE | …` — the third capture group
  `(\S+)` cannot span the space in "NOT DONE" (group would match `NOT`, then the
  regex expects ` |` and sees `D`), so the whole line is skipped.
- The skipped ids fall through to the **literal default `"NOT DONE"`** in
  `build_questions()`. The dashboard is therefore showing the code's default, not
  a value read from the ledger, for all 29 rows.
- Consequence: a status edit for Q1–29 is only picked up if written as a
  **single word** (e.g. `DONE`); the multi-word `NOT DONE` is unparseable.
- `ledger vs data.json` statuses currently agree 125/125 — by construction.

So: **"status field never (actually) read — fallback default wins"** is the
mechanism; **"missing explanation prose"** is the substantive reason recorded in
the ledger for the same 29.

## 3. The 29 questions

"Ledger seg / dashboard seg" shows the segment-letter mismatch (see §4).
"Counts already exist in" lists the evidence files the ledger itself cites —
the numbers are computed; only the written explanation/decision is missing.

| # | Question (dashboard title) | Seg (ledger / dash) | Why NOT DONE — ledger's stated missing sub-part | Counts already exist in |
|---|---|---|---|---|
| 1 | Rows per extract vs rows loaded | A / A | Row-by-row difference explanation prose not written | `src/data_loader.py`, `data/profile.csv`, `data/raw_manifest.json` |
| 2 | Odd column names kept verbatim | A / A | Mismatch-note prose not written | `src/data_loader.py` |
| 3 | Numeric-looking text columns | A / A | Disagreeing-columns list prose not written | `src/data_loader.py` |
| 4 | Short/long order rows | A / A | Quoting-caused-vs-not explanation prose not written | `data/raw_manifest.json` |
| 5 | Leading zeros and spaces in ids | A / A | One-example-each demonstration prose not written | `src/data_loader.py`, `src/normalise.py` |
| 6 | Dates changed on load | A / A | Changed-date count + ambiguity decision prose not written | `src/normalise.py` |
| 7 | File encodings | A / A | Currency/accent misread test report prose not written | `src/data_loader.py` |
| 8 | Quotes inside notes | A / A | Affected-row misalignment report prose not written | `src/data_loader.py` |
| 9 | Loading the same file twice | A / A | Demonstration + reload-policy decision prose not written | `src/data_loader.py` |
| 10 | Empty vs placeholder cells per customer column | B / A | Placeholder-definition statement prose not written | `src/quality_checks.py`, `data/issue_registry.csv` |
| 11 | Placeholders in orders and their clustering | B / A | Most-column + month-clustering + process-fault explanation prose not written | `src/quality_checks.py`, `data/quality_datamart.csv` |
| 12 | Most-empty orders column | B / A | Share + status-dependence finding prose not written | `data/quality_datamart.csv`, `data/profile.csv` |
| 13 | Empty prices by month/product | B / A | Month/product comparison + unusual-share note prose not written | `data/quality_datamart.csv` |
| 14 | Missing and placeholder emails | B / A | Two-group counts + placeholder-rule explanation prose not written | `src/quality_checks.py` (`QC_CUST_EMAIL_INVALID` 57) |
| 15 | Missing and text prices | B / A | Text-price forms list prose not written | `src/quality_checks.py` (`QC_PROD_PRICE_INVALID` 2) |
| 16 | Never-empty vs >10% empty columns | B / A | Meaning-for-analysis statement prose not written | `data/quality_datamart.csv`, `data/profile.csv` |
| 17 | Empty delivery days by status | B / A | Share comparison + matter-decision + meaning explanation prose not written | `data/quality_datamart.csv` |
| 18 | Co-empty column pairs | B / A | Top pairs + single-cause judgement prose not written | `data/quality_datamart.csv` |
| 19 | Unusable stock per category | B / A | Per-category shares + stock-report implication prose not written | `src/quality_checks.py` (`QC_PROD_STOCK_INVALID` 14), `data/quality_datamart.csv` |
| 20 | Repeated order_ids | C / B | Reviewer explanation prose for non-exact copies not written | `src/deduplication.py`, `data/duplicate_registry.csv` |
| 21 | Which columns differ across copies | C / B | Pattern + corrections-vs-errors judgement prose not written | `src/deduplication.py`, `data/duplicate_registry.csv` |
| 22 | Repeated customers: same person? | C / B | Written rule + kept-count prose not written | `src/deduplication.py` |
| 23 | Case/spacing/dash customer variants | C / B | No-double-count proof + rule statement prose not written | `src/deduplication.py`, `src/normalise.py` |
| 24 | Customers with and without orders | C / B | Gap explanation prose not written | `src/deduplication.py`, `data/customer_master.csv` |
| 25 | Shared email addresses | C / B | Pairs-needing-decision + dependency prose not written | `src/deduplication.py` |
| 26 | Shared product names | C / B | Duplicate-vs-distinct decision + evidence prose not written | `src/deduplication.py` |
| 27 | Repeated product_ids | C / B | Per-repeat action + product-count effect prose not written | `src/deduplication.py`, `data/duplicate_registry.csv` |
| 28 | Customers with several cities | C / B | Trusted-city decision + city-count effect prose not written | `src/deduplication.py`, `data/customer_master.csv` |
| 29 | Delivered left after dedup | C / B | Small-amount judgement + conclusion-change statement prose not written | `data/duplicate_registry.csv`, `reports/deduplication_report.md` |

All 29 share the same *category* of cause: **computation done (counts in files),
written explanation/decision omitted** → not eligible for DONE under the ledger's
own rule — plus the parser/fallback quirk of §2 for how the dashboard obtains the
label.

## 4. Cross-checks

### 4a. `sql/`
- `sql/questions/` contains **96 files, all for Q30–125**
  (seg4: 10, seg5: 10, seg6: 18, seg7: 8, seg8: 2, seg9: 48). **Zero files for
  Q1–29** — matches the DONE set 1:1.
- This is expected: the capstone brief says *"Segments 1 to 5 need only the files,
  and Segments 6 to 9 need the files loaded into a PostgreSQL database."* Q1–29 are
  segments 1–3 (file-only). What Q1–29 lack is not SQL but the written answer.
- Saved SQL results: `data/SQL_OUTPUTS/` and `data/output/` contain **q50–q125
  only** (76 files each). Q30–49 have SQL sources but no committed ASCII results,
  so the dashboard's "View saved result" button correctly appears only for q50+
  (the endpoint 404s otherwise — a data-availability property, not a linking bug).

### 4b. Capstone 2 (`QuickMart_Mock_Project.html`)
- The brief's structure matches the ledger's segment letters 1:1:
  Segment 1 Loading and shape (Q1–9) · 2 Completeness (Q10–19) · 3 Identity and
  duplicates (Q20–29) · 4 Across the three extracts (Q30–39) · 5 Values and
  meaning (Q40–49) · 6 Advanced SQL (Q50–67) · 7 Professional SQL engineering
  (Q68–75) · 8 Expert SQL engineering (Q76–77) · 9 Expert SQL on the QuickMart
  data (Q78–125).
- The brief contains **no done/not-done statuses** — those are the pipeline's
  internal working ledger, not a capstone requirement. Nothing in the brief
  demands SQL for segments 1–3.
- **Discrepancy found (labelling, not status):** `src/dashboard_data.py:36–43`
  (`SEGMENT_OF`) assigns A=Q1–19, B=Q20–29, D=Q30–39 … with **no C**, while the
  ledger (and the brief's segment numbering) has A=Q1–9, B=Q10–19, C=Q20–29,
  D=Q30–39 … Effect: in `data.json` (and the UI) Q10–19 are labelled "A",
  Q20–29 are labelled "B", and the UI's "C · Identity" filter is always empty
  while "B" shows the identity questions.

### 4c. `docs/` and `src/questions/`
- Answer prose exists only for segments 4–9
  (`answers_segment4_5.md`, `answers_segment6_7.md`, `answers_segment8_9.md`).
  **No `docs/answers_segment1_3.md`** → the ledger's stated reason for Q1–29 is
  accurate and current.
- `src/questions/` contains only `seg4…seg9` modules; there are **no question
  functions for Q1–29**. Their "answers" are the pipeline-level counts
  (`data_loader` / `quality_checks` / `deduplication` outputs), which is why
  `build_questions()` emits the stub instead of a computed result.

## 5. Impact and risks

- **Today's UI is coincidentally correct**: Q1–29 are NOT DONE in both the ledger
  and the payload — but via two independent mechanisms (skipped line → fallback).
- **Latent bug 1 (parser):** multi-word statuses in the ledger can never be read.
  If someone writes anything other than a single token (e.g. "NOT DONE",
  "IN PROGRESS") for *any* question, the dashboard silently falls back to
  "NOT DONE".
- **Latent bug 2 (stub inconsistency):** if a Q1–29 ledger row were changed to
  single-word `DONE`, the payload would still emit zero code/SQL, no result and
  "explanation prose pending" — a DONE badge with a pending body.
- **Latent bug 3 (labels):** the Q10–29 segment letters in `data.json` don't match
  the ledger/brief (missing C; B shows identity questions); the UI's C filter is
  empty and B/C labels are misleading.
- **Not a bug:** no SQL/outputs for Q1–29. Segments 1–3 are deliberately
  file-only in the capstone brief.

## 6. Recommendations (for when code changes are allowed)

1. **Pick one source of truth for status.** Either keep the ledger and fix the
   parser to accept multi-word statuses (e.g. capture anything up to the next
   ` | ` and normalise), or compute DONE from an explicit evidence manifest.
2. **Surface the ledger reason** into `data.json` (e.g. `pending_reason`) so the
   Questions explorer explains *why* instead of the generic
   "Counts in code; explanation prose pending."
3. **To legitimately move Q1–29 to DONE:** write `docs/answers_segment1_3.md`
   (the missing prose), flip the ledger rows to a single-word `DONE`, and extend
   `build_questions()` to emit a real result payload (or explicitly accept a
   badge-only DONE and make the stub stop saying "pending").
4. **Align segment letters** with the brief (A=1–9 … C=20–29 … I=78–125) — or
   change the UI filter labels to match the payload. One of the two must move.
5. Optional: have the dashboard derive "has saved result" from `data/SQL_OUTPUTS`
   (already done) but annotate Q30–49 SQL files as "SQL source available, no saved
   result" so the gap is explicit.

## 7. How this was verified

- `_diag_probe.py` — parses the ledger with a corrected regex and prints all 29
  rows with reasons + payload fields; confirms 96 DONE / 29 NOT DONE and
  ledger↔data.json agreement (125/125).
- `_diag_probe2.py` — imports and runs the pipeline's own
  `src.dashboard_data.ledger_rows()`: **96 ids, 30–125 only; Q1–29 absent;
  regex reproduces NO MATCH on Q1/Q29 lines and MATCH on Q30.**
- Inventory commands: `sql/questions` per-segment counts, `data/SQL_OUTPUTS` ÷
  `data/output` file lists, `docs/` listing, `src/questions/` listing, and a
  search for the question texts (found only in `src/dashboard_data.py`).
- Capstone 2 HTML grepped for segment names and the "125 questions … nine
  segments" statement (no per-question statuses in the brief).

---

## 8. Phase 1 resolution (applied and verified, 2026-10-17)

Owner-approved Phase 1 fixes (parser, segment letters, reason surfacing) were
implemented. No numbers changed: still 96 DONE / 29 NOT DONE.

### What changed

| # | File | Change |
|---|---|---|
| 1 | `src/dashboard_data.py::ledger_rows()` | Status regex now captures multi-word cells: `\| Q(\d+) \| (\S+) \| (.+?) \|`. All 125 ledger rows parse (was 96). The "missing sub-part" column is read and cleaned (leading `reason: ` stripped; em-dash means "no reason"). |
| 2 | `src/dashboard_data.py::SEGMENT_OF` | Letters aligned with the brief/ledger: A=1-9, B=10-19, C=20-29, D=30-39, E=40-49, F=50-67, G=68-75, H=76-77, I=78-125. Segment C now exists (Q20-29). |
| 3 | `src/dashboard_data.py::build_questions()` | Every question now carries `pending_reason` (empty for DONE). Q1-29 expose their ledger reason. |
| 4 | `dashboard/main.py::_trim_question()` | Passes `pending_reason` through (scrubbed) on `/api/questions`. |
| 5 | `dashboard/static/app.js` | NOT DONE rows render `Missing sub-part: <ledger reason>`; the reason is also searchable. |
| 6 | `dashboard/static/styles.css` | `.q-reason` line in the pending-badge amber. |
| 7 | `dashboard/data.json` | Regenerated via `python -m src.dashboard_data` (never hand-edited). |

### Verification (all green)

- Ledger parse: 125/125 ids; Q1 status "NOT DONE" with its reason read from the
  file (was: 96 ids, Q1-29 absent -> fallback).
- `data.json`: 29 NOT DONE / 96 DONE; segments A:9 B:10 C:10 D:10 E:10 F:18
  G:8 H:2 I:48; every NOT DONE row has a reason; no DONE row carries one.
- `dashboard/tests/smoke_api.py`: 28/28 endpoints OK, KPI asserts pass.
- `dashboard/tests/live_check.py` (live server): 0 failures - assets, 28
  endpoints no-NaN, privacy spot-check clean, KPI cross-checks OK.
- Headless DOM test (`dom_test.js`): 30/30 checks, 0 runtime errors.
- Determinism: re-running `python -m src.dashboard_data` produced a
  byte-identical file (sha256 fd9494b7...).

### Notes found during verification (not fixed, not part of Phase 1)

- Raw `data.json` contains 6 pre-existing NaN tokens (Q78 x2, Q79 x1, Q107 x3) -
  present in HEAD too; the API layer sanitises them to `null`, so they never
  reach the browser. Optional tidy-up: null them in `build()`.
- Regeneration picked up pre-existing drift vs the old payload: the working
  `data/` extracts differ from when the old payload was built (provenance
  extract hashes changed; Q48 `outside_values.sample` now starts "BLR").
  No other question result changed; deterministic on re-run.

### Remaining (Phase 3)

- Phase 3: optional NaN tidy-up (6 pre-existing tokens in raw `data.json`);
  saved CSVs for Q30-49; remove `_diag_probe*.py`, `_parse_probe.py`, the
  `_evidence_probe*.py` scripts and their report files.
- Reusable checks left at project root: `_verify_phase1.py`, `_verify_phase2b.py`,
  `_flip_ledger.py`, `_api_phase1_check.py` (delete together with the probes when
  done).

---

## 9. Phase 2 resolution (applied and verified, 2026-10-17)

Owner reviewed `docs/answers_segment1_3.md` and approved; Q1-29 moved to DONE.

### What changed

| # | File | Change |
|---|---|---|
| 1 | `docs/question_ledger.md` | Q1-29 rows flipped NOT DONE -> DONE (one-off `_flip_ledger.py`): answer-file column now cites `docs/answers_segment1_3.md` plus code/evidence refs; key counts in the detail column; reason cells cleared; footer "DONE 125 / NOT DONE 0"; allocation note aligned to A-I. |
| 2 | `src/dashboard_data.py::seg1_3_answers()` | New parser for `docs/answers_segment1_3.md`: per-question method/decision/result text (whitespace collapsed) + first code ref; emails masked at build time (the payload guard rejects them). |
| 3 | `src/dashboard_data.py::build_questions()` | Q1-29 payload: `headline` = decision, `method` = method, `result` = `{kind: text, value: result}`; the build fails loudly if any of the 29 sections is missing. |
| 4 | `dashboard/main.py` | `scrub_question_text()`: email/phone masking + deterministic C-id masking. `_trim_question()` serves `result_text` (emails + C-ids masked; phone masking skipped so month/count tokens like "2024-11 12" survive). Server-side search covers `result_text`. |
| 5 | `dashboard/static/app.js` | Questions explorer renders a `Result` details block (next to Method); result text searchable. |
| 6 | `dashboard/tests/smoke_api.py` | New asserts: 125 questions all DONE, no `pending_reason`, Q1-29 `result_kind=text`, no email/raw-C-id leaks, NOT DONE filter empty, result-text search hits Q29. |
| 7 | `docs/answers_segment1_3.md` | Q6 decision reworded (`01/11/2026` read day-first as 1 Nov 2026) so no ISO date token trips the API phone mask. |
| 8 | `dashboard/data.json` | Regenerated via `python -m src.dashboard_data` (never hand-edited). |
| 9 | `dashboard/NOTES.md` | 125 DONE wording; Q1-29 answer flow described. |

### Verification (all green)

- `_verify_phase2b.py`: 21/21 - ledger 125/125 DONE with no reasons; answers
  parse 29/29 with all fields; payload 125 DONE, no stubs, headlines == parsed
  decisions, guard scan clean; API scrub removes raw C-ids/emails and keeps
  count tokens.
- `python -m src.dashboard_data`: byte-identical on re-run (sha256 d0367ad6...).
- Smoke API: 28/28 endpoints OK; new question asserts pass.
- Live check (live server): 0 failures - incl. privacy spot-check on
  `/api/questions?limit=200` (now carrying the 29 result texts) and KPI
  cross-checks.
- Headless DOM test: 31/31 checks (new: Result details rendered for the first
  25 questions), 0 runtime errors.
