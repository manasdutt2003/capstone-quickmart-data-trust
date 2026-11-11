# Specs — dashboard, payload, checks, insights

## dashboard/index.html
- Single file, UTF-8, LF newlines, no `http://`/`https://` outside HTML
  comments, no CDN, no fonts, no libraries. Budget: under 3 MB
  (actual ~310 KB).
- Python renders all content; JS enhances only (theme, slides via
  arrows/Home/End/Esc, search/filters, SVG charts from embedded JSON,
  view-data toggles, source popover on `[data-src]` click).
- Charts: hand-written inline SVG with `<title>`; every chart ships its
  table (`view data` toggle); chart JSON blocks equal the tables.
- Deterministic: `data.json` has no timestamps; render twice → same SHA.
- Print: `@media print` expands slides, hides nav/buttons.

## dashboard/data.json
- Built only by `python -m src.dashboard_data` from outputs, marts,
  ledger, judgement calls, reference manifests, committed insights and
  the criteria cache. Question headlines come from running the actual
  Q30–125 functions; ids masked (`X***`); PII-scanned pre-write.

## src/criteria_check.py
- 23 checks + 5 validations, each executing the real command/test/
  recompute via an injectable runner. Statuses PASS/PARTIAL/FAIL, no
  hard-coded passes. `run_hash` = sha256 of canonical results (no
  timestamps). Re-run: `python -m src.criteria_check --write-cache`.

## src/llm_insights.py
- `build_model_input`: the ONLY model-input function (aggregated mart
  rows, PII-asserted). Rounding rule: figures must match a mart value
  within 0.01. `verify_insight` marks the rest UNVERIFIED with reasons.
- Rule-based fallback: 8 insights, deterministic, labelled rule-based.
- `run_model` raises until the model go-ahead; model: qwen2.5:0.5b,
  temperature 0, seed 42, prompt `prompts/insights_prompt.txt`.

## tests
- `tests/test_dashboard.py`: 125/23/12/5 counts; insight figures in
  payload; chart JSON == tables; PII scan; no URLs; size; determinism;
  all 23 check functions observed executing.
- `tests/test_llm_insights.py`: PII-free input; invented Rs 9,999,999.99
  caught; 8/8 rule-based VERIFIED + deterministic; committed files
  verify; model refuses without go.
