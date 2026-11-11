"""Datamart generator. All marts derive from trusted orders only."""

import pandas as pd

from .normalise import parse_date, standardise


def _iso_month(value):
    d = parse_date(str(value))
    return f"{d.year:04d}-{d.month:02d}" if d else "INVALID"


def _month_or(value, fallback):
    s = str(value)
    return s[:7] if isinstance(value, str) and len(value) >= 7 else fallback


def _flag_impossible_delivery(days):
    """Flag impossible delivery day values (Sprint 4, Q4d)."""
    if pd.isna(days):
        return "missing"
    elif days < 0:
        return "negative"
    elif days > 30:
        return "over_30"
    else:
        return "ok"


def enrich(trusted, customers, products, city_map, cat_map, status_map,
           pay_map):
    cust = customers.copy()
    cust["city_std"] = cust["city"].astype(str).map(
        lambda v: standardise(city_map, v, "UNMAPPED"))
    prod = products.copy()
    prod["category_std"] = prod["category"].astype(str).map(
        lambda v: standardise(cat_map, v, "UNMAPPED"))
    base = trusted.merge(cust[["customer_id", "city_std", "signup_date"]],
                         on="customer_id", how="left")
    base = base.merge(prod[["product_id", "category_std"]], on="product_id",
                      how="left")
    base["status_std"] = base["order_status"].astype(str).map(
        lambda v: standardise(status_map, v, "UNMAPPED"))
    base["payment_std"] = base["payment_mode"].astype(str).map(
        lambda v: standardise(pay_map, v, "UNMAPPED"))
    base["order_month"] = base["order_date"].astype(str).apply(_iso_month)
    base["city_std"] = base["city_std"].fillna("UNKNOWN")
    base["category_std"] = base["category_std"].fillna("UNKNOWN")
    return base


def _line_value(row):
    from .line_value import line_value
    from .normalise import parse_discount_frac, parse_float, parse_int
    try:
        q = int(row["quantity"]) if str(row["quantity"]).strip() != "" else None
    except (ValueError, TypeError):
        q = parse_int(str(row["quantity"]))
    try:
        p = float(row["unit_price_paid"]) \
            if str(row["unit_price_paid"]).strip() != "" else None
    except (ValueError, TypeError):
        p = parse_float(str(row["unit_price_paid"]))
    d = row.get("discount", 0)
    try:
        d = float(d) if d is not None and str(d).strip() != "" else 0.0
    except (ValueError, TypeError):
        d = parse_discount_frac(str(d)) or 0.0
    if q is None or p is None:
        return 0.0
    return line_value(q, p, d)


def build_marts(base):
    delivered = base[base["status_std"] == "Delivered"].copy()
    if "line_value" not in delivered.columns:
        delivered["line_value"] = delivered.apply(_line_value, axis=1)
    sales = (delivered.groupby(["order_month", "city_std", "category_std"],
                               as_index=False)
             .agg(orders=("order_id", "count"),
                  units=("quantity", lambda s: pd.to_numeric(s, errors="coerce")
                           .fillna(0).astype(int).sum()),
                  value=("line_value", "sum")))
    base = base.copy()
    if "line_value" not in base.columns:
        base["line_value"] = base.apply(_line_value, axis=1)
    cust_val = (delivered.groupby(["customer_id", "city_std"], as_index=False)
                .agg(orders=("order_id", "count"), value=("line_value", "sum"),
                     first_order=("order_date", "min"),
                     last_order=("order_date", "max")))
    payment = (base.groupby(["order_month", "city_std", "payment_std"],
                            as_index=False)
               .agg(orders=("order_id", "count"), value=("line_value", "sum")))
    
    # Delivery mart with impossible values flagged
    df = delivered.copy()
    df["delivery_days"] = pd.to_numeric(df["delivery_days"], errors="coerce")
    df["delivery_flag"] = df["delivery_days"].apply(_flag_impossible_delivery)
    
    valid = df[df["delivery_flag"] == "ok"]
    impossible = df[df["delivery_flag"] != "ok"]
    
    delivery = valid.groupby(["city_std", "category_std"], as_index=False).agg(
        orders=("order_id", "count"),
        avg_days=("delivery_days",
                  lambda s: round(pd.to_numeric(s, errors="coerce").mean(), 2)),
        median_days=("delivery_days",
                     lambda s: round(float(pd.to_numeric(s, errors="coerce").median()), 2)))
    
    impossible_counts = impossible.groupby(["city_std", "category_std"], dropna=False).agg(
        impossible_orders=("order_id", "count"),
        negative_orders=("delivery_flag", lambda x: (x == "negative").sum()),
        over_30_orders=("delivery_flag", lambda x: (x == "over_30").sum()),
        missing_orders=("delivery_flag", lambda x: (x == "missing").sum())
    ).reset_index()
    
    delivery = delivery.merge(impossible_counts, on=["city_std", "category_std"], how="left")
    for col in ["impossible_orders", "negative_orders", "over_30_orders", "missing_orders"]:
        delivery[col] = delivery[col].fillna(0).astype(int)
    
    tmp = delivered.copy()
    tmp["signup_month"] = tmp["signup_date"].astype(str).apply(
        lambda v: _month_or(v, "UNKNOWN"))
    cohort = (tmp.groupby(["signup_month", "order_month"], as_index=False)
              .agg(customers=("customer_id", "nunique"),
                   value=("line_value", "sum")))
    return {"sales": sales, "customer_value": cust_val, "payment": payment,
            "delivery": delivery, "cohort": cohort}


