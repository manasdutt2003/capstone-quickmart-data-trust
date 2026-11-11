"""Trusted populations: strict / lenient / recommended + quarantine (Sprint 3).

Policies: strict excludes any FAIL or WARNING row; lenient excludes only
FAIL rows. RECOMMENDED_POLICY is lenient: WARNING rows stay flagged but
usable, because strict would additionally set aside every
payment-unknown, delivery-suspicious, unverifiable-price and
cancelled-with-days row, leaving Q4 headline answers on a sliver of
delivered value. Revisit only if a later quantified cutover says
otherwise.

Quarantine (rejected_orders): every set-aside row keeps source_file,
source_row_number, all original raw values, dedup_rule_applied and a
pipe-joined sorted list of failed rule_ids. PII deviation (documented):
customer_name, email, phone and their raw_* mirrors are NEVER written to
outputs/ (criterion #20); notes travel masked plus notes_sha256 of the
original text.
"""

import hashlib

import pandas as pd

from .commission import COMMISSION_RATE
from .line_value import row_line_value
from .llm_reporting import PII_PATTERNS
from .path_guard import assert_inside_write_root
from .validation_rules import (
    REGISTRY,
    RuleResult,
    evaluate_all,
)

RECOMMENDED_POLICY = "lenient"

DROPPED_PII_COLUMNS = (
    "customer_name", "email", "phone",
    "raw_customer_name", "raw_email", "raw_phone", "raw_notes",
    "_source_row",
)

POPULATION_COLUMNS = (
    "source_file", "source_row_number",
    "order_id", "customer_id", "product_id", "order_date", "quantity",
    "unit_price_paid", "discount", "payment_mode", "order_status",
    "delivery_days", "notes", "notes_sha256",
    "raw_order_id", "raw_customer_id", "raw_product_id", "raw_order_date",
    "raw_quantity", "raw_unit_price_paid", "raw_discount", "raw_payment_mode",
    "raw_order_status", "raw_delivery_days",
    "dedup_rule_applied", "rules_passed", "rules_failed",
    "line_value", "commission",
)


def mask_notes(text):
    """Mask email/phone patterns in free text (criterion #20)."""
    out = str(text)
    for pat in PII_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def notes_sha256(text):
    """SHA-256 of the original notes text."""
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _row_line_value(row):
    """Line value with legacy zero-fill mapping (single site: line_value)."""
    return row_line_value(row)


def _population_frame(orders_df, keep_index, fail_map, rate, with_failed_col):
    """Build one deterministic population frame (PII-scrubbed)."""
    base = orders_df.loc[keep_index].copy()
    out = pd.DataFrame(index=base.index)
    out["source_file"] = base["source_file"] if "source_file" in base.columns \
        else "UNKNOWN"
    if "source_row_number" in base.columns:
        out["source_row_number"] = base["source_row_number"].values
    else:
        out["source_row_number"] = range(1, len(base) + 1)

    def _col(name, default=""):
        return base[name].astype(str).values if name in base.columns \
            else [default] * len(base)

    for col in ("order_id", "customer_id", "product_id", "order_date",
                "quantity", "unit_price_paid", "discount", "payment_mode",
                "order_status", "delivery_days"):
        out[col] = _col(col)
    original_notes = base["raw_notes"].astype(str) \
        if "raw_notes" in base.columns else base["notes"].astype(str) \
        if "notes" in base.columns else pd.Series([""] * len(base),
                                                  index=base.index)
    out["notes"] = [mask_notes(v) for v in original_notes.values]
    out["notes_sha256"] = [notes_sha256(v) for v in original_notes.values]
    for col in ("raw_order_id", "raw_customer_id", "raw_product_id",
                "raw_order_date", "raw_quantity", "raw_unit_price_paid",
                "raw_discount", "raw_payment_mode", "raw_order_status",
                "raw_delivery_days"):
        out[col] = _col(col)
    out["dedup_rule_applied"] = base["dedup_rule_applied"] \
        if "dedup_rule_applied" in base.columns else ""
    for col in ("rules_passed", "rules_failed"):
        out[col] = base[col] if col in base.columns else ""
    lvs = [_row_line_value(row) for _, row in base.iterrows()]
    out["line_value"] = ["" if v is None else v for v in lvs]
    out["commission"] = ["" if v is None else round(v * rate, 2) for v in lvs]
    cols = list(POPULATION_COLUMNS)
    if with_failed_col:
        srn = out["source_row_number"]
        out["failed_rule_ids"] = ["|".join(sorted(fail_map.get(s, [])))
                                  for s in srn.values]
        cols = cols + ["failed_rule_ids"]
    out = out[cols]
    return out.sort_values(
        ["source_row_number", "order_id"]).reset_index(drop=True)


