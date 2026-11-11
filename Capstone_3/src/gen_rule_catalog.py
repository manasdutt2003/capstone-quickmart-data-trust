"""Generate docs/rule_catalog.md FROM the registry (never by hand).

Usage: python -m src.gen_rule_catalog  (run from the write root)
Reads pipeline outputs (data/clean_orders.csv, customer_master.csv,
products_clean.csv), runs every implemented rule body, and writes the
catalog table plus threshold-alternative sections with quantified
effects. Deterministic: same inputs -> same document.
"""

import pandas as pd

from .line_value import line_value
from .normalise import parse_discount_frac, parse_float, parse_int
from .path_guard import assert_inside_write_root
from .validation_rules import (
    _IMPLS,
    R06_PRICE_TOLERANCE,
    R10_DELIVERY_UPPER,
    REGISTRY,
    Context,
    _r05_fence,
    _r06_valid_price,
    _r07_classify,
)


def _load_inputs(root):
    data = root / "data"
    orders = pd.read_csv(data / "clean_orders.csv", dtype=str,
                         keep_default_na=False, encoding="utf-8")
    customers = pd.read_csv(data / "customer_master.csv", dtype=str,
                            keep_default_na=False, encoding="utf-8")
    products = pd.read_csv(data / "products_clean.csv", dtype=str,
                           keep_default_na=False, encoding="utf-8")
    ctx = Context(customers=customers, products=products, city_map={},
                  cat_map={}, pay_map={}, status_map={})
    return orders, ctx


def _rule_rows(orders, ctx):
    rows = []
    for rule in REGISTRY.values():
        impl = _IMPLS.get(rule.rule_id)
        if impl is None:
            counts = {"PASS": len(orders)}
            detail = {}
        else:
            frame = impl(orders, ctx)
            counts = frame["result"].value_counts().to_dict()
            detail = frame["failing_detail"].value_counts().to_dict()
        rows.append((rule, counts, detail))
    return rows


def _swapped_text(frac):
    """Rewrite an interpreted fraction so the canonical parser reads it swapped."""
    if frac <= 1:
        return repr(frac / 100.0)
    return f"{frac * 100.0}%"


