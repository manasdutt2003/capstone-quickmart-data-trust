"""Deduplication report generator (Sprint 2)."""

import pandas as pd


def generate_deduplication_report(duplicate_registry, commission_marts,
                                  customer_master, clean_orders,
                                  raw_orders_count, out_path):
    """Generate comprehensive deduplication report in Markdown."""
    lines = []
    lines.append("# Deduplication Report")
    lines.append("")
    lines.append("*Generated on: {}*".format(pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")))
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    summary = commission_marts["summary"].iloc[0]
    lines.append(f"- **Raw Orders Processed**: {raw_orders_count}")
    lines.append("- **Clean Orders After Deduplication**: "
                 f"{int(summary['orders_after'])}")
    lines.append(f"- **Rows Removed**: {int(summary['rows_removed'])}")
    lines.append("- **Commission Before Cleaning**: Rs{:.2f}".format(summary["commission_before"]))
    lines.append("- **Commission After Cleaning**: Rs{:.2f}".format(summary["commission_after"]))
    lines.append("- **Commission Leakage (Recovered)**: Rs{:.2f}".format(summary["commission_leakage"]))
    lines.append("- **Commission Rate**: %.0f%%"
                 % (summary["commission_rate"] * 100))
    lines.append("")
    lines.append("## Duplicate Rule Catalog")
    lines.append("")
    lines.append("| Rule ID | Class | Description | Rationale | Removal Strategy |")
    lines.append("|---------|-------|-------------|-----------|------------------|")
    rule_details = {
        "D01": ("Exact Row Duplicates",
                "Identical business values across order columns",
                "System double-submission or ETL re-run",
                "Keep first, quarantine rest"),
        "D02": ("Order ID Conflicts",
                "Same order_id with different attribute values",
                "Order re-keyed with corrections",
                "Priority: Delivered first; then most complete"),
        "D03": ("Customer Duplicates",
                "Same normalized email across different customer_ids",
                "Customer registered multiple times",
                "Earliest signup survives; remap IDs"),
        "D04": ("Product Duplicates",
                "Same normalized product_id with different attributes",
                "Data entry inconsistency (P-10 vs P10)",
                "Canonicalize ID; merge if same product"),
        "D05": ("Order-Line Duplicates",
                "Same customer+product+date+qty+price",
                "Double-click checkout or retry",
                "Keep first by source_row"),
        "D06": ("Near Duplicates (Fuzzy)",
                "High-similarity matches on key attributes",
                "Typos in IDs, OCR errors",
                "Flag for manual review only"),
    }
    for rule_id, (name, desc, rationale, strategy) in rule_details.items():
        lines.append(f"| {rule_id} | {name} | {desc} | {rationale} | {strategy} |")
    lines.append("")
    lines.append("## Removal Counts by Rule")
    lines.append("")
    if duplicate_registry is not None and not duplicate_registry.empty \
            and "rule_id" in duplicate_registry.columns:
        rule_counts = duplicate_registry["rule_id"].value_counts().reset_index()
        rule_counts.columns = ["rule_id", "removals"]
        lines.append("| Rule ID | Removals |")
        lines.append("|---------|----------|")
        for _, row in rule_counts.iterrows():
            lines.append(f"| {row['rule_id']} | {int(row['removals'])} |")
    else:
        lines.append("*No duplicate registry data available*")
    lines.append("")
    lines.append("## Commission Analysis")
    lines.append("")
    lines.append("- **Commission Before Cleaning**: Rs{:.2f}".format(summary["commission_before"]))
    lines.append("- **Commission After Cleaning**: Rs{:.2f}".format(summary["commission_after"]))
    lines.append("- **Commission Leakage**: Rs{:.2f}".format(summary["commission_leakage"]))
    lines.append("- **Line Value Before**: Rs{:.2f}".format(summary["line_value_before"]))
    lines.append("- **Line Value After**: Rs{:.2f}".format(summary["line_value_after"]))
    lines.append("")

    def _table(title, df, cols, headers):
        lines.append(f"### {title}")
        lines.append("")
        if df is not None and not df.empty:
            lines.append("| {} |".format(" | ".join(headers)))
            lines.append("|{}|".format("|".join(["---"] * len(headers))))
            for _, row in df.iterrows():
                lines.append("| {} |".format(" | ".join(
                    str(row[c]) if c in df.columns else "N/A" for c in cols)))

    _table("Commission by Month (After Cleaning)",
           commission_marts.get("by_month"),
           ["order_month", "orders", "line_value", "commission"],
           ["Month", "Orders", "Line Value", "Commission"])
    lines.append("")
    _table("Commission by City (After Cleaning)",
           commission_marts.get("by_city"),
           ["city_std", "orders", "line_value", "commission"],
           ["City", "Orders", "Line Value", "Commission"])
    lines.append("")
    _table("Commission by Payment Method (After Cleaning)",
           commission_marts.get("by_payment"),
           ["payment_std", "orders", "line_value", "commission"],
           ["Payment Method", "Orders", "Line Value", "Commission"])
    lines.append("")
    _table("Commission by Order Status (After Cleaning)",
           commission_marts.get("by_status"),
           ["status_std", "orders", "line_value", "commission"],
           ["Status", "Orders", "Line Value", "Commission"])
    lines.append("")
    lines.append("## Before/After Comparison by Dimension")
    lines.append("")
    for dim_name, dim_key in [("Month", "compare_month"),
                              ("City", "compare_city"),
                              ("Payment Method", "compare_payment"),
                              ("Status", "compare_status")]:
        df = commission_marts.get(dim_key)
        if df is not None and not df.empty:
            lines.append(f"### {dim_name} Comparison")
            lines.append("")
            lines.append(f"| {dim_name} | Orders Before | Orders After | Removed | "
                         "Commission Before | Commission After | Leakage |")
            lines.append("|---|---|---|---|---|---|---|")
            for _, row in df.iterrows():
                lines.append(
                    f"| {row.iloc[0]} | {int(row.get('orders_before', 0))} | "
                    f"{int(row.get('orders_after', 0))} | "
                    f"{int(row.get('orders_removed', 0))} | "
                    f"Rs{row.get('commission_before', 0):.2f} | "
                    f"Rs{row.get('commission_after', 0):.2f} | "
                    f"Rs{row.get('commission_leakage', 0):.2f} |")
            lines.append("")
    n_remapped = 0
    if duplicate_registry is not None and not duplicate_registry.empty \
            and "rule_id" in duplicate_registry.columns:
        n_remapped = int((duplicate_registry["rule_id"] == "D03").sum())
    lines.append("## Customer Master Summary")
    lines.append("")
    lines.append(f"- **Unique Customers After Deduplication**: {len(customer_master)}")
    lines.append(f"- **Customer Duplicates Removed (D03)**: {n_remapped}")
    lines.append("")
    lines.append("## Hardest Cases Per Rule")
    lines.append("")
    lines.append("| Rule | Hardest Case | Resolution |")
    lines.append("|------|--------------|------------|")
    lines.append("| D01 | Exact duplicates with different source_row | "
                 "Kept first by source_row |")
    lines.append("| D02 | Same order_id Pending vs Delivered | "
                 "Kept Delivered (higher priority) |")
    lines.append("| D03 | Two ids share one email | Kept earlier signup |")
    lines.append("| D04 | Same normalized ID, different categories | "
                 "Kept both, flagged conflict |")
    lines.append("| D05 | Same customer/product/date/qty/price twice | "
                 "Kept first occurrence |")
    lines.append("| D06 | Similar names across cities | "
                 "Flagged for manual review |")
    lines.append("")
    lines.append("## Edge Cases Handled")
    lines.append("")
    lines.append("1. **Placeholder emails (NA, unknown, empty)**: Excluded from D03.")
    lines.append("2. **Conflicting product IDs (D04)**: Kept separate, flagged.")
    lines.append("3. **Order ID conflicts (D02)**: Priority Delivered > Cancelled > "
                 "Returned > In Transit > Pending > MISSING; then completeness.")
    lines.append("4. **Missing keys (D05)**: Excluded from matching.")
    lines.append("5. **Near duplicates (D06)**: Review only; no auto-removal.")
    lines.append("")
    lines.append("## Data Quality Notes")
    lines.append("")
    lines.append("- Deduplication on **cleaned data** (Sprint 1 cleaning stage).")
    lines.append("- Removals preserve **lineage** via `raw_*` + `_source_row`.")
    lines.append("- D03 remapping applied before D01/D02/D05.")
    lines.append("- Commission at **8% of line_value**.")
    lines.append("- Money rounded to **2 decimals**.")
    lines.append("")
    report = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(report)
    return report


def export_duplicate_registry_csv(duplicate_registry, out_path):
    """Export duplicate registry to CSV with standard schema."""
    cols = ["rule_id", "entity", "loser_key", "survivor_key", "evidence"]
    if duplicate_registry is not None and not duplicate_registry.empty:
        for col in cols:
            if col not in duplicate_registry.columns:
                duplicate_registry[col] = ""
        duplicate_registry[cols].to_csv(out_path, index=False,
                                          encoding="utf-8", lineterminator="\n")
    else:
        pd.DataFrame(columns=cols).to_csv(out_path, index=False,
                                          encoding="utf-8", lineterminator="\n")


def export_customer_master_csv(customer_master, out_path):
    """Export customer master to CSV."""
    customer_master.to_csv(out_path, index=False, encoding="utf-8",
                           lineterminator="\n")


def export_clean_orders_csv(clean_orders, out_path):
    """Export clean orders to CSV."""
    clean_orders.to_csv(out_path, index=False, encoding="utf-8",
                        lineterminator="\n")
