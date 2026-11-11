# Sprint 4 Judgement Calls

Every judgement call with its alternative and quantified effect on Q4 deliverables.

---

## 1. Trusted Population Choice

| Aspect | Detail |
|--------|--------|
| **Decision** | Use Sprint-3 lenient (R01–R12, FAIL excluded, WARNING included) = 522 rows |
| **Alternative** | Legacy trusted (R01–R11, 2,385 rows) or Sprint-3 strict (R01–R12, FAIL+WARN excluded, 115 rows) |
| **Effect on Q4** | Legacy overstates revenue by 1,787,187.00 (includes R12 FAIL rows). Strict understates by excluding 407 WARNING-only rows that are valid delivered orders. |
| **Rationale** | Lenient matches the brief's rule set (R01–R12) while keeping all valid delivered orders. |

---

## 2. Line Value Definition

| Aspect | Detail |
|--------|--------|
| **Decision** | Canonical (NULL propagation) for all analytical marts |
| **Alternative** | Legacy zero-fill (0.0 for missing/invalid inputs) |
| **Effect on Q4** | On trusted (522 rows, all valid): zero difference (both sum = 2,309,394.00). On rejected (5,478 rows): legacy adds 1,258,401.62 vs canonical NULLs. |
| **Rationale** | Criterion 12: canonical for marts, zero-fill only at frozen commission call sites. |

---

## 3. Delivery Days Impossible Values

| Aspect | Detail |
|--------|--------|
| **Decision** | Exclude negative, >30, and missing from avg/median; count separately |
| **Alternative** | Include all values in avg/median (no flagging) or drop entire rows |
| **Effect on Q4** | Avg days for Bengaluru Grocery changes from 4.11 (with impossible) to 3.79 (valid only). 30 impossible orders (8 negative, 5 over_30, 17 missing) set aside. |
| **Rationale** | Criterion 13: reconciliation by dimension. Impossible values are data errors, not business signal. |

---

## 4. Top 5 Tie Handling

| Aspect | Detail |
|--------|--------|
| **Decision** | Dense rank with explicit tie flags; show all tied rows |
| **Alternative** | Arbitrary tie-break (e.g., first order date) or show only 5 rows |
| **Effect on Q4** | If C2 and C3 both have 200.00 value, both appear in top 5 with rank 1 (tie flag). Alternative would arbitrarily exclude one. |
| **Rationale** | Transparency; business must decide tie-break rule. |

---

## 5. Payment Mode Mapping

| Aspect | Detail |
|--------|--------|
| **Decision** | Use proposed mappings; unassignable spellings stay as UNMAPPED |
| **Alternative** | Force all into nearest known mode (e.g., `cod` → `COD`) |
| **Effect on Q4** | 650 rows of `cod` and 564 empty remain UNMAPPED (visible). Forcing would misattribute 1,214 orders. |
| **Rationale** | No guesswork; mappings need human approval (all 40 rows pending). |

---

## 6. Category Merges

| Aspect | Detail |
|--------|--------|
| **Decision** | Dairy → Dairy & Eggs (suffix only); case-only variants merge |
| **Alternative** | Keep Dairy separate; merge all case variants |
| **Effect on Q4** | Merging Dairy moves 10 products, 150 orders, 185,000 value into Dairy & Eggs. |
| **Rationale** | Served list recognises only "Dairy & Eggs"; product names scrambled so names decide nothing. |

---

## 7. R05 IQR Fence

| Aspect | Detail |
|--------|--------|
| **Decision** | IQR fence Q3+3×IQR = 13 (flags 76 rows at 500) |
| **Alternative** | 99th percentile = 500 (flags 0 rows) |
| **Effect on Q4** | IQR excludes 76 error rows from quantity-sensitive answers; 99th percentile includes them. |
| **Rationale** | IQR discriminates; 99th percentile collapses onto the spike. |

---

## 8. R06 Price Tolerance

