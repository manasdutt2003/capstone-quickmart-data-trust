# Line value — single definition

**Formula.** `line_value = quantity * unit_price_paid * (1 - discount_frac)`,
rounded to 2 dp. Python: `src/line_value.py::line_value` (the only Python
definition; `validation_rules.line_value_of` delegates to it). SQL:
`sql/v_line_value.sql` mirrors the formula over cleaned columns and never
redefines it.

**Discount interpretation.** Raw discount text is interpreted once, in
`normalise.parse_discount_frac`: surrounding whitespace, a trailing `%`
or the word "percent" are stripped; a number `<= 1` is already a fraction
(`0.1` -> `0.10`); a number `> 1` is a whole percent (`15` -> `0.15`).
Whether that rule is right for every row is finalised in R07 (WARNING):
unparseable or out-of-range discounts are flagged there, never silently
reinterpreted here.

**Null handling.** Canonical: null quantity, price or discount each give
NULL line value, never 0. Frozen legacy zero-fill is preserved at the
old call sites (commission row values, mart values, pipeline commission
frame, `deduplication.commission_frame` fillna) and in
`line_value_of`'s None-discount-means-0.0 mapping — numbers depending on
them (e.g. commission leakage) are unchanged.

**Where Python returns 0.0 (exhaustive, line-value context only).**
`src/commission.py::calculate_line_value` returns 0.0 when quantity is
missing/non-positive or price is missing/negative, and maps out-of-range
discount to 0.0 (`:32-36`); `src/datamarts.py::_line_value` returns 0.0
when quantity or price is missing (`:58`, used only when a mart frame
has no `line_value` column yet); `src/pipeline.py::lv` appends 0.0 when
quantity or price is missing (`:140`); `src/deduplication.py`
`commission_frame` applies `.fillna(0.0)` (`:366`); `row_line_value`
maps blank, unparseable or >= 1 discount to 0.0 (`line_value.py:46-52`)
while missing quantity/price stay None. Everywhere else (including
`line_value()` itself) missing input gives None.

**Where SQL returns NULL.** `sql/v_line_value.sql` returns NULL (empty
CASE result, never 0) whenever quantity, unit_price_paid or discount is
NULL, empty, or fails its regex guard.

**Which semantic the Q4 numbers use.** The Q4 path
(`pipeline.evaluate` → `row_line_value` → `datamarts.build_marts`,
which reuses the existing `line_value` column) preserves per-row NULLs
— `data/trusted_orders.csv`, `data/sales_datamart.csv` and
`outputs/trusted_orders.csv` currently hold zero blank line values
(2385, 450 and 522 rows checked) — and pandas/SQL `SUM` skips NULLs, so
an invalid line would contribute 0 to every total exactly as zero-fill
would. Totals are identical under either semantic; the stored rows keep
NULL, never 0.0.

**Rounding.** Python `round()` (banker's rounding) to 2 dp; SQL `ROUND(x,
2)`. The two disagree on exact `.5` ties — parity noted for criterion
#16; nearest-cent agreement is asserted, not bit identity.
