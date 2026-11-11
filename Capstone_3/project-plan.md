# Project plan — QuickMart dashboard + Sprint 5 close-out

## Done (this change)
1. `src/dashboard_data.py` → `dashboard/data.json`: 125 questions (live
   function runs), 23 criteria (from live cache), 12 rules + lift,
   5 marts + reconciliation, 8 verified insights, provenance hashes.
   PII-scanned; refuses to write on any hit.
2. `src/criteria_check.py`: all 23 checks execute real commands/tests/
   recomputes; `--write-cache` → `dashboard/criteria_cache.json`
   (no timestamps, run hash only). Honest PARTIAL/FAIL where due.
3. `src/llm_insights.py`: aggregated-only input + PII assert, figure
   verifier (0.01 rule), 8/8 rule-based insights VERIFIED, two-run
   comparison, committed `reports/llm_insights.json` + run record.
   Model path refuses without go.
4. `src/dashboard.py` → `dashboard/index.html` (317,601 bytes, one file,
   no external URLs, dark/light, slides + scroll + print).
5. `tests/test_dashboard.py` (7) + `tests/test_llm_insights.py` (5).
6. `docs/presentation_script.md` (this plan's talk track), specs below.

## Waiting on you ("go")
- Install ollama + pull qwen2.5:0.5b (~394 MB), run the model pass,
  compare with the rule-based set, commit the new
  `reports/llm_insights.json`. Nothing in the dashboard depends on it.

## Waiting on the business
- Sign the 40 mapping rows (criterion 11 FAIL until then).

## Then
- Write `src/refresh.py` (criterion 22 PARTIAL), cut marts to lenient,
  merge sprint 5 (commands below in the report, run by you).