def build_sales_datamart(trusted, customers, products):
    df = trusted.copy()
    cust_city = dict(zip(customers["customer_id"].astype(str).str.strip(),
                         customers["city"].astype(str).str.strip()))
    prod_cat = dict(zip(products["product_id"].astype(str).str.strip(),
                        products["category"].astype(str).str.strip()))
    df["city"] = df["customer_id"].astype(str).str.strip().map(
        cust_city).fillna("UNKNOWN")
    df["category"] = df["product_id"].astype(str).str.strip().map(
        prod_cat).fillna("UNKNOWN")
    df["order_month"] = df["order_date"].apply(
        lambda x: _month_or(x, "INVALID"))
    df["line_value"] = df.apply(_line_value, axis=1)
    sales = df.groupby(["order_month", "city", "category", "order_status"],
                       dropna=False).agg(
        orders=("order_id", "count"),
        quantity=("quantity", lambda s: pd.to_numeric(s, errors="coerce")
                  .fillna(0).astype(int).sum()),
        revenue=("line_value", "sum")).reset_index()
    return sales


def build_customer_datamart(trusted, customers):
    df = trusted.copy()
    cust_city = dict(zip(customers["customer_id"].astype(str).str.strip(),
                         customers["city"].astype(str).str.strip()))
    cust_signup = dict(zip(customers["customer_id"].astype(str).str.strip(),
                           customers["signup_date"]))
    df["city"] = df["customer_id"].astype(str).str.strip().map(
        cust_city).fillna("UNKNOWN")
    df["signup_date"] = df["customer_id"].astype(str).str.strip().map(
        cust_signup)
    df["line_value"] = df.apply(_line_value, axis=1)
    df["order_month"] = df["order_date"].apply(
        lambda x: _month_or(x, "INVALID"))
    cust_agg = df.groupby(["customer_id", "city"], dropna=False).agg(
        total_orders=("order_id", "count"),
        total_quantity=("quantity", lambda s: pd.to_numeric(s, errors="coerce")
                       .fillna(0).astype(int).sum()),
        total_value=("line_value", "sum"),
        first_order=("order_date", "min"),
        last_order=("order_date", "max"),
        signup_date=("signup_date", "first")).reset_index()
    cust_agg["tenure_days"] = (
        pd.to_datetime(cust_agg["last_order"], errors="coerce")
        - pd.to_datetime(cust_agg["signup_date"], errors="coerce")).dt.days
    cust_agg["frequency_days"] = (
        (pd.to_datetime(cust_agg["last_order"], errors="coerce")
         - pd.to_datetime(cust_agg["first_order"], errors="coerce")).dt.days
        / cust_agg["total_orders"].clip(lower=1))
    return cust_agg


