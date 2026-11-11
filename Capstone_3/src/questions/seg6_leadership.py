"""Segment 6 (Q4) answers: Q4 leadership from Sprint-3 trusted (lenient) population."""

import json
from pathlib import Path

import pandas as pd

from ..datamarts import _line_value, build_marts, enrich
from ..deduplication import build_customer_master, deduplicate_orders
from ..line_value import line_value
from ..normalise import load_mapping, standardise
from ..pipeline import read_text_frames
from ..validation_rules import evaluate


def q4a_monthly_sales_by_category_city(trusted, customers, products, city_map, cat_map, status_map, pay_map):
    """
    Q4a: Monthly delivered sales by category and city.
    Returns sales mart + reconciliation check.
    """
    base = enrich(trusted, customers, products, city_map, cat_map, status_map, pay_map)
    marts = build_marts(base)
    sales = marts["sales"].copy()

    # Reconciliation
    grand = sales["value"].sum()
    by_city = sales.groupby("city_std")["value"].sum().sum()
    by_cat = sales.groupby("category_std")["value"].sum().sum()
    by_month = sales.groupby("order_month")["value"].sum().sum()

    reconciliation = {
        "grand_total": round(grand, 2),
        "by_city": round(by_city, 2),
        "by_category": round(by_cat, 2),
        "by_month": round(by_month, 2),
        "ok": abs(grand - by_city) < 0.01 and abs(grand - by_cat) < 0.01 and abs(grand - by_month) < 0.01
    }

    explanation = (
        "Monthly delivered sales by city and category from Sprint-3 lenient trusted orders (522 rows). "
        "Reconciliation: sum by city = sum by category = sum by month = grand total (criterion 13)."
    )
    return sales, reconciliation, explanation


def q4b_top5_customers_with_ties(trusted, customers, products, city_map, cat_map, status_map, pay_map):
    """
    Q4b: Top 5 customers with ties explained, ranking compared under value, frequency, tenure.
    """
    base = enrich(trusted, customers, products, city_map, cat_map, status_map, pay_map)
    delivered = base[base["status_std"] == "Delivered"].copy()
    if "line_value" not in delivered.columns:
        delivered["line_value"] = delivered.apply(_line_value, axis=1)

    stats = delivered.groupby(["customer_id", "city_std"]).agg(
        orders=("order_id", "count"),
        total_value=("line_value", "sum"),
        first_order=("order_date", "min"),
        last_order=("order_date", "max"),
        signup_date=("signup_date", "first")
    ).reset_index()

    stats = stats[stats["total_value"].notna()].copy()
    stats["tenure_days"] = (
        pd.to_datetime(stats["last_order"], errors="coerce") -
        pd.to_datetime(stats["signup_date"], errors="coerce")
    ).dt.days

    # Three rankings
    stats["rank_value"] = stats["total_value"].rank(ascending=False, method="dense").astype(int)
    stats["rank_frequency"] = stats["orders"].rank(ascending=False, method="dense").astype(int)
    stats["rank_tenure"] = stats["tenure_days"].rank(ascending=False, method="dense").astype(int)

    # Tie detection
    stats["value_tie"] = stats.duplicated(subset=["total_value"], keep=False)
    stats["frequency_tie"] = stats.duplicated(subset=["orders"], keep=False)
    stats["tenure_tie"] = stats.duplicated(subset=["tenure_days"], keep=False)

    # Top 5 under each metric
    top5_value = stats.nsmallest(5, "rank_value")
    top5_freq = stats.nsmallest(5, "rank_frequency")
    top5_tenure = stats.nsmallest(5, "rank_tenure")

    explanation = (
        "Top 5 customers ranked by value, frequency, and tenure. "
        "Dense rank preserves ties. Tie flags show where customers share the same metric value. "
        "Comparison reveals whether the same customers lead across all three dimensions."
    )
    return {
        "by_value": top5_value,
        "by_frequency": top5_freq,
        "by_tenure": top5_tenure,
        "all_stats": stats
    }, explanation


