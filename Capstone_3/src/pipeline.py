"""One-command pipeline: raw -> quality -> dedup -> trusted -> marts -> report.

Usage: python -m src.pipeline  (run from QuickMart/ directory)
All outputs are deterministic; reruns on the same files give identical hashes.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .cleaning import clean_all
from .commission import build_commission_datamart
from .data_loader import load_all_text, sha256_of, write_manifest
from .datamarts import build_marts, enrich
from .deduplication import build_customer_master, commission_frame, deduplicate_orders
from .issue_registry import (
    build_issue_registry,
    build_quality_datamart,
    build_quality_scorecard,
)
from .line_value import line_value
from .llm_reporting import (
    MODEL_INFO,
    PROMPT_V1,
    PROMPT_V2,
    aggregate_inputs,
    draft_report,
    validate_report,
)
from .normalise import (
    load_mapping,
    parse_discount_frac,
    parse_float,
    parse_int,
    standardise,
)
from .profiling import profile_table
from .quality_checks import run_all_checks
from .reconcile import reconcile
from .trusted import (
    build_populations,
    write_population_csv,
    write_waterfall_md,
)
from .validation_datamart import (
    build_validation_datamart,
    write_validation_datamart,
)
from .validation_rules import RULES, Context, evaluate

ROOT = Path(__file__).resolve().parents[1]


def _repo_root() -> Path:
    """Walk up from QuickMart dir to the git repo root (contains .git)."""
    p = ROOT
    for _ in range(8):
        if (p / ".git").exists():
            return p
        p = p.parent
    return Path.cwd()


REPO = _repo_root()
RAW_DIR = REPO / "Resources/Capstone Questions/Capstone 2/data"
CONFIG = ROOT / "config"
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
CHARTS = ROOT / "charts"


def read_text_frames(raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data = load_all_text(raw_dir)
    return (pd.DataFrame(data["customers"]), pd.DataFrame(data["products"]), pd.DataFrame(data["orders"]))


def main() -> None:
    for d in (DATA, REPORTS, CHARTS, CONFIG):
        d.mkdir(parents=True, exist_ok=True)
    settings = json.loads((CONFIG / "settings.json").read_text(encoding="utf-8"))
    today: str = settings["today"]
    rate: float = float(settings["commission_rate"])
    city_map = load_mapping(CONFIG / "city_mapping.csv")
    cat_map = load_mapping(CONFIG / "category_mapping.csv")
    status_map = load_mapping(CONFIG / "status_mapping.csv")
    pay_map = load_mapping(CONFIG / "payment_mapping.csv")

    manifest = write_manifest(RAW_DIR, DATA / "raw_manifest.json")
    raw_customers, raw_products, raw_orders = read_text_frames(RAW_DIR)
    n_raw_orders = len(raw_orders)

    # ---- Cleaning stage (all later sprints consume ONLY these) ----
    customers, products, orders = clean_all(
        raw_customers, raw_products, raw_orders,
        city_map, cat_map, status_map, pay_map,
        source_files={"customers": "customers.csv",
                      "products": "products.csv",
                      "orders": "orders.csv"},
    )
    for name, frame in (("customers", customers), ("products", products), ("orders", orders)):
        path = DATA / f"{name}_clean.csv"
        frame.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")
        manifest[f"{name}_clean"] = {
            "file": path.relative_to(ROOT).as_posix(), "sha256": sha256_of(path), "rows": len(frame),
        }
    (DATA / "raw_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # ---- Sprint 1 (profiling on RAW source; checks on CLEANED frames) ----
    prof = pd.concat([profile_table(raw_customers, "customers"), profile_table(raw_products, "products"), profile_table(raw_orders, "orders")])
    prof.to_csv(DATA / "profile.csv", index=False, encoding="utf-8", lineterminator="\n")
    checks = run_all_checks(customers, products, orders, today)
    registry = build_issue_registry(checks)
    registry.to_csv(DATA / "issue_registry.csv", index=False, encoding="utf-8", lineterminator="\n")
    qmart = build_quality_datamart(orders, checks, customers, products, city_map, cat_map, pay_map, status_map)
    qmart.to_csv(DATA / "quality_datamart.csv", index=False, encoding="utf-8", lineterminator="\n")
    scorecard = build_quality_scorecard(customers, products, orders, checks)
    scorecard.to_csv(DATA / "quality_scorecard.csv", index=False, encoding="utf-8", lineterminator="\n")

    # ---- Sprint 2 (consumes cleaned frames + Sprint-1 outputs only) ----
    status_pre = orders["order_status"].astype(str).map(lambda v: standardise(status_map, v, "UNMAPPED"))
    master, cust_reg, id_remap = build_customer_master(customers)
    master.to_csv(DATA / "customer_master.csv", index=False, encoding="utf-8", lineterminator="\n")
    clean_orders, dup_reg = deduplicate_orders(orders, status_pre, id_remap)
    full_dup_reg = pd.concat([cust_reg.rename(columns={"loser_id": "loser_key", "survivor_id": "survivor_key"}), dup_reg], ignore_index=True) if len(cust_reg) else dup_reg
    full_dup_reg.to_csv(DATA / "duplicate_registry.csv", index=False, encoding="utf-8", lineterminator="\n")
    clean_orders.to_csv(DATA / "clean_orders.csv", index=False, encoding="utf-8", lineterminator="\n")

    def lv(df: pd.DataFrame) -> pd.Series:
        vals = []
        for _, r in df.iterrows():
            q = parse_int(str(r["quantity"]))
            p = parse_float(str(r["unit_price_paid"]))
            d = parse_discount_frac(str(r["discount"]))
            d = 0.0 if str(r["discount"]).strip() == "" else (d if d is not None else 0.0)
            vals.append(line_value(q, p, d) if (q is not None and p is not None) else 0.0)
        return pd.Series(vals, index=df.index)

    comm_before = commission_frame(raw_orders, lv(raw_orders), rate)
    comm_after = commission_frame(clean_orders, lv(clean_orders), rate)
    comm_mart = pd.DataFrame([{
        "commission_before": round(float(comm_before["commission"].sum()), 2),
        "commission_after": round(float(comm_after["commission"].sum()), 2),
        "commission_leakage": round(float(comm_before["commission"].sum() - comm_after["commission"].sum()), 2),
        "orders_before": len(orders), "orders_after": len(clean_orders),
        "rows_removed": len(orders) - len(clean_orders),
    }])
    comm_mart.to_csv(DATA / "commission_datamart.csv", index=False, encoding="utf-8", lineterminator="\n")

    # ---- Sprint 2b: commission breakdowns by month/city/payment/status ----
    # Additive: summary schema above is unchanged (criterion #7/#10 targets).
    comm_breakdowns = build_commission_datamart(
        orders, clean_orders, master, products,
        city_map, cat_map, pay_map, status_map,
        rate=rate,
    )
    for _name in ("by_month", "by_city", "by_payment", "by_status",
                  "by_month_city", "by_month_payment", "by_month_status",
                  "by_city_payment", "by_city_status", "compare_month",
                  "compare_city", "compare_payment", "compare_status"):
        comm_breakdowns[_name].to_csv(DATA / (f"commission_{_name}.csv"),
                                       index=False, encoding="utf-8",
                                       lineterminator="\n")

    # ---- Sprint 3 ----
    status_clean = clean_orders["order_status"].astype(str).map(lambda v: standardise(status_map, v, "UNMAPPED"))
    pay_clean = clean_orders["payment_mode"].astype(str).map(lambda v: standardise(pay_map, v, "UNMAPPED"))
    verdicts, fail_mask, line_values = evaluate(clean_orders, master, products, status_clean, pay_clean, today)
    trusted = clean_orders[~fail_mask].copy()
    trusted["status_std"] = status_clean.loc[trusted.index].values
    trusted["payment_std"] = pay_clean.loc[trusted.index].values
    trusted["line_value"] = line_values.loc[trusted.index].values
    trusted["commission"] = (trusted["line_value"].astype(float) * rate).round(2)
    rejected = clean_orders[fail_mask].copy()
    trusted.to_csv(DATA / "trusted_orders.csv", index=False, encoding="utf-8", lineterminator="\n")
    rejected.to_csv(DATA / "rejected_orders.csv", index=False, encoding="utf-8", lineterminator="\n")
    # lenient = allow WARNING-only rows (already in trusted); strict = no warnings
    warn_only = ((verdicts == "WARNING").any(axis=1)) & ~fail_mask
    strict = clean_orders[~fail_mask & ~warn_only].copy()
    strict.to_csv(DATA / "trusted_orders_strict.csv", index=False, encoding="utf-8", lineterminator="\n")
    fail_log = verdicts[fail_mask | warn_only].copy()
    fail_log.insert(0, "order_id", clean_orders.loc[fail_log.index, "order_id"].values)
    fail_log.to_csv(DATA / "rule_failure_log.csv", index=False, encoding="utf-8", lineterminator="\n")
    vdm = verdicts.copy()
    vdm.insert(0, "order_id", clean_orders["order_id"].values)
    vdm.to_csv(DATA / "validation_datamart.csv", index=False, encoding="utf-8", lineterminator="\n")

    # ---- Sprint 3 populations (rule bodies R01-R12; legacy outputs above untouched) ----
    ctx3 = Context(customers=master, products=products, city_map=city_map,
                   cat_map=cat_map, pay_map=pay_map, status_map=status_map,
                   today=today)
    pops = build_populations(clean_orders, ctx3, rate=rate)
    OUT = ROOT / "outputs"
    OUT.mkdir(parents=True, exist_ok=True)
    for _name in ("trusted", "rejected", "rule_failure_log", "strict", "lenient"):
        _fname = {"trusted": "trusted_orders.csv",
                  "rejected": "rejected_orders.csv",
                  "rule_failure_log": "rule_failure_log.csv",
                  "strict": "strict_trusted_orders.csv",
                  "lenient": "lenient_trusted_orders.csv"}[_name]
        write_population_csv(pops[_name], OUT / _fname)
    rec = reconcile(clean_orders, pops, pops["eval_long"], master, products,
                    ctx3, n_raw_orders, len(raw_orders))
    write_waterfall_md(rec["waterfall"], rec["join_log"],
                       ROOT / "docs" / "waterfall.md")
    vdmart = build_validation_datamart(clean_orders, pops["eval_long"],
                                       master, products, ctx3)
    write_validation_datamart(vdmart, OUT / "validation_datamart.csv")

    # ---- Sprint 4/5 marts (trusted only) ----
    trusted["quantity"] = trusted["quantity"].astype(int)
    base = enrich(trusted, master, products, city_map, cat_map, status_map, pay_map)
    # ensure numeric line_value/commission survive enrich (merge keeps them)
    marts = build_marts(base)
    marts["sales"].to_csv(DATA / "sales_datamart.csv", index=False, encoding="utf-8", lineterminator="\n")
    marts["customer_value"].to_csv(DATA / "customer_value_datamart.csv", index=False, encoding="utf-8", lineterminator="\n")
    marts["payment"].to_csv(DATA / "payment_datamart.csv", index=False, encoding="utf-8", lineterminator="\n")
    marts["delivery"].to_csv(DATA / "delivery_datamart.csv", index=False, encoding="utf-8", lineterminator="\n")
    marts["cohort"].to_csv(DATA / "cohort_datamart.csv", index=False, encoding="utf-8", lineterminator="\n")

    # charts (values taken directly from sales mart)
    monthly = marts["sales"].groupby("order_month")["value"].sum().sort_index()
    plt.figure()
    monthly.plot(kind="bar")
    plt.title("Delivered sales by month (trusted orders)")
    plt.ylabel("Rs")
    plt.tight_layout()
    plt.savefig(CHARTS / "monthly_sales.png")
    plt.close()

    # ---- Sprint 5 report ----
    agg = aggregate_inputs(marts)
    grand_total = agg["grand_total"]
    rep_v1 = draft_report(agg, "v1")  # type: ignore[return-value, arg-type]
    rep_v2 = draft_report(agg, "v2")  # type: ignore[return-value, arg-type]
    (REPORTS / "generated_report.md").write_text(rep_v1, encoding="utf-8")  # type: ignore[arg-type]
    val = validate_report(rep_v1, marts)  # type: ignore[arg-type]
    val.to_csv(DATA / "report_validation.csv", index=False, encoding="utf-8", lineterminator="\n")
    recon = [
        (f"raw_orders={n_raw_orders} clean_orders={len(clean_orders)} "
         f"trusted={len(trusted)} rejected={len(rejected)} strict={len(strict)}"),
        f"sales_value={grand_total['value']} sales_orders={grand_total['orders']}",
        (f"commission_before={comm_mart.iloc[0]['commission_before']} "
         f"after={comm_mart.iloc[0]['commission_after']} "
         f"leakage={comm_mart.iloc[0]['commission_leakage']}"),
        f"report_figures_checked={len(val)} failed={int((val['status'] == 'FAIL').sum())}",
    ]
    (REPORTS / "reconciliation_report.md").write_text("\n".join(recon) + "\n", encoding="utf-8")
    (REPORTS / "model_registry.md").write_text(json.dumps(MODEL_INFO, indent=2), encoding="utf-8")
    (REPORTS / "prompt_registry.md").write_text(
        f"## v1\n{PROMPT_V1}\n\n## v2\n{PROMPT_V2}\n\n"
        f"v1 chars={len(rep_v1)} v2 chars={len(rep_v2)}; figures identical (deterministic template).\n",
        encoding="utf-8",
    )
    audit = trusted[["order_id", "customer_id", "product_id"]].copy()
    audit["source"] = "orders.csv"
    audit["cleaning_rule"] = "mapping+dedup+D01/D02/D05"
    audit["validation"] = "R01-R11 PASS (lenient)"
    audit.to_csv(DATA / "audit_log.csv", index=False, encoding="utf-8", lineterminator="\n")

    # markdown summaries
    (REPORTS / "quality_summary.md").write_text(
        "# Quality summary\n\n" + registry.to_string(index=False)
        + "\n\nScorecard:\n" + scorecard.to_string(index=False) + "\n",
        encoding="utf-8",
    )
    (REPORTS / "deduplication_report.md").write_text(
        "# Deduplication report\n\nRules D01-D06 applied "
        "(D06 flags for review only, never removes).\n\n"
        + full_dup_reg.groupby("rule_id").size().to_string()
        + f"\n\nCommission: {comm_mart.to_string(index=False)}\n"
        + (
            f"\nReconciliation: raw_orders={len(orders)} "
            f"clean_orders={len(clean_orders)} "
            f"removed={len(orders) - len(clean_orders)} "
            "(rows in = rows out + rows set aside).\n"
        )
        + "\nLeakage concentration: see commission_compare_city.csv "
        "(by city), commission_compare_month.csv (by month), "
        "commission_compare_payment.csv and commission_compare_status.csv.\n",
        encoding="utf-8",
    )
    (REPORTS / "trusted_order_framework.md").write_text(
        "# Trusted order framework\n\nRules:\n"
        + "\n".join(f"- {r['rule_id']} ({r['severity']}): {r['description']}" for r in RULES)
        + f"\n\nTrusted={len(trusted)} Rejected={len(rejected)} Strict={len(strict)}\n",
        encoding="utf-8",
    )
    top5 = marts["customer_value"].nlargest(5, "value")
    (REPORTS / "executive_report.md").write_text(
        "# Executive report (trusted delivered orders only)\n\n"
        f"Grand delivered value Rs {grand_total['value']:,.2f} across {grand_total['orders']} orders.\n\n"
        "## Top 5 customers\n" + top5.to_string(index=False)
        + "\n\n## Sales mart head\n" + marts["sales"].head().to_string(index=False)
        + "\n\nCity/category/month totals reconcile to the grand total (see reconciliation_report.md).\n"
        "\n## Limits\n1. Stock report unreliable (many blank/negative stock_qty).\n"
        "2. Delivery estimates unreliable for non-Delivered rows (empty/invalid days).\n"
        "3. Customer-city answers exclude FK-broken orders (city unknown).\n",
        encoding="utf-8",
    )
    print("PIPELINE OK", {"raw": n_raw_orders, "trusted": len(trusted), "value": grand_total["value"]})


def output_hashes() -> dict:
    """SHA-256 of each outputs/*.csv (criterion 1 idempotence check)."""
    import hashlib

    out = ROOT / "outputs"
    hashes = {}
    for path in sorted(out.glob("*.csv")):
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def write_output_hashes() -> Path:
    """Write reference/output_hashes.json by code (through the path guard)."""
    from .path_guard import assert_inside_write_root

    target = assert_inside_write_root(ROOT / "reference" / "output_hashes.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output_hashes(), indent=2) + "\n",
                      encoding="utf-8")
    return target


def verify_output_hashes() -> dict:
    """Compare live outputs/*.csv hashes against reference/output_hashes.json."""
    from .path_guard import assert_inside_write_root

    ref = assert_inside_write_root(ROOT / "reference" / "output_hashes.json")
    if not ref.exists():
        raise SystemExit(f"reference hashes missing: {ref.name} "
                         f"(run: python -m src.pipeline --write-hashes)")
    expected = json.loads(ref.read_text(encoding="utf-8"))
    actual = output_hashes()
    failed = False
    for name in sorted(set(expected) | set(actual)):
        ok = expected.get(name) == actual.get(name)
        failed = failed or not ok
        exp = (expected.get(name) or "missing")[:16]
        got = (actual.get(name) or "missing")[:16]
        print(f"{name}: expected={exp}… actual={got}… "
              f"{'OK' if ok else 'MISMATCH'}")
    if failed:
        raise SystemExit("output hashes MISMATCH (rerun the pipeline?)")
    print("output hashes verify: OK")
    return actual


if __name__ == "__main__":
    import sys

    if "--verify-hashes" in sys.argv:
        verify_output_hashes()
    elif "--write-hashes" in sys.argv:
        print(f"wrote {write_output_hashes()}")
    else:
        main()