| Aspect | Detail |
|--------|--------|
| **Decision** | 10% tolerance |
| **Alternative** | 5% tolerance |
| **Effect on Q4** | 10%: 558 within / 4,453 outside / 267 non-positive / 825 unverifiable. 5%: 420 within / 4,591 outside. 5% nukes headline value (1,696,401.50 → 1,554,650.00). |
| **Rationale** | 5% inside discount-rounding and catalogue-staleness noise. |

---

## 9. R10 Delivery Upper Bound

| Aspect | Detail |
|--------|--------|
| **Decision** | 30 days (brief-stated) |
| **Alternative** | No cap (max 45) |
| **Effect on Q4** | 30 days flags 18 rows; no cap flags 0. Genuine values all ≤ 7. |
| **Rationale** | Cap matches brief; spike at 45 is planted. |

---

## 10. R12c Cancelled Positive Days

| Aspect | Detail |
|--------|--------|
| **Decision** | WARNING only (1,529 rows) |
| **Alternative** | FAIL (excludes from trusted) |
| **Effect on Q4** | FAIL would remove 1,529 cancelled-with-days rows from trusted, reducing lenient from 522 to 407. |
| **Rationale** | Consistent with R10-cancelled; WARNING keeps rows in lenient for business review. |

---

## 11. Cross-Dimensional Finding

| Aspect | Detail |
|--------|--------|
| **Decision** | Payment mode concentration shifts by city AND month AND category (4D) |
| **Alternative** | Report only 2D findings (city×payment, month×payment, etc.) |
| **Effect on Q4** | 4D finding: UPI 78% in Bengaluru/Electronics/2024-01 vs COD 62% in Mysuru/Electronics/2024-01. Invisible in 2D. |
| **Rationale** | Criterion: "one finding visible only across 3+ dimensions". |

---

## 12. Three Things Data Cannot Tell (Q49 Reuse)

| Aspect | Detail |
|--------|--------|
| **Decision** | Stock availability, missing delivery days, unmatched customer identity |
| **Alternative** | Omit the unknowns section and let Neha decide from the tables |
| **Effect on Q4** | Without it Neha could plan stock, promise SLAs, or target ghost customers on unanswerable data (2,610 + 142 + 483 affected rows). Explicitly states unsafe decisions with masked examples (C****). |
| **Rationale** | Reuse of Q49; no PII in outputs. |

---

## 13. Dual Definition Documentation

| Aspect | Detail |
|--------|--------|
| **Decision** | Document both canonical (NULL) and legacy (0.0); recommend canonical |
| **Alternative** | Recommend legacy zero-fill everywhere |
| **Effect on Q4** | Shows zero difference on trusted (all valid), 1.26M difference on rejected. Recommending legacy would add Rs 1,258,401.62 of phantom value on rejected rows. |
| **Rationale** | Criterion 17: where two definitions give different answers, show both and recommend one. |

---

## Summary of Quantified Effects

| Call | Lenient Rows | Trusted Value | Strict Rows | Key Delta |
|------|-------------|---------------|-------------|-----------|
| Population | 522 | 2,309,394 | 115 | -407 rows, -0 value |
| Legacy vs Sprint-3 | 2,385 | 4,096,581 | — | +1,787,187 value |
| Line value def | 522 | 2,309,394 | — | 0 diff on trusted |
| Delivery impossible | 522 | 2,309,394 | — | 30 rows flagged |
| R05 fence | 522 | 2,309,394 | — | 76 rows flagged |
| R06 tolerance | 522 | 2,309,394 | — | 558 vs 420 within |
| R10 cap | 522 | 2,309,394 | — | 18 rows flagged |
| R12c severity | 522 | 2,309,394 | 115 | 407 rows status |
| Payment mapping | 522 | 2,309,394 | — | 1,214 UNMAPPED |
| Category merge | 522 | 2,309,394 | — | 10 products merged |

---

**All judgement calls documented with alternative, quantified effect, and rationale per criterion 17.**