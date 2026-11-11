"""Segment 4 answers (Q30-Q39): across the three extracts."""

import pandas as pd

from ..dimensions import enrich_dimensions
from ..line_value import row_line_value
from ..normalise import norm_id
from ..validation_rules import (
    _r01_customer_exists,
    _r02_product_exists,
    _r03_signup_before_order,
    _r06_valid_price,
)


def _settings():
    import json
    from pathlib import Path
    return json.loads((Path(__file__).resolve().parents[2] / "config"
                       / "settings.json").read_text(encoding="utf-8"))


def _line_sum(orders):
    total = 0.0
    for _, row in orders.iterrows():
        val = row_line_value(row)
        total += val if val is not None else 0.0
    return round(total, 2)


def q30_unmatched_customers(orders, customers, ctx):
    """Q30: match rules considered, counts under each, adopted rule + why."""
    frame = _r01_customer_exists(orders, ctx)
    exact = int((frame["failing_detail"] == "matched_exact").sum())
    rescued = int((frame["failing_detail"] == "matched_normalised").sum())
    unmatched = orders.loc[
        frame["failing_detail"] == "unmatched_after_normalisation",
        "customer_id"].astype(str).str.strip()
    top = unmatched.value_counts()
    result = {"exact_matched": exact,
              "normalised_matched": exact + rescued,
              "rescued_by_normalisation": rescued,
              "unmatched": len(unmatched),
              "top_unmatched_value": str(top.index[0]) if len(top) else "",
              "top_unmatched_count": int(top.iloc[0]) if len(top) else 0}
    explanation = (
        "Rules considered: (a) exact stripped match, (b) normalised match "
        "(trim, UPPER, strip spaces/dashes via normalise.norm_id). Adopted "
        "(b): case/dash variants are entry noise, and (b) rescues "
        f"{rescued} order lines without inventing customers. Unmatched "
        "after normalisation cannot be attributed to anyone.")
    return result, explanation


def q31_unmatched_products(orders, products, ctx):
    """Q31: typing variants vs nonexistent identifiers, reported separately."""
    frame = _r02_product_exists(orders, ctx)
    unmatched = orders.loc[
        frame["failing_detail"] == "unmatched_after_normalisation",
        "product_id"].astype(str).str.strip()
    master_norms = {norm_id(str(v)) for v in
                    products["product_id"].astype(str).str.strip()
                    if str(v).strip() != ""}
    typing, missing = [], []
    for value in unmatched:
        if value == "":
            missing.append(value)
            continue
        needle = norm_id(value)
        if any(needle in m or m in needle for m in master_norms if m and len(needle) >= 2):
            typing.append(value)
        else:
            missing.append(value)
    typing_s = pd.Series(typing)
    missing_s = pd.Series(missing)
    result = {"unmatched": len(unmatched),
              "typing_variants": len(typing_s),
              "nonexistent": len(missing_s),
              "top_typing": str(typing_s.value_counts().index[0])
              if len(typing_s) else "",
              "top_missing": str(missing_s.value_counts().index[0])
              if len(missing_s) else ""}
    explanation = (
        "Typing variant = unmatched non-empty value sharing a substring "
        "either way with a real normalised id (entry noise); nonexistent = "
        "empty or no such overlap (wrong catalogue or test ids). Kept "
        "separate because only the first group could ever be remapped "
        "without guessing.")
    return result, explanation


def q32_ghost_customer_value(orders, customers, ctx):
    """Q32: orders on unmatched customers and their total value."""
    frame = _r01_customer_exists(orders, ctx)
    ghost = orders.loc[
        frame["failing_detail"] == "unmatched_after_normalisation"].copy()
    value = _line_sum(ghost)
    result = {"ghost_customers": int(ghost["customer_id"].astype(str)
                                    .str.strip().nunique()),
              "ghost_orders": len(ghost),
              "ghost_value": value}
    explanation = (
        "Ghost-customer value is excluded from revenue: it cannot be "
        "attributed to anyone, so including it would let unknown buyers "
        "inflate city and customer answers. Tell the business the rupee "
        "amount sits in quarantine until the ids are resolved.")
    return result, explanation


