"""Issue registry + quality datamart builders (Sprint 1)."""

import pandas as pd

from .normalise import parse_date, standardise
from .quality_checks import RULE_CATALOG


def build_issue_registry(checks, rules=None):
    """Build issue registry from check results."""
    if rules is None:
        rules = RULE_CATALOG
    rows = []
    for rule in rules:
        rule_id = rule["rule_id"]
        if rule_id in checks:
            fail_count = int(checks[rule_id].sum())
            rows.append({
                "rule_id": rule_id,
                "extract": rule["table"],
                "table": rule["table"],
                "column": rule.get("column", rule_id),
                "rule": rule_id,
                "predicate": rule["predicate"],
                "fail_count": fail_count,
                "count": fail_count,
                "treatment": rule["treatment"],
                "reason": f"Sprint-1 quality gate; see quality_summary.md ({rule_id}).",
                "pass_count": int(len(checks[rule_id]) - fail_count),
            })
    cols = ["rule_id", "extract", "table", "column", "rule", "predicate",
            "fail_count", "count", "treatment", "reason", "pass_count"]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows)[cols]


def build_quality_datamart(orders, checks, customers, products,
                           city_map, cat_map, pay_map, status_map):
    """Build quality datamart with issue flags per order."""
    df = orders.copy()

    def _month(v):
        d = parse_date(str(v))
        return f"{d.year:04d}-{d.month:02d}" if d else "INVALID"

    df["order_month"] = df["order_date"].astype(str).apply(_month)
    cust_city = dict(zip(customers["customer_id"].astype(str).str.strip(),
                         customers["city"].astype(str).str.strip()))
    prod_cat = dict(zip(products["product_id"].astype(str).str.strip(),
                        products["category"].astype(str).str.strip()))
    df["city_std"] = df["customer_id"].astype(str).str.strip().map(
        cust_city).fillna("UNKNOWN").map(
            lambda x: standardise(city_map, x, "UNMAPPED"))
    df["category_std"] = df["product_id"].astype(str).str.strip().map(
        prod_cat).fillna("UNKNOWN").map(
            lambda x: standardise(cat_map, x, "UNMAPPED"))
    df["payment_std"] = df["payment_mode"].astype(str).map(
        lambda x: standardise(pay_map, x, "UNMAPPED"))
    df["status_std"] = df["order_status"].astype(str).map(
        lambda x: standardise(status_map, x, "UNMAPPED"))
    order_checks = {k: v for k, v in checks.items()
                    if k.startswith("QC_ORD_")}
    for rule_id, mask in order_checks.items():
        df[f"flag_{rule_id}"] = mask.astype(int).values
    df["n_issues"] = sum(df[f"flag_{k}"].values for k in order_checks)
    cust_broken = checks.get("QC_ORD_CUST_FK_BROKEN",
                             pd.Series(False, index=orders.index))
    prod_broken = checks.get("QC_ORD_PROD_FK_BROKEN",
                             pd.Series(False, index=orders.index))
    df["is_broken_fk"] = (cust_broken | prod_broken).astype(int).values
    df["is_dup"] = checks.get(
        "QC_ORD_ROW_DUP",
        checks.get("QC_ORD_ID_DUP",
                   pd.Series(False, index=orders.index))).astype(int).values
    df["is_dup_id"] = checks.get(
        "QC_ORD_ID_DUP",
        pd.Series(False, index=orders.index)).astype(int).values
    return df


def build_quality_scorecard(customers, products, orders, checks):
    """Build aggregate quality scorecard."""
    table_prefixes = {
        "customers": "QC_CUST_",
        "products": "QC_PROD_",
        "orders": "QC_ORD_",
    }
    tables = {"customers": customers, "products": products, "orders": orders}
    rows = []
    for table, df in tables.items():
        prefix = table_prefixes[table]
        table_checks = {k: v for k, v in checks.items()
                        if k.startswith(prefix)}
        total_rows = len(df)
        total_checks = len(table_checks)
        total_cells = total_rows * len(df.columns)
        issue_cells = sum(int(v.sum()) for v in table_checks.values())
        rows.append({
            "table": table,
            "rows": total_rows,
            "columns": len(df.columns),
            "total_cells": total_cells,
            "checks_run": total_checks,
            "failed_cells": issue_cells,
            "quality_score_pct": round((1 - issue_cells / total_cells) * 100, 2)
            if total_cells > 0 else 100.0,
        })
    return pd.DataFrame(rows)


def concentration(df, dim, name):
    tmp = df.copy()
    tmp["_dim"] = dim.astype(str)
    out = tmp.groupby("_dim").size().reset_index(name="issues")
    out = out.rename(columns={"_dim": name}).sort_values("issues",
                                                         ascending=False)
    return out