def build_populations(orders_df, ctx, rules=None, rate=COMMISSION_RATE):
    """Build strict / lenient / recommended(trusted) / rejected + failure log.

    Returns dict with frames plus the long evaluation frame. Deterministic.
    """
    long_ = evaluate_all(orders_df, ctx, rules)
    fail_map, warn_map = {}, {}
    for _, row in long_.iterrows():
        target = fail_map if row["result"] == RuleResult.FAIL.value \
            else warn_map if row["result"] == RuleResult.WARNING.value else None
        if target is not None:
            target.setdefault(row["source_row_number"], []).append(row["rule_id"])
    bad = set(fail_map)
    warned = set(warn_map) - bad
    keep_strict = [i for i in orders_df.index
                   if _srn_of(orders_df, i) not in bad
                   and _srn_of(orders_df, i) not in warned]
    keep_lenient = [i for i in orders_df.index
                    if _srn_of(orders_df, i) not in bad]
    keep_rejected = [i for i in orders_df.index
                     if _srn_of(orders_df, i) in bad]
    strict = _population_frame(orders_df, keep_strict, fail_map, rate, False)
    lenient = _population_frame(orders_df, keep_lenient, fail_map, rate, False)
    trusted = lenient.copy()
    rejected = _population_frame(orders_df, keep_rejected, fail_map, rate, True)
    order_ids = _order_id_map(orders_df)
    log_rows = long_[long_["result"] != RuleResult.PASS.value].copy()
    log_rows["order_id"] = [order_ids.get(s, "") for s in
                            log_rows["source_row_number"].values]
    rule_failure_log = log_rows[["source_row_number", "order_id", "rule_id",
                                 "result", "failing_detail"]].sort_values(
        ["source_row_number", "rule_id"]).reset_index(drop=True)
    return {"strict": strict, "lenient": lenient, "trusted": trusted,
            "rejected": rejected, "rule_failure_log": rule_failure_log,
            "eval_long": long_}


def _srn_of(orders_df, idx):
    if "_source_row" in orders_df.columns:
        return orders_df.loc[idx, "_source_row"]
    return orders_df.index.get_loc(idx) + 1


def _order_id_map(orders_df):
    if "_source_row" in orders_df.columns and \
            "order_id" in orders_df.columns:
        return dict(zip(orders_df["_source_row"].astype(str).values,
                        orders_df["order_id"].astype(str).values))
    if "order_id" in orders_df.columns:
        return {str(i + 1): str(v) for i, v in
                enumerate(orders_df["order_id"].astype(str).values)}
    return {}


def build_waterfall(raw_rows, loaded_rows, clean_orders, eval_long,
                    strict_frame, lenient_frame):
    """Waterfall raw -> load -> dedup -> R01..R12 -> trusted/strict.

    Sequential attribution in fixed rule order (R01 first ... R12 last):
    each rule removes FAIL rows still remaining. Independent counts run
    each rule on the full input; the gap between sequential and
    independent counts is rows failing multiple rules, attributed to the
    first rule that catches them. WARNING never removes.
    """
    rule_ids = [r.rule_id for r in REGISTRY.values()]
    remaining = set(clean_orders["source_row_number"].astype(str).values) \
        if "source_row_number" in clean_orders.columns else set()
    if not remaining:
        remaining = {str(i + 1) for i in range(len(clean_orders))}
    fails = {}
    for rid in rule_ids:
        sub = eval_long[(eval_long["rule_id"] == rid) &
                        (eval_long["result"] == RuleResult.FAIL.value)]
        fails[rid] = {str(s) for s in sub["source_row_number"].values}
    stages = [
        {"stage": "raw", "rows_in": raw_rows, "rows_removed": 0,
         "rows_out": raw_rows, "independent_removed": ""},
        {"stage": "loaded", "rows_in": raw_rows,
         "rows_removed": raw_rows - loaded_rows, "rows_out": loaded_rows,
         "independent_removed": ""},
        {"stage": "deduped", "rows_in": loaded_rows,
         "rows_removed": loaded_rows - len(clean_orders),
         "rows_out": len(clean_orders), "independent_removed": ""},
    ]
    running = set(remaining)
    for rid in rule_ids:
        attributed = sorted(fails.get(rid, set()) & running)
        running -= set(attributed)
        stages.append({"stage": rid, "rows_in": len(running) + len(attributed),
                       "rows_removed": len(attributed),
                       "rows_out": len(running),
                       "independent_removed": len(fails.get(rid, set()))})
    stages.append({"stage": "trusted_lenient", "rows_in": len(running),
                   "rows_removed": 0, "rows_out": len(lenient_frame),
                   "independent_removed": ""})
    stages.append({"stage": "strict", "rows_in": len(lenient_frame),
                   "rows_removed": len(lenient_frame) - len(strict_frame),
                   "rows_out": len(strict_frame), "independent_removed": ""})
    return pd.DataFrame(stages, columns=["stage", "rows_in", "rows_removed",
                                        "rows_out", "independent_removed"])


def population_csv_text(df):
    """Deterministic CSV text for hashing (no timestamps, LF endings)."""
    return df.to_csv(index=False, encoding="utf-8", lineterminator="\n")


def write_population_csv(df, path):
    """Write a population CSV through the path guard (fixed order, sorted)."""
    target = assert_inside_write_root(path)
    target.write_text(population_csv_text(df), encoding="utf-8",
                      newline="\n")
    return target


def write_waterfall_md(waterfall, join_log, path):
    """Write the waterfall + join log as markdown through the path guard."""
    target = assert_inside_write_root(path)
    lines = ["# Waterfall: raw rows to trusted orders", "",
             "| stage | rows_in | rows_removed | rows_out | independent_removed |",
             "|---|---|---|---|---|"]
    for _, row in waterfall.iterrows():
        lines.append(f"| {row['stage']} | {row['rows_in']} | "
                     f"{row['rows_removed']} | {row['rows_out']} | "
                     f"{row['independent_removed']} |")
    lines += ["", ("Sequential attribution runs R01 first ... R12 last; each "
                     "rule removes FAIL rows still remaining. Independent "
                     "counts run each rule on the full input; the gap is rows "
                     "failing multiple rules, attributed to the first "
                     "catcher. WARNING never removes."), "",
              "# Join row-count log", "",
              "| join | left_rows | right_rows | out_rows | dropped |",
              "|---|---|---|---|---|"]
    for _, row in join_log.iterrows():
        lines.append(f"| {row['join']} | {row['left_rows']} | "
                     f"{row['right_rows']} | {row['out_rows']} | "
                     f"{row['dropped']} |")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