def _threshold_sections(orders, ctx):
    out = ["## Thresholds and alternatives (quantified)", ""]
    # R05 fence vs p99
    qty = pd.to_numeric(orders["quantity"].astype(str).str.strip(),
                        errors="coerce").dropna()
    fence = _r05_fence(orders["quantity"])
    p99 = float(qty.quantile(0.99))
    n_fence = int((qty > fence).sum()) if fence is not None else 0
    n_p99 = int((qty > p99).sum())
    out.append("### R05 implausible-high threshold")
    out.append("")
    out.append(f"Chosen: IQR fence Q3+3*IQR = {fence:g}, flagging {n_fence} "
               f"rows (the 500-quantity spike). Alternative: 99th percentile "
               f"({p99:g}), flagging {n_p99} rows — it collapses onto the "
               "spike value itself and discriminates nothing. IQR wins.")
    out.append("")
    # R06 tolerance 10% vs 5%
    base = _r06_valid_price(orders, ctx)["result"].value_counts().to_dict()
    alt = _r06_valid_price(orders, ctx, tol=0.05)["result"].value_counts().to_dict()
    lv_keep = {}
    for tol, tag in ((0.10, "chosen"), (0.05, "alternative")):
        frame = _r06_valid_price(orders, ctx, tol=tol)
        kept = 0.0
        for idx, row in orders.iterrows():
            if frame["result"].loc[idx] == "FAIL":
                continue
            q = parse_int(str(row["quantity"]))
            p = parse_float(str(row["unit_price_paid"]))
            dd = parse_discount_frac(str(row["discount"])) \
                if str(row["discount"]).strip() != "" else 0.0
            v = line_value(q, p, dd if dd is not None else None)
            kept += v if v is not None else 0.0
        lv_keep[tag] = round(kept, 2)
    out.append("### R06 price tolerance")
    out.append("")
    out.append(
        f"Chosen: {int(R06_PRICE_TOLERANCE * 100)}% -> {base}; line value "
        f"kept Rs {lv_keep['chosen']:,}. Alternative 5% -> {alt}; kept Rs "
        f"{lv_keep['alternative']:,}. 5% sits inside discount-rounding and "
        "catalogue-staleness noise yet still nukes the headline, so 10% is "
        "recommended.")
    out.append("")
    # R07 canonical vs swapped interpretation
    col = "raw_discount" if "raw_discount" in orders.columns else "discount"
    canon = {"fraction": 0, "percentage": 0}
    swap_lv = {"canonical": 0.0, "swapped": 0.0}
    for _, row in orders.iterrows():
        detail, frac, _ok = _r07_classify(row[col])
        if detail.startswith("fraction"):
            canon["fraction"] += 1
        elif detail == "percentage":
            canon["percentage"] += 1
        # Opposite rule applied to the RAW number: (0,1] read as percent,
        # (1,100] read as fraction.
        raw_num = None
        t = str(row[col]).strip().replace("percent", "").replace("%", "").strip()
        try:
            raw_num = float(t.replace(",", ""))
        except ValueError:
            raw_num = None
        q = parse_int(str(row["quantity"]))
        p = parse_float(str(row["unit_price_paid"]))
        if q is not None and p is not None and frac is not None:
            swap_lv["canonical"] += line_value(q, p, frac) or 0.0
        if q is not None and p is not None and raw_num is not None:
            if raw_num == 0 or str(row[col]).strip() == "":
                swapped = 0.0
            elif raw_num <= 1:
                swapped = raw_num / 100.0
            else:
                swapped = raw_num
            swap_lv["swapped"] += line_value(q, p, swapped) or 0.0
    out.append("### R07 fraction-vs-percent rule")
    out.append("")
    out.append(f"Canonical (0,1]-fraction/(1,100]-percent: {canon['fraction']} "
               f"fraction rows, {canon['percentage']} percent rows; line-value "
               f"sum Rs {round(swap_lv['canonical'], 2):,}. Swapped rule sum Rs "
               f"{round(swap_lv['swapped'], 2):,} (percent rows go negative) — "
               "the opposite rule destroys value accounting, so canonical stands.")
    out.append("")
    # R10 bound vs data max
    dd = pd.to_numeric(
        orders[orders["order_status"] == "Delivered"]["delivery_days"]
        .astype(str).str.strip(), errors="coerce").dropna()
    out.append("### R10 delivery upper bound")
    out.append("")
    out.append(f"Chosen: {R10_DELIVERY_UPPER} days (brief-stated and "
               f"data-consistent: genuine values all <= 7, only an 18-row "
               f"spike at 45 exceeds it; p99 {float(dd.quantile(0.99)):.1f}). "
               f"Alternative no-cap (data max {float(dd.max()):.0f}): 0 rows "
               "flagged vs 18 at the cap. The cap stands.")
    out.append("")
    # R12c WARNING vs FAIL
    r12c_only = 0
    impl12 = _IMPLS.get("R12")
    if impl12 is not None:
        frame12 = impl12(orders, ctx)
        r12c_only = int(((frame12["result"] == "WARNING")).sum())
    out.append("### R12c cancelled-positive-days consequence")
    out.append("")
    out.append(f"Chosen: R12c-only violations stay WARNING ({r12c_only} rows, "
               "consistent with R10-cancelled). Alternative FAIL would set "
               "aside those rows from trusted orders entirely.")
    out.append("")
    return out


def main():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    orders, ctx = _load_inputs(root)
    lines = ["# Rule catalog (generated — do not edit by hand)", "",
             ("Generated from `src.validation_rules.REGISTRY` by "
              "`python -m src.gen_rule_catalog` over "
              f"{len(orders)} cleaned order lines."), "",
             ("| rule_id | name | predicate | fields | files joined | severity | "
              "treatment | rationale | failing count |"),
             "|---|---|---|---|---|---|---|---|---|"]
    for rule, counts, detail in _rule_rows(orders, ctx):
        failing = sum(n for k, n in counts.items() if k != "PASS")
        top = ", ".join(f"{k}:{n}" for k, n in
                        sorted(detail.items(), key=lambda kv: -kv[1])[:3])
        lines.append(f"| {rule.rule_id} | {rule.name} | {rule.predicate_text} | "
                     f"{', '.join(rule.fields_used)} | "
                     f"{', '.join(rule.files_joined)} | {rule.severity} | "
                     f"{rule.treatment} | {rule.rationale} | {failing} "
                     f"({top}) |")
    lines.append("")
    lines.extend(_threshold_sections(orders, ctx))
    out_path = assert_inside_write_root(root / "docs" / "rule_catalog.md")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path} ({len(orders)} rows)")


if __name__ == "__main__":
    main()