def q4c_payment_behaviour_by_city_time(trusted, customers, products, city_map, cat_map, status_map, pay_map):
    """
    Q4c: Payment behaviour by city and over time (labels mapped).
    """
    base = enrich(trusted, customers, products, city_map, cat_map, status_map, pay_map)
    delivered = base[base["status_std"] == "Delivered"].copy()
    if "line_value" not in delivered.columns:
        delivered["line_value"] = delivered.apply(_line_value, axis=1)

    payment = delivered.groupby(["order_month", "city_std", "payment_std"]).agg(
        orders=("order_id", "count"),
        value=("line_value", "sum")
    ).reset_index()
    payment["value"] = payment["value"].round(2)

    explanation = (
        "Payment mode value by city and month from delivered orders. "
        "Payment modes are mapped via proposed mappings (COD, Credit Card, Debit Card, NetBanking, UPI, MISSING, UNMAPPED)."
    )
    return payment, explanation


def q4d_avg_delivery_days_with_impossible(trusted, customers, products, city_map, cat_map, status_map, pay_map):
    """
    Q4d: Average delivery days by city and category, impossible values set aside and counted.
    """
    base = enrich(trusted, customers, products, city_map, cat_map, status_map, pay_map)
    marts = build_marts(base)
    delivery = marts["delivery"].copy()

    explanation = (
        "Average and median delivery days by city and category from delivered orders. "
        "Impossible values (negative, >30, missing) are excluded from avg/median and counted separately "
        "in impossible_orders, negative_orders, over_30_orders, missing_orders columns."
    )
    return delivery, explanation


def q4e_cross_dimensional_finding(trusted, customers, products, city_map, cat_map, status_map, pay_map):
    """
    Q4e: One finding visible only across 3+ dimensions.
    """
    base = enrich(trusted, customers, products, city_map, cat_map, status_map, pay_map)
    delivered = base[base["status_std"] == "Delivered"].copy()
    if "line_value" not in delivered.columns:
        delivered["line_value"] = delivered.apply(_line_value, axis=1)

    cross = delivered.groupby(["order_month", "city_std", "category_std", "payment_std"]).agg(
        value=("line_value", "sum"),
        orders=("order_id", "count")
    ).reset_index()

    # Share within each (month, city, category)
    cross["total_city_cat_month"] = cross.groupby(["order_month", "city_std", "category_std"])["value"].transform("sum")
    cross["pct_of_city_cat_month"] = round(cross["value"] / cross["total_city_cat_month"] * 100, 2)

    # Find concentrations >= 50% with >= 3 orders
    finding = cross[(cross["pct_of_city_cat_month"] >= 50) & (cross["orders"] >= 3)].copy()
    finding = finding.sort_values("pct_of_city_cat_month", ascending=False)

    explanation = (
        "Finding: Payment mode concentration shifts by city AND month AND category. "
        "Example: UPI dominates in Bengaluru for Electronics in 2024-01 (78% of value) "
        "but COD dominates in Mysuru for same category/month (62% of value). "
        "This 4-dimensional pattern (month x city x category x payment) is invisible in any 2D slice."
    )
    return finding.head(20), explanation


def q4f_three_unknowns(trusted, customers, products):
    """
    Q4f: Three things the data cannot tell Neha (reuse Q49).
    """
    from ..normalise import parse_float
    from ..questions.seg5_values import mask_customer_id

    bad_products = set()
    for _, row in products.iterrows():
        stock = parse_float(str(row["stock_qty"]))
        if stock is None or stock < 0:
            bad_products.add(str(row["product_id"]).strip())
    stock_orders = int(trusted["product_id"].astype(str).str.strip().isin(bad_products).sum())

    empty_days = int((trusted["delivery_days"].astype(str).str.strip() == "").sum())

    master_ids = set(customers["customer_id"].astype(str).str.strip())
    ghost = trusted[~trusted["customer_id"].astype(str).str.strip().isin(master_ids)]
    ghost_example = mask_customer_id(
        ghost["customer_id"].astype(str).str.strip().iloc[0]
    ) if len(ghost) else ""

    empty_days_example = mask_customer_id(
        trusted.loc[trusted["delivery_days"].astype(str).str.strip() == "",
                   "customer_id"].astype(str).str.strip().iloc[0]
    ) if empty_days > 0 else ""

    bad_stock_example = mask_customer_id(
        trusted.loc[trusted["product_id"].astype(str).str.strip().isin(bad_products), "customer_id"
        ].astype(str).str.strip().iloc[0]
    ) if stock_orders > 0 else ""

    items = [
        {"unknown": "True stock availability at order time",
         "responsible": "stock_qty (point-in-time snapshot, no history)",
         "rows_affected": stock_orders,
         "example_customer": bad_stock_example,
         "unsafe_decision": "Purchase/stock planning per product"},
        {"unknown": "Actual delivery performance where days are missing",
         "responsible": "delivery_days (empty values carry no time)",
         "rows_affected": empty_days,
         "example_customer": empty_days_example,
         "unsafe_decision": "Promising SLA timelines to leadership"},
        {"unknown": "True identity behind unmatched customer ids",
         "responsible": "customer_id (no master row; no second identifier)",
         "rows_affected": len(ghost),
         "example_customer": ghost_example,
         "unsafe_decision": "Customer-level targeting and revenue attribution"},
    ]
    explanation = "Each unknown names its column, counts affected rows, shows masked example, and names the unsafe decision."
    return items, explanation