def q33_never_ordered_products(orders, products, ctx):
    """Q33: products with no orders, with price/stock and evidence."""
    ordered = {norm_id(v) for v in
               orders["product_id"].astype(str).str.strip() if v.strip()}
    rows = []
    for _, row in products.iterrows():
        pid = str(row["product_id"]).strip()
        if norm_id(pid) in ordered or pid == "":
            continue
        price, stock = str(row["unit_price"]).strip(), \
            str(row["stock_qty"]).strip()
        try:
            usable_stock = float(stock) >= 0
        except ValueError:
            usable_stock = False
        if not usable_stock:
            verdict = "possibly inactive: no usable stock signal"
        elif price in ("", "NA"):
            verdict = "possibly mislabelled: no usable price"
        else:
            verdict = "unpopular or new: priced and stocked, never ordered"
        rows.append({"product_id": pid, "price": price, "stock": stock,
                     "evidence": verdict})
    result = pd.DataFrame(rows, columns=["product_id", "price", "stock",
                                         "evidence"]).sort_values(
        "product_id").reset_index(drop=True)
    explanation = (
        "Never-ordered means no normalised match in any order line. "
        "Verdicts use only observables (stock usability, price usability); "
        "inactivity vs unpopularity cannot be separated without intro dates, "
        "which the extracts lack.")
    return result, explanation


