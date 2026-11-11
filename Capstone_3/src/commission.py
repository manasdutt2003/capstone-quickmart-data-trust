"""Commission calculations with breakdowns by month, city, payment, status."""

import pandas as pd

from .line_value import line_value
from .normalise import (
    parse_date,
    parse_discount_frac,
    parse_float,
    parse_int,
    standardise,
)

# Single source of truth: config/settings.json -> "commission_rate".
# COMMISSION_RATE mirrors it as the code default so existing callers
# (which pass no rate) keep working; pipeline passes settings rate explicitly.
COMMISSION_RATE = 0.08


def calculate_line_value(row):
    """Row-level line value with legacy zero-fill for invalid inputs.

    Parsing and guards are frozen (criterion #12 numbers depend on them);
    the arithmetic itself delegates to src.line_value.line_value.
    """
    qty = parse_int(str(row.get("quantity", 0)))
    price = parse_float(str(row.get("unit_price_paid", 0)))
    disc = parse_discount_frac(str(row.get("discount", 0)))
    if disc is None:
        disc = 0.0
    if qty is None or qty <= 0:
        return 0.0
    if price is None or price < 0:
        return 0.0
    if disc < 0 or disc >= 1:
        disc = 0.0
    return line_value(qty, price, disc)


def calculate_commission(line_value, rate=COMMISSION_RATE):
    return round(line_value * rate, 2)


def enrich_with_commission(orders, rate=COMMISSION_RATE):
    df = orders.copy()
    df["line_value"] = df.apply(calculate_line_value, axis=1).values
    df["commission"] = df["line_value"].apply(
        lambda v: calculate_commission(v, rate)).values
    return df


def _order_month(value):
    d = parse_date(str(value))
    return f"{d.year:04d}-{d.month:02d}" if d else "INVALID"


def standardize_dimensions(orders, city_map, cat_map, pay_map, status_map,
                           customers, products):
    df = orders.copy()
    cust_city = dict(zip(customers["customer_id"].astype(str).str.strip(),
                         customers["city"].astype(str).str.strip()))
    df["city_std"] = df["customer_id"].astype(str).str.strip().map(
        cust_city).fillna("UNKNOWN")
    df["city_std"] = df["city_std"].apply(
        lambda x: standardise(city_map, x, "UNMAPPED")).values
    prod_cat = dict(zip(products["product_id"].astype(str).str.strip(),
                        products["category"].astype(str).str.strip()))
    df["category_std"] = df["product_id"].astype(str).str.strip().map(
        prod_cat).fillna("UNKNOWN")
    df["category_std"] = df["category_std"].apply(
        lambda x: standardise(cat_map, x, "UNMAPPED")).values
    df["payment_std"] = df["payment_mode"].astype(str).apply(
        lambda x: standardise(pay_map, x, "UNMAPPED")).values
    df["status_std"] = df["order_status"].astype(str).apply(
        lambda x: standardise(status_map, x, "UNMAPPED")).values
    df["order_month"] = df["order_date"].astype(str).apply(_order_month).values
    return df


def commission_breakdown(df, group_cols):
    for col in group_cols:
        if col not in df.columns:
            df[col] = "UNKNOWN"
    grouped = df.groupby(group_cols, dropna=False).agg(
        orders=("order_id", "count"),
        commission=("commission", "sum"),
        line_value=("line_value", "sum"),
    ).reset_index().sort_values(group_cols)
    for col in ["commission", "line_value"]:
        if col in grouped.columns:
            grouped[col] = grouped[col].round(2)
    return grouped


def build_commission_datamart(raw_orders, clean_orders, customers, products,
                              city_map, cat_map, pay_map, status_map,
                              rate=COMMISSION_RATE):
    raw_enriched = enrich_with_commission(standardize_dimensions(
        raw_orders, city_map, cat_map, pay_map, status_map, customers,
        products), rate=rate)
    clean_enriched = enrich_with_commission(standardize_dimensions(
        clean_orders, city_map, cat_map, pay_map, status_map, customers,
        products), rate=rate)
    summary = pd.DataFrame([{
        "commission_before": round(raw_enriched["commission"].sum(), 2),
        "commission_after": round(clean_enriched["commission"].sum(), 2),
        "commission_leakage": round(raw_enriched["commission"].sum()
                                    - clean_enriched["commission"].sum(), 2),
        "line_value_before": round(raw_enriched["line_value"].sum(), 2),
        "line_value_after": round(clean_enriched["line_value"].sum(), 2),
        "orders_before": len(raw_orders),
        "orders_after": len(clean_orders),
        "rows_removed": len(raw_orders) - len(clean_orders),
        "commission_rate": rate,
    }])

    def compare_dimension(dim_col):
        before = raw_enriched.groupby(dim_col).agg(
            orders_before=("order_id", "count"),
            commission_before=("commission", "sum")).reset_index().sort_values(dim_col)
        after = clean_enriched.groupby(dim_col).agg(
            orders_after=("order_id", "count"),
            commission_after=("commission", "sum")).reset_index().sort_values(dim_col)
        merged = before.merge(after, on=dim_col, how="outer").fillna(0)
        merged["commission_leakage"] = (
            merged["commission_before"] - merged["commission_after"]).round(2)
        merged["orders_removed"] = (merged["orders_before"]
                                    - merged["orders_after"]).astype(int)
        return merged.sort_values(dim_col)

    return {
        "summary": summary,
        "by_month": commission_breakdown(clean_enriched, ["order_month"]),
        "by_city": commission_breakdown(clean_enriched, ["city_std"]),
        "by_payment": commission_breakdown(clean_enriched, ["payment_std"]),
        "by_status": commission_breakdown(clean_enriched, ["status_std"]),
        "by_month_city": commission_breakdown(clean_enriched,
                                             ["order_month", "city_std"]),
        "by_month_payment": commission_breakdown(
            clean_enriched, ["order_month", "payment_std"]),
        "by_month_status": commission_breakdown(clean_enriched,
                                               ["order_month", "status_std"]),
        "by_city_payment": commission_breakdown(clean_enriched,
                                               ["city_std", "payment_std"]),
        "by_city_status": commission_breakdown(clean_enriched,
                                              ["city_std", "status_std"]),
        "compare_month": compare_dimension("order_month"),
        "compare_city": compare_dimension("city_std"),
        "compare_payment": compare_dimension("payment_std"),
        "compare_status": compare_dimension("status_std"),
        "clean_enriched": clean_enriched,
        "raw_enriched": raw_enriched,
    }


def export_commission_datamart(marts, out_dir):
    from pathlib import Path
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    for name, df in marts.items():
        if isinstance(df, pd.DataFrame):
            df.to_csv(out_path / (f"commission_{name}.csv"), index=False,
                      encoding="utf-8", lineterminator="\n")
    marts["summary"].to_csv(out_path / "commission_datamart.csv", index=False,
                            encoding="utf-8", lineterminator="\n")