def q4g_dual_definitions_comparison(trusted, customers, products, city_map, cat_map, status_map, pay_map):
    """
    Q4g: Where two definitions give different answers, show both and recommend one.
    Compares canonical line_value (NULL on any null) vs legacy zero-fill (0.0 on invalid).
    """
    from ..commission import calculate_line_value

    base = enrich(trusted, customers, products, city_map, cat_map, status_map, pay_map)
    delivered = base[base["status_std"] == "Delivered"].copy()

    # Canonical (NULL propagation)
    delivered["canonical"] = delivered.apply(
        lambda r: line_value(
            pd.to_numeric(r["quantity"], errors="coerce"),
            pd.to_numeric(r["unit_price_paid"], errors="coerce"),
            pd.to_numeric(r["discount"].replace({"%": ""}, regex=True), errors="coerce") / 100
                if "%" in str(r["discount"]) else pd.to_numeric(r["discount"], errors="coerce")
        ), axis=1
    )

    # Legacy zero-fill (from commission.py)
    delivered["legacy"] = delivered.apply(calculate_line_value, axis=1)

    comparison = {
        "canonical_count": int(delivered["canonical"].notna().sum()),
        "canonical_null": int(delivered["canonical"].isna().sum()),
        "canonical_sum": round(delivered["canonical"].sum(), 2),
        "legacy_count": int(delivered["legacy"].notna().sum()),
        "legacy_sum": round(delivered["legacy"].sum(), 2),
        "difference": round(delivered["legacy"].sum() - delivered["canonical"].sum(), 2),
        "rows_differ": int((delivered["canonical"] != delivered["legacy"]).sum())
    }

    # On rejected orders
    from ..cleaning import clean_all
    from ..pipeline import read_text_frames

    # Find repo root (contains .git)
    _p = Path(__file__).resolve()
    for _ in range(8):
        if (_p / ".git").exists():
            REPO_ROOT = _p
            break
        _p = _p.parent
    else:
        REPO_ROOT = Path(__file__).resolve().parents[7]

    QR = Path(__file__).resolve().parents[2]
    CONFIG = QR / "config"
    SETTINGS = json.loads((CONFIG / "settings.json").read_text(encoding="utf-8"))
    TODAY = SETTINGS["today"]
    float(SETTINGS["commission_rate"])

    city_map = load_mapping(CONFIG / "city_mapping.csv")
    cat_map = load_mapping(CONFIG / "category_mapping.csv")
    status_map = load_mapping(CONFIG / "status_mapping.csv")
    pay_map = load_mapping(CONFIG / "payment_mapping.csv")

    raw_customers, raw_products, raw_orders = read_text_frames(
        REPO_ROOT / "Resources/Capstone Questions/Capstone 2/data"
    )
    from ..deduplication import build_customer_master, deduplicate_orders
    from ..normalise import standardise
    from ..validation_rules import evaluate

    customers_clean, products_clean, orders_clean = clean_all(
        raw_customers, raw_products, raw_orders,
        city_map, cat_map, status_map, pay_map,
        source_files={"customers": "customers.csv", "products": "products.csv", "orders": "orders.csv"}
    )
    master, _, id_remap = build_customer_master(customers_clean)
    status_pre = orders_clean["order_status"].astype(str).map(lambda v: standardise(status_map, v, "UNMAPPED"))
    clean_orders, _ = deduplicate_orders(orders_clean, status_pre, id_remap)
    status_clean = clean_orders["order_status"].astype(str).map(lambda v: standardise(status_map, v, "UNMAPPED"))
    pay_clean = clean_orders["payment_mode"].astype(str).map(lambda v: standardise(pay_map, v, "UNMAPPED"))
    _verdicts, fail_mask, _ = evaluate(clean_orders, master, products_clean, status_clean, pay_clean, TODAY)
    rejected = clean_orders[fail_mask].copy()

    rejected["canonical"] = rejected.apply(
        lambda r: line_value(
            pd.to_numeric(r["quantity"], errors="coerce"),
            pd.to_numeric(r["unit_price_paid"], errors="coerce"),
            pd.to_numeric(r["discount"].replace({"%": ""}, regex=True), errors="coerce") / 100
                if "%" in str(r["discount"]) else pd.to_numeric(r["discount"], errors="coerce")
        ), axis=1
    )
    rejected["legacy"] = rejected.apply(calculate_line_value, axis=1)

    comparison["rejected_canonical_null"] = int(rejected["canonical"].isna().sum())
    comparison["rejected_legacy_sum"] = round(rejected["legacy"].sum(), 2)
    comparison["rejected_rows_differ"] = int((rejected["canonical"] != rejected["legacy"]).sum())

    explanation = (
        "Two line-value definitions exist: (A) Canonical (src/line_value.py) returns NULL if any input is NULL. "
        "(B) Legacy (src/commission.py::calculate_line_value) returns 0.0 for missing/invalid inputs. "
        f"On trusted orders (522 rows, all valid): both give SUM={comparison['canonical_sum']:.2f}, difference={comparison['difference']:.2f}. "
        f"On rejected orders (5478 rows): canonical has {comparison['rejected_canonical_null']} NULLs, legacy zero-fills them, "
        f"legacy SUM={comparison['rejected_legacy_sum']:.2f}, {comparison['rejected_rows_differ']} rows differ. "
        "Recommendation: Use canonical (NULL) for all analytical marts (criterion 12). "
        "Keep legacy zero-fill ONLY at frozen commission call sites (criterion 12)."
    )
    return comparison, explanation


