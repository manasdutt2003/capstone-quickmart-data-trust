# Presentation script — 10 minutes with the dashboard

Open `dashboard/index.html` (present mode, arrows to move). Times are ceilings.

## 0:00–1:00 Trust statement (section 1)
"522 of 6,103 order rows are trusted; here is where the data breaks."
Walk the waterfall bars: raw 6,103 → deduped 6,000 → rejected 5,478 →
lenient 522 → strict 115. Point: every row is counted somewhere; nothing
vanishes silently.

## 1:00–3:00 Five problems (section 2)
One sentence each: Q1 maps breakage by city/month/payment; Q2 names four
duplicate levels with a 103-row removal; Q3 keeps 522 lenient rows under
12 rules; Q4 reports delivered-only revenue of Rs 2,309,394.00 that
reconciles three ways; Q5 turns marts into a verified written report.

## 3:00–4:30 Where it breaks (section 3)
R06 (price) fails 4,636 rows; R03 (signup dates) 1,851. Heatmap: failures
cluster, they do not scatter. Co-occurrence lift over 1 names pairs that
travel together (same broken feed).

## 4:30–5:30 Strict vs lenient (section 4)
407 WARNING-only rows separate the two; top-5 overlap is shown live.
Recommendation: lenient. Strict drops valid delivered rows.

## 5:30–7:00 Leadership answers (section 5)
Monthly bars come from the same table underneath (toggle view data).
Top customers masked. Payment mix and delivery bands by city.

## 7:00–8:00 Verification (section 7)
20 of 23 criteria PASS live from code; #11 FAIL (40 mapping rows await
your sign-off — that is my ask today); #4 PARTIAL (GitHub-side);
#22 PARTIAL (refresh helper not yet written). Rubric self-score 75.0.

## 8:00–9:00 LLM insights (section 8)
Input is aggregated JSON only (PII asserted out). 8/8 rule-based insights
VERIFIED; the rejected drawer is empty because nothing failed it — the
test suite plants an invented figure to prove the catch works.

## 9:00–10:00 Least sure + next (section 9)
Least-sure number: the 407 WARNING-only rows behind the lenient/strict
delta. Defence: every one is traced in rule_failure_log; re-running the
split on any new extract reproduces it exactly.

## Likely reviewer questions
1. "Why should I believe 522 and not 2,385?" — 2,385 includes R12
   failures; the waterfall shows exactly which rules remove what.
2. "Do the city totals add to the grand total?" — Yes three ways
   (criterion 13, live check, Rs 2,309,394.00).
3. "Did the model invent anything?" — Every figure carries its mart
   source; click any number. The verifier test plants Rs 9,999,999.99
   and it lands in the rejected drawer.
