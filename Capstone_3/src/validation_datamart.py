"""Validation datamart: per-rule failures by dimension (Sprint 3).

Grain: one row per (rule_id, dimension, dimension_value). failing_orders
counts order lines failing the rule (FAIL or WARNING); value_removed sums
the single line value (None counts as 0.0, matching the commission
fillna convention). Dimensions come from dimensions.enrich_dimensions,
so UNMATCHED/UNMAPPED/INVALID buckets are explicit and splits always
close to rule totals.
"""

import pandas as pd

from .dimensions import DIMENSIONS, enrich_dimensions
from .line_value import row_line_value
from .path_guard import assert_inside_write_root
from .validation_rules import REGISTRY, RuleResult


def build_validation_datamart(orders_df, eval_long, customers, products, ctx):
    """Build the long validation datamart (deterministic)."""
    dims = enrich_dimensions(orders_df, customers, products, ctx)
    values = [row_line_value(row) for _, row in orders_df.iterrows()]
    failing = eval_long[eval_long["result"] != RuleResult.PASS.value]
    rows = []
    for rule in REGISTRY.values():
        hit = failing[failing["rule_id"] == rule.rule_id]
        hit_srn = {str(s) for s in hit["source_row_number"].values}
        for dim in DIMENSIONS:
            grouped = dims.loc[dims["source_row_number"].astype(str).isin(
                hit_srn)].groupby(dim, sort=True)
            counts = grouped.size()
            for value, sub in grouped.groups.items():
                part = 0.0
                for idx in sub:
                    val = values[orders_df.index.get_loc(idx)]
                    part += val if val is not None else 0.0
                rows.append({"rule_id": rule.rule_id, "dimension": dim,
                             "dimension_value": str(value),
                             "failing_orders": int(counts.loc[value]),
                             "value_removed": round(part, 2)})
    out = pd.DataFrame(rows, columns=["rule_id", "dimension",
                                      "dimension_value", "failing_orders",
                                      "value_removed"])
    return out.sort_values(
        ["rule_id", "dimension", "dimension_value"]).reset_index(drop=True)


def write_validation_datamart(df, path):
    """Write the validation datamart through the path guard."""
    target = assert_inside_write_root(path)
    target.write_text(df.to_csv(index=False, encoding="utf-8",
                                lineterminator="\n"), encoding="utf-8",
                      newline="\n")
    return target


def cooccurrence(eval_long):
    """Rule x rule failing,row sets with lift vs independence.

    Failing = FAIL or WARNING (every row in the failure log). Lift =
    observed joint / expected joint; diagonal holds single counts.
    Returns (matrix DataFrame of joint counts, lift DataFrame).
    """
    failing = eval_long[eval_long["result"] != RuleResult.PASS.value]
    sets = {rid: {str(s) for s in
                  failing[failing["rule_id"] == rid]["source_row_number"].values}
            for rid in sorted(failing["rule_id"].unique())}
    universe = {str(s) for s in eval_long["source_row_number"].values}
    n = len(universe)
    ids = sorted(sets)
    joint = pd.DataFrame(0, index=ids, columns=ids)
    lift = pd.DataFrame(0.0, index=ids, columns=ids)
    for left in ids:
        for right in ids:
            both = len(sets[left] & sets[right])
            joint.loc[left, right] = both
            expected = len(sets[left]) * len(sets[right]) / n if n else 0
            lift.loc[left, right] = round(both / expected, 2) if expected else 0.0
    return joint, lift


def concentration(failing_srn, dims, dimension, min_rows=30, min_ratio=1.5):
    """Over-represented dimension values among failing rows.

    Compares each value's share of failing rows to its share of all rows;
    flags ratio >= min_ratio with at least min_rows failing rows.
    Returns DataFrame sorted by ratio descending.
    """
    total = len(dims)
    fail_set = {str(s) for s in failing_srn}
    fail_mask = dims["source_row_number"].astype(str).isin(fail_set)
    n_fail_total = int(fail_mask.sum())
    rows = []
    for value, group in dims.groupby(dimension, sort=True):
        n_fail = int((group["source_row_number"].astype(str).isin(
            fail_set)).sum())
        if n_fail_total and total:
            ratio = (n_fail / n_fail_total) / (len(group) / total)
        else:
            ratio = 0.0
        rows.append({"dimension_value": str(value),
                     "failing_rows": n_fail,
                     "share_of_failures": round(n_fail / n_fail_total, 4)
                     if n_fail_total else 0.0,
                     "share_of_rows": round(len(group) / total, 4)
                     if total else 0.0,
                     "ratio": round(ratio, 2),
                     "flagged": bool(n_fail >= min_rows
                                     and ratio >= min_ratio)})
    out = pd.DataFrame(rows, columns=["dimension_value", "failing_rows",
                                      "share_of_failures", "share_of_rows",
                                      "ratio", "flagged"])
    return out.sort_values("ratio", ascending=False).reset_index(drop=True)