def q34_price_gap_per_product(orders, products, ctx):
    """Q34: catalogue vs paid gap per product, amount and percent."""
    from ..normalise import parse_discount_frac, parse_float
    cat = {}
    for _, row in products.iterrows():
        price = parse_float(str(row["unit_price"]))
        if str(row["product_id"]).strip() != "" and price is not None \
                and price > 0:
            cat[str(row["product_id"]).strip()] = price
    rows = []
    for pid, group in orders.groupby(orders["product_id"].astype(str)
                                     .str.strip(), sort=True):
        if pid == "" or pid not in cat:
            continue
        nets = []
        for _, row in group.iterrows():
            paid = parse_float(str(row["unit_price_paid"]))
            disc = parse_discount_frac(str(row["discount"])) \
                if str(row["discount"]).strip() != "" else 0.0
            if paid is not None and paid >= 0 and disc is not None:
                nets.append(paid * (1 - disc))
        if not nets:
            continue
        median_net = sorted(nets)[len(nets) // 2]
        gap = round(median_net - cat[pid], 2)
        gap_pct = round(gap / cat[pid] * 100, 1)
        signs = [1 if (n - cat[pid]) >= 0 else -1 for n in nets]
        systematic = abs(sum(signs)) / len(signs) >= 0.8 and abs(gap_pct) > 10
        rows.append({"product_id": pid, "catalogue_price": cat[pid],
                     "median_net_paid": round(median_net, 2),
                     "gap_amount": gap, "gap_pct": gap_pct,
                     "systematic": bool(systematic)})
    result = pd.DataFrame(rows).sort_values("product_id").reset_index(drop=True)
    explanation = (
        "Gap = median net paid minus catalogue price (median resists the "
        "500-quantity-style spikes; percent = gap / catalogue). Systematic "
        "means >= 80% of lines deviate the same way with median |gap| over "
        "10%: catalogue staleness or systematic discounting, not noise.")
    return result, explanation


def q35_price_closeness(orders, products, ctx):
    """Q35: how close paid is to catalogue; far defined by R06 tolerance."""
    frame = _r06_valid_price(orders, ctx)
    detail = frame["failing_detail"].value_counts().to_dict()
    result = {"within_tolerance": int(detail.get("within_tolerance", 0)),
              "outside_tolerance": int(detail.get("outside_tolerance", 0)),
              "non_positive_price": int(detail.get("non_positive_price", 0)),
              "unverifiable": int(detail.get(
                  "unverifiable:no_catalogue_price", 0))}
    explanation = (
        "Far means relative gap over 10% (R06_PRICE_TOLERANCE; 5% sits "
        "inside discount-rounding and catalogue-staleness noise). A far "
        "value can mean stacked discounts, a stale catalogue, bulk pricing "
        "or a data error — the rule flags, the business decides.")
    return result, explanation


def q36_fuzzy_attribution(orders, customers, ctx):
    """Q36: orders attributable only via normalised (inexact) identifiers."""
    frame = _r01_customer_exists(orders, ctx)
    only_fuzzy = orders.loc[frame["failing_detail"] == "matched_normalised"]
    share = round(_line_sum(only_fuzzy) / _line_sum(orders) * 100, 2) \
        if len(orders) else 0.0
    result = {"fuzzy_orders": len(only_fuzzy),
              "fuzzy_value_share_pct": share,
              "held_back": ["top customers", "cohorts", "tenure",
                            "customer concentration"]}
    explanation = (
        "Fuzzy-attributed rows carry the wrong spelling of who bought; any "
        "answer keyed by customer identity (top lists, cohorts, tenure, "
        "concentration) is held back for them, while city/month totals keep "
        "them — a wrong city is a smaller error than a wrong person.")
    return result, explanation


def q37_every_month_vs_one_month(orders, customers, ctx):
    """Q37: every-month vs one-month customers, by city and signup."""
    from ..normalise import parse_date
    def _ym(v):
        d = parse_date(str(v))
        return d.strftime("%Y-%m") if d else None
    ym_series = orders["order_date"].astype(str).apply(_ym)
    months = sorted({m for m in ym_series if pd.notna(m)})
    by_cust = orders.groupby(orders["customer_id"].astype(str).str.strip())[
        "order_date"].apply(lambda s: {m for m in s.astype(str).apply(_ym) if pd.notna(m)})
    every = [c for c, ms in by_cust.items() if set(months) <= ms]
    one = [c for c, ms in by_cust.items() if len(ms) == 1]

    def _describe(ids):
        sub = customers[customers["customer_id"].astype(str).str.strip()
                        .isin(ids)]
        cities = sub["city"].astype(str).str.strip().value_counts().to_dict()
        signs = sorted(sub["signup_date"].astype(str).str.strip())
        return {"n": len(ids), "cities": cities,
                "signup_min": signs[0] if signs else "",
                "signup_max": signs[-1] if signs else ""}

    unmatched = set()
    try:
        unmatched = set(orders.loc[
            _r01_customer_exists(
                orders, ctx)["failing_detail"] ==
            "unmatched_after_normalisation", "customer_id"]
            .astype(str).str.strip())
    except (KeyError, AttributeError):
        unmatched = set()
    one_ghost = len(set(one) & unmatched)
    result = {"months": months, "n_months": len(months),
              "every_month": _describe(every), "one_month": _describe(one),
              "one_month_unmatched": one_ghost}
    explanation = (
        "One-month customers are both: a real long tail (most buyers buy "
        f"once) and partly a data problem ({one_ghost} one-month ids match "
        "no customer). Every-month buyers are the reliable core; compare "
        "their cities and signup span before generalising.")
    return result, explanation


def q38_orders_before_signup(orders, customers, ctx):
    """Q38: orders predating signup; which side is likelier wrong."""
    frame = _r03_signup_before_order(orders, ctx)
    bad = orders.loc[frame["failing_detail"] == "order_before_signup"]
    future_signup = int((customers["signup_date"].astype(str).str.strip()
                         > "2026-10-11").sum())
    future_order = int((orders["order_date"].astype(str).str.strip()
                        > "2026-10-11").sum())
    result = {"orders": len(bad),
              "customers": int(bad["customer_id"].astype(str).str.strip()
                               .nunique()),
              "future_signups_in_master": future_signup,
              "future_orders": future_order}
    explanation = (
        "Signup dates reach past TODAY while most flagged orders sit in "
        "plausible past months, so the signup side is likelier wrong "
        "(default/placeholder future dates); order dates cluster credibly. "
        "Neither side is certain — R03 sets these rows aside either way.")
    return result, explanation


def q39_join_losses(orders, customers, products, ctx):
    """Q39: row counts kept by every join; which loss changes answers."""
    keep = []
    exact_c = orders["customer_id"].astype(str).str.strip().isin(
        set(customers["customer_id"].astype(str).str.strip()))
    keep.append({"join": "orders-customers (exact)", "before": len(orders),
                 "kept": int(exact_c.sum())})
    normed = {norm_id(v)
              for v in customers["customer_id"].astype(str).str.strip()
              if v.strip()}
    keep_c = orders["customer_id"].astype(str).str.strip().apply(
        lambda v: norm_id(v) in normed)
    keep.append({"join": "orders-customers (normalised)", "before": len(orders),
                 "kept": int(keep_c.sum())})
    exact_p = orders["product_id"].astype(str).str.strip().isin(
        set(products["product_id"].astype(str).str.strip()))
    keep.append({"join": "orders-products (exact)", "before": len(orders),
                 "kept": int(exact_p.sum())})
    prod_normed = {norm_id(w)
                   for w in products["product_id"].astype(str).str.strip()
                   if w.strip()}
    keep.append({"join": "orders-products (normalised)", "before": len(orders),
                 "kept": int(sum(
                     1 for v in orders["product_id"].astype(str).str.strip()
                     if norm_id(v) in prod_normed))})
    dims = enrich_dimensions(orders, customers, products, ctx)
    keep.append({"join": "orders-city attribution", "before": len(orders),
                 "kept": int((dims["city"] != "UNMATCHED").sum())})
    result = pd.DataFrame(keep, columns=["join", "before", "kept"])
    result["dropped"] = result["before"] - result["kept"]
    explanation = (
        "The customer join drops the most rows, and it changes business "
        "answers: dropped rows vanish from city and customer cuts (see the "
        "reconcile join log), so city/customer answers exclude them by "
        "construction. Matches reconcile.join_log row counts.")
    return result, explanation