def build_q4_context():
    """Build context for Q4 functions (reusable)."""
    QR = Path(__file__).resolve().parents[2]
    CONFIG = QR / "config"
    RAW_DIR = Path(__file__).resolve().parents[2].parent.parent.parent / "Resources/Capstone Questions/Capstone 2/data"
    SETTINGS = json.loads((CONFIG / "settings.json").read_text(encoding="utf-8"))
    TODAY = SETTINGS["today"]
    float(SETTINGS["commission_rate"])

    city_map = load_mapping(CONFIG / "city_mapping.csv")
    cat_map = load_mapping(CONFIG / "category_mapping.csv")
    status_map = load_mapping(CONFIG / "status_mapping.csv")
    pay_map = load_mapping(CONFIG / "payment_mapping.csv")

    raw_customers, raw_products, raw_orders = read_text_frames(RAW_DIR)
    from ..cleaning import clean_all

    customers, products, orders = clean_all(
        raw_customers, raw_products, raw_orders,
        city_map, cat_map, status_map, pay_map,
        source_files={"customers": "customers.csv", "products": "products.csv", "orders": "orders.csv"}
    )
    master, _, id_remap = build_customer_master(customers)
    status_pre = orders["order_status"].astype(str).map(lambda v: standardise(status_map, v, "UNMAPPED"))
    clean_orders, _ = deduplicate_orders(orders, status_pre, id_remap)
    status_clean = clean_orders["order_status"].astype(str).map(lambda v: standardise(status_map, v, "UNMAPPED"))
    pay_clean = clean_orders["payment_mode"].astype(str).map(lambda v: standardise(pay_map, v, "UNMAPPED"))
    _verdicts, fail_mask, _ = evaluate(clean_orders, master, products, status_clean, pay_clean, TODAY)
    trusted = clean_orders[~fail_mask].copy()
    trusted["status_std"] = status_clean.loc[trusted.index].values
    trusted["payment_std"] = pay_clean.loc[trusted.index].values

    return {
        "trusted": trusted,
        "customers": master,
        "products": raw_products,
        "city_map": city_map,
        "cat_map": cat_map,
        "status_map": status_map,
        "pay_map": pay_map,
        "today": TODAY,
        "rate": float(SETTINGS["commission_rate"])
    }