def build_payment_datamart(trusted, customers, products):
    df = trusted.copy()
    cust_city = dict(zip(customers["customer_id"].astype(str).str.strip(),
                         customers["city"].astype(str).str.strip()))
    df["city"] = df["customer_id"].astype(str).str.strip().map(
        cust_city).fillna("UNKNOWN")
    df["order_month"] = df["order_date"].apply(
        lambda x: _month_or(x, "INVALID"))
    df["line_value"] = df.apply(_line_value, axis=1)
    payment = df.groupby(["order_month", "city", "payment_mode"],
                         dropna=False).agg(
        orders=("order_id", "count"),
        revenue=("line_value", "sum")).reset_index()
    return payment


def build_delivery_datamart(trusted, customers, products):
    df = trusted.copy()
    df = df[df["order_status"] == "Delivered"].copy()
    cust_city = dict(zip(customers["customer_id"].astype(str).str.strip(),
                         customers["city"].astype(str).str.strip()))
    prod_cat = dict(zip(products["product_id"].astype(str).str.strip(),
                        products["category"].astype(str).str.strip()))
    df["city"] = df["customer_id"].astype(str).str.strip().map(
        cust_city).fillna("UNKNOWN")
    df["category"] = df["product_id"].astype(str).str.strip().map(
        prod_cat).fillna("UNKNOWN")
    df["delivery_days"] = pd.to_numeric(df["delivery_days"], errors="coerce")
    df["delivery_flag"] = df["delivery_days"].apply(_flag_impossible_delivery)
    
    # Aggregate by city, category with impossible values set aside
    valid = df[df["delivery_flag"] == "ok"]
    impossible = df[df["delivery_flag"] != "ok"]
    
    delivery = valid.groupby(["city", "category"], dropna=False).agg(
        orders=("order_id", "count"),
        avg_delivery_days=("delivery_days", "mean"),
        median_delivery_days=("delivery_days", "median"),
        min_delivery_days=("delivery_days", "min"),
        max_delivery_days=("delivery_days", "max"),
        on_time_pct=("delivery_days",
                     lambda x: (x <= 7).mean() * 100)).reset_index()
    
    # Add impossible counts as separate columns
    impossible_counts = impossible.groupby(["city", "category"], dropna=False).agg(
        impossible_orders=("order_id", "count"),
        negative_orders=("delivery_flag", lambda x: (x == "negative").sum()),
        over_30_orders=("delivery_flag", lambda x: (x == "over_30").sum()),
        missing_orders=("delivery_flag", lambda x: (x == "missing").sum())
    ).reset_index()
    
    delivery = delivery.merge(impossible_counts, on=["city", "category"], how="left")
    for col in ["impossible_orders", "negative_orders", "over_30_orders", "missing_orders"]:
        delivery[col] = delivery[col].fillna(0).astype(int)
    
    return delivery


def build_cohort_datamart(trusted, customers):
    df = trusted.copy()
    cust_signup = dict(zip(customers["customer_id"].astype(str).str.strip(),
                           customers["signup_date"]))
    df["signup_month"] = df["customer_id"].astype(str).str.strip().map(
        cust_signup).apply(lambda x: _month_or(x, "UNKNOWN"))
    df["order_month"] = df["order_date"].apply(
        lambda x: _month_or(x, "INVALID"))
    df = df[df["order_status"] == "Delivered"]
    cohort = df.groupby(["signup_month", "order_month"], dropna=False).agg(
        active_customers=("customer_id", "nunique"),
        orders=("order_id", "count")).reset_index()
    return cohort


def build_all_datamarts(trusted, customers, products, city_map=None,
                        cat_map=None, pay_map=None, status_map=None):
    """Build all analytical datamarts."""
    return {
        "sales_datamart": build_sales_datamart(trusted, customers, products),
        "customer_datamart": build_customer_datamart(trusted, customers),
        "payment_datamart": build_payment_datamart(trusted, customers,
                                                   products),
        "delivery_datamart": build_delivery_datamart(trusted, customers,
                                                      products),
        "cohort_datamart": build_cohort_datamart(trusted, customers),
    }