"""Shared dimension enrichment for reconciliation and analysis (Sprint 3).

Single home for the city/month/category/payment derivation so the
reconcile gates and the validation datamart cannot drift apart. All
matches are LEFT matches: unmatched customers or products form an
explicit UNMATCHED bucket, and unparseable dates an INVALID month, so
no row is ever dropped by an inner join.
"""

import pandas as pd

from .normalise import norm_id, parse_date, standardise

DIMENSIONS = ("city", "month", "category", "payment")


def match_master(orders, master, order_col, master_col, value_col, bucket):
    """LEFT match order values to master values (first wins, deterministic)."""
    lookup = {}
    if order_col in orders.columns and master_col in master.columns \
            and value_col in master.columns:
        for _, row in master.iterrows():
            key = norm_id(str(row[master_col]))
            if key and key not in lookup:
                lookup[key] = str(row[value_col]).strip()
    if order_col not in orders.columns:
        return pd.Series([bucket] * len(orders), index=orders.index)
    return orders[order_col].astype(str).str.strip().apply(
        lambda v: lookup.get(norm_id(v), bucket))


def order_month(value):
    """Order month YYYY-MM, or INVALID when unparseable."""
    day = parse_date(str(value))
    return f"{day.year:04d}-{day.month:02d}" if day else "INVALID"


def enrich_dimensions(frame, customers, products, ctx):
    """Add city/month/category/payment columns (never drops rows)."""
    out = frame.copy()
    city = match_master(frame, customers, "customer_id", "customer_id",
                        "city", "UNMATCHED")
    out["city"] = city.apply(
        lambda v: "UNMATCHED" if v == "UNMATCHED"
        else standardise(ctx.city_map, v, "UNMAPPED"))
    out["month"] = frame["order_date"].astype(str).apply(order_month) \
        if "order_date" in frame.columns else "INVALID"
    cat = match_master(frame, products, "product_id", "product_id",
                       "category", "UNMATCHED")
    out["category"] = cat.apply(
        lambda v: "UNMATCHED" if v == "UNMATCHED"
        else standardise(ctx.cat_map, v, "UNMAPPED"))
    out["payment"] = frame["payment_mode"].astype(str).apply(
        lambda v: standardise(ctx.pay_map, v, "UNMAPPED")) \
        if "payment_mode" in frame.columns else "UNMAPPED"
    return out
