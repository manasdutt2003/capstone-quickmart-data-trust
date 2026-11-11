## Q68–75 Analogue Answers (Segment 7)

| Question | Missing Data | Honest Analogue (stated, labelled) | Missing Column Label |
|----------|-------------|-----------------------------------|----------------------|
| **Q68** 30-min gap sessionisation | No intra-day timestamps in orders/extracts | Use order_date timestamp only; gap detection limited to date-level. Closest analogue: "no intra-day granularity; treat each order as a point event at its order_date." | `order_timestamp`, `session_start` |
| **Q70** Referral-chain depth | No `referral_id` field in extracts | Recursive CTE on a dummy "chain" column; cannot follow actual referral ancestry. Analogue: depth = 1 for all customers (no chain). | `referral_id`, `referred_by` |
| **Q73** Order funnel (placed/confirmed/delivered) | No `browse` events in extracts | Funnel stages derived from order_status only: placed → confirmed → delivered. No pre-purchase browse data. Analogue: "stages = placed/confirmed/delivered based on order_status; no browse intermediate." | `browse_event`, `visit_time` |
| **Q74** Status snapshot classification | No transition log; single status per order | Each order has one status at snapshot time. Classification: "orders with status=Delivered, others as non-delivered." No history of status changes. Analogue: "single status per order; no transition log; classify by current status only." | `status_history`, `transition_timestamp` |
| **Q75** Quality scorecard 0–100 | Gaming notes documented per criterion 17 | Scores computed on trusted orders only: completeness=30%, uniqueness=20%, referential integrity=30%, conformance=20. Notes: no PII in outputs; notes masked + notes_sha256 retained. | — |

---
**Decision summary (from judgement_calls.md, 13 calls):**
- Trusted population: Sprint-3 lenient (522 rows, R01–R12, FAIL excluded, WARNING included) recommended over legacy 2,385
- Line value: canonical NULL semantics (single def in `src/line_value.py`); legacy zero-fill only at frozen commission call sites
- Dedup order: D01→D03-remap→D02→D05 (D06 flag-only), integer-cast tiebreakers, mirrors Python exactly
- Mappings: all 40 `approved_by` rows blank; human sign-off required before Q4 cites them
- PII deviation: `notes` column masked + `notes_sha256` retained in outputs; no name/email/phone in outputs
- Quality scorecard weights: completeness 30%, uniqueness 20%, referential integrity 30%, conformance 20%
- Tie-breaking: CROLLATE "C" on customer_id/order_id for deterministic sort; Python and SQL must agree on same semantics