"""Profiling: one row per column with missing + usable = rows."""

import pandas as pd


def profile_table(df, table):
    rows = []
    n = len(df)
    for col in df.columns:
        s = df[col].astype(str)
        n_missing = int(((s.str.strip() == "") | (s.str.strip().str.upper().isin(
            {"NA", "N/A", "NULL", "NONE", "UNKNOWN", "?", "-", "--"}))).sum())
        usable = n - n_missing
        rows.append({
            "table": table,
            "column": col,
            "rows": n,
            "missing": n_missing,
            "usable": usable,
            "distinct": int(s.nunique()),
            "missing_pct": round(n_missing / n * 100, 2) if n else 0.0,
        })
    return pd.DataFrame(rows)


def profile_all(customers, products, orders):
    return pd.concat([
        profile_table(customers, "customers"),
        profile_table(products, "products"),
        profile_table(orders, "orders"),
    ], ignore_index=True)
