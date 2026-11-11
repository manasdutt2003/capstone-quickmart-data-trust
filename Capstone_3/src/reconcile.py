"""Reconciliation gates: raise on any mismatch, never warn-and-continue.

Checks, on source_row_number sets and group closures:
- orders_in == trusted + set_aside, total and grouped by city, month and
  category (city/category via normalised master match; unmatched rows form
  an explicit UNMATCHED bucket through LEFT joins, never dropped by an
  inner join);
- sequential rule-removal counts reconcile to the clean_orders row count;
- every row is in exactly one of trusted or rejected;
- strict is a subset of lenient, lenient a subset of clean_orders.
Returns {"waterfall": DataFrame, "join_log": DataFrame}.
"""

import pandas as pd

from .dimensions import enrich_dimensions
from .trusted import build_waterfall
from .validation_rules import REGISTRY


def _logged_dims(frame, customers, products, ctx, join_log):
    """Enrich dimensions, logging both master joins (never drop rows)."""
    before_city = len(frame)
    dims = enrich_dimensions(frame, customers, products, ctx)
    join_log.append({"join": "orders-customers-city", "left_rows": before_city,
                     "right_rows": len(customers), "out_rows": len(dims),
                     "dropped": before_city - len(dims)})
    join_log.append({"join": "orders-products-category",
                     "left_rows": before_city, "right_rows": len(products),
                     "out_rows": len(dims), "dropped": before_city - len(dims)})
    if len(dims) != before_city:
        raise AssertionError("dimension enrichment dropped rows")
    return dims


def reconcile(clean_orders, populations, eval_long, customers, products, ctx,
              raw_rows, loaded_rows):
    """Run every gate; raise AssertionError on the first mismatch."""
    join_log = []
    trusted, rejected = populations["trusted"], populations["rejected"]
    strict, lenient = populations["strict"], populations["lenient"]

    def _srn(frame):
        return {str(v) for v in frame["source_row_number"].values}

    s_clean, s_trusted = _srn(clean_orders), _srn(trusted)
    s_rejected, s_strict, s_lenient = _srn(rejected), _srn(strict), _srn(lenient)

    if s_trusted | s_rejected != s_clean:
        raise AssertionError("trusted + rejected != clean_orders")
    if s_trusted & s_rejected:
        raise AssertionError("row in both trusted and rejected")
    if not s_strict <= s_lenient <= s_clean:
        raise AssertionError("strict/lenient/clean subset chain broken")

    waterfall = build_waterfall(raw_rows, loaded_rows, clean_orders, eval_long,
                                strict, lenient)
    rule_rows = waterfall[waterfall["stage"].isin(
        [r.rule_id for r in REGISTRY.values()])]
    if int(rule_rows["rows_removed"].sum()) != len(clean_orders) - len(trusted):
        raise AssertionError("rule removals do not reconcile to clean_orders")

    dims_clean = _logged_dims(clean_orders, customers, products, ctx,
                            join_log)
    dims_trusted = _logged_dims(trusted, customers, products, ctx, join_log)
    dims_rejected = _logged_dims(rejected, customers, products, ctx, join_log)
    for dim in ("city", "month", "category"):
        total = dims_clean[dim].value_counts()
        got = dims_trusted[dim].value_counts().add(
            dims_rejected[dim].value_counts(), fill_value=0).astype(int)
        for key in set(total.index) | set(got.index):
            if int(total.get(key, 0)) != int(got.get(key, 0)):
                raise AssertionError(
                    f"{dim} group {key!r} does not close: "
                    f"{int(total.get(key, 0))} != {int(got.get(key, 0))}")
        if int(total.sum()) != len(clean_orders):
            raise AssertionError(f"{dim} groups lose clean rows")

    join_df = pd.DataFrame(join_log, columns=["join", "left_rows",
                                              "right_rows", "out_rows",
                                              "dropped"])
    return {"waterfall": waterfall, "join_log": join_df}
