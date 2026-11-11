# Trusted order framework (Sprint 3)

## Purpose

Decide which order lines the business can put its name to, through 12
named rules with counted outcomes, and reconcile every input row to
exactly one of trusted or rejected. Populations: strict (no FAIL and
no WARNING), lenient (no FAIL), trusted = lenient (recommended, see
below), rejected (quarantine with lineage + masked notes).

## Rule list

| rule_id | name | severity | treatment | failing (of 6000 clean lines) |
|---|---|---|---|---|
| R01 | Customer Exists | FAIL | set_aside | 198 (5530 exact, 272 rescued by normalisation) |
| R02 | Product Exists | FAIL | set_aside | 159 (5551 exact, 290 rescued) |
| R03 | Customer Signup Before Order | FAIL | set_aside | 1851 (1312 before-signup, 539 unparseable dates, 198 skipped) |
| R04 | Valid Order Date | FAIL | set_aside | 833 (457 future, 286 unparseable, 90 pre-2022-01-08) |
| R05 | Valid Quantity | FAIL | set_aside | 718 (zero 247, empty 168, negative 109, fence 76, decimal 61, word 57) |
| R06 | Valid Price | FAIL | set_aside | 4636 + 814 WARNING (550 within 10%, 262 non-positive) |
| R07 | Valid Discount | WARNING | flag | 561 (zero 2231, percent 2142, fraction 522 pass) |
| R08 | Valid Status | FAIL | set_aside | 623 (all missing; zero unmapped) |
| R09 | Valid Payment | WARNING | flag | 1198 (640 unmapped, 558 missing) |
| R10 | Valid Delivery Days | WARNING | flag | 75 FAIL + 1548 WARNING (cancelled-with-days) |
| R11 | Inventory Feasibility | WARNING | flag | 185 (3015 skipped: unusable stock) |
| R12 | Cross-field Business Rule | FAIL | set_aside | 175 FAIL + 1529 WARNING (R12c-only) |

Full catalog (predicates, fields, files, rationales, threshold
alternatives): `docs/rule_catalog.md`, generated from the registry.

## Waterfall

`docs/waterfall.md` (generated): raw 6103 -> loaded 6103 -> deduped 6000
(103 removed) -> R01..R12 sequential attribution -> trusted (lenient) 522
-> strict 115. Sequential attribution runs R01 first ... R12 last; each
rule removes still-remaining FAIL rows. Independent counts run each
rule on the full input; the gap is multi-fail rows to the first
catcher. WARNING never removes. R06 is the dominant driver (2371 of
5478 sequential removals); R12 removes 0 sequentially (its 175 FAIL
rows were all caught earlier).

## Clustering findings

Co-occurrence (FAIL+WARNING sets, lift vs independence): R10xR12 lift
3.35 (joint 1575 — expected, R12c mirrors R10-cancelled logic);
R05xR11 lift 1.73 (quantity/stock link is real); R03xR04 lift 1.50
(date problems travel together). All other pairs lift 0.0–1.4.

Concentration (fail share vs row share per dimension, flag at ratio >=
1.5 with >= 30 rows): NOTHING flagged in any dimension — city, month,
category and payment all sit at ratio 0.95–1.02. Failures are systemic
noise, not a localized process fault.

## Root causes

- EVIDENCED: planted anomaly spikes — quantity 500 (76 rows) and
  delivery_days 45 (18 Delivered rows) are exact repeated values spread
  evenly across dimensions, i.e. generator faults, not business.
- EVIDENCED: catalogue/paid systematic divergence — 77% of lines fall
  outside 10% tolerance, so R06 dominates set-aside; catalogue prices
  cannot be treated as ground truth without review.
- EVIDENCED: date-generator faults — order dates to 2027-12, orders
  from 2019 (before first signup 2022-01-08), signups dated after TODAY.
- EVIDENCED: placeholder emails shared across customers (D03 merges)
  and case-variant ids (272 + 290 rows rescued by normalisation).
- HYPOTHESIS: the 500-quantity and 45-day spikes come from one faulty
  generator pass (same uniform spread, same exact-value signature);
  untested — check row overlap to confirm.
- HYPOTHESIS: catalogue staleness (not fraud) explains most R06
  failures; untested — needs price-history the extracts lack.

## Strict vs lenient vs trusted

| population | orders | line value | delivered orders | delivered value |
|---|---|---|---|---|
| strict | 115 (-78%) | Rs 79,738.50 (-82%) | 51 | Rs 27,552.00 (-80%) |
| lenient | 522 | Rs 455,160.75 | 168 | Rs 134,720.50 |
| trusted | 522 | Rs 455,160.75 | 168 | Rs 134,720.50 |

Top-5 customers (by delivered value, ties shown — none at either
cutoff): trusted = C0284, C0431, C0002, C0434, C0142; strict = C0173,
C0221, c0312, C0131, C0284. Membership changes almost completely (only
C0284 survives, ranked 1st vs 5th). Average delivery days
(city x category): trusted 3.72 vs strict 3.49 (-6%).

## Recommendation

Ship **lenient as trusted**. Strict discards a further 407 WARNING-only
rows (-80% of delivered value) and replaces the entire top-5, while the
flagged rows' core facts (customer, product, date, value) still
validate — exactly what WARNING means. Revisit only if payment-unknown
or unverifiable-price rows are later shown to distort a specific Q4
answer; the WARNING flags make that cut possible per question.
