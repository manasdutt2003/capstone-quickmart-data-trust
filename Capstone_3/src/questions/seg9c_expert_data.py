"""Segment 9 answers, part C (Q87-Q94, Q110-Q112): expert SQL on the data.

Same population and tie rules as parts A/B; see docs/answers_segment8_9.md.
completed = status_std Delivered AND line_value NOT NULL; trusted =
lenient set any-status where the question needs sequencing/identity.
"""

import pandas as pd

from .seg6_advanced_sql import _delivered, _enriched

_VALID_DATE = r"^\d{4}-\d{2}-\d{2}$"


def _valid_dates(base):
    return base[base["order_date"].astype(str).str.match(
        _VALID_DATE, na=False)].copy()


def _root():
    from pathlib import Path
    return Path(__file__).resolve().parents[2]


def q87_grouping_sets(trusted, customers, products, ctx):
    """Q87: value by city+category with city/categry/grand subtotals."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    cell = base.groupby(["city_std", "category_std"])["line_value"].sum()
    by_city = base.groupby("city_std")["line_value"].sum()
    by_cat = base.groupby("category_std")["line_value"].sum()
    grand = float(base["line_value"].sum())
    rows = []
    for (city, cat), v in cell.items():
        rows.append({"city_std": city, "category_std": cat,
                     "total_value": round(float(v), 2), "kind": "cell"})
    for city, v in by_city.items():
        rows.append({"city_std": city, "category_std": "SUBTOTAL",
                     "total_value": round(float(v), 2), "kind": "city"})
    for cat, v in by_cat.items():
        rows.append({"city_std": "SUBTOTAL", "category_std": cat,
                     "total_value": round(float(v), 2), "kind": "category"})
    rows.append({"city_std": "GRAND", "category_std": "GRAND",
                 "total_value": round(grand, 2), "kind": "grand"})
    result = pd.DataFrame(rows)
    ok = (abs(by_city.sum() - grand) < 0.01
          and abs(by_cat.sum() - grand) < 0.01)
    explanation = (
        "GROUPING() = 1 marks subtotal rows, 0 marks true data (a real "
        "NULL city would show 0). City subtotals, category subtotals and "
        f"grand ({grand:.2f}) reconcile: {bool(ok)}.")
    return {"table": result, "grand": round(grand, 2),
            "cells": len(cell), "ok": bool(ok)}, explanation


def q88_median_monthly_qty(trusted, customers, products, ctx):
    """Q88: products above their own median monthly qty every active month."""
    base = _valid_dates(_delivered(_enriched(trusted, customers, products,
                                             ctx)))
    base["q"] = pd.to_numeric(base["quantity"], errors="coerce").fillna(0)
    base["ym"] = base["order_date"].astype(str).str[:7]
    mc = (base.groupby(["product_id", "ym"])["q"].sum()
          .reset_index(name="qty"))
    out = []
    for pid, grp in mc.groupby("product_id"):
        med = float(grp["qty"].median())
        out.append({"product_id": pid, "median_monthly_qty": round(med, 2),
                    "all_months_above": bool((grp["qty"] > med).all())})
    result = pd.DataFrame(out).sort_values("product_id").reset_index(
        drop=True)
    explanation = (
        "Median is per-product over its own active months (correlated "
        "subquery / window median). A global median would compare bulk "
        "staples against slow movers and flip the list.")
    return {"table": result, "n": int(result["all_months_above"].sum())}, \
        explanation


def q89_range_90d(trusted, customers, products, ctx):
    """Q89: rolling 90-day distinct customers per city (RANGE + exact)."""
    base = _valid_dates(_enriched(trusted, customers, products, ctx))
    base["d"] = pd.to_datetime(base["order_date"])
    dedup = base.drop_duplicates(
        ["city_std", "customer_id", "order_date"]).copy()
    dedup = dedup.sort_values(["city_std", "d"]).reset_index(drop=True)
    out = []
    for city, grp in dedup.groupby("city_std"):
        dates = sorted(grp["d"].unique())
        for d in dates:
            lo = d - pd.Timedelta(days=89)
            window = grp[(grp["d"] >= lo) & (grp["d"] <= d)]
            row_count = len(window)
            distinct = int(window["customer_id"].nunique())
            out.append({"city_std": city, "date": d.date().isoformat(),
                        "distinct_customers": distinct,
                        "range_row_count": row_count})
    result = pd.DataFrame(out).sort_values(
        ["city_std", "date"]).reset_index(drop=True)
    explanation = (
        "RANGE (89 days PRECEDING..CURRENT ROW) frames the right day span "
        "but COUNT(*) counts rows, not customers; DISTINCT is exact via "
        "the deduped set. ROWS would count a fixed number of rows "
        "regardless of date gaps and differs on sparse cities.")
    return result, explanation


def q90_cohort(trusted, customers, products, ctx):
    """Q90: first-order-month cohorts, share ordering in next 6 months."""
    base = _valid_dates(_enriched(trusted, customers, products, ctx))
    base["ym"] = base["order_date"].astype(str).str[:7]
    first = base.groupby("customer_id")["ym"].min().rename("cohort")
    base = base.join(first, on="customer_id")
    months = sorted(base["ym"].unique())
    idx = {m: i for i, m in enumerate(months)}
    base["offset"] = base["ym"].map(idx) - base["cohort"].map(idx)
    piv = (base[base["offset"].between(0, 6)]
           .groupby(["cohort", "offset"])["customer_id"].nunique()
           .reset_index(name="n"))
    size = base.groupby("cohort")["customer_id"].nunique().rename("size")
    piv = piv.join(size, on="cohort")
    piv["share_pct"] = round(piv["n"] / piv["size"] * 100, 2)
    result = piv.sort_values(["cohort", "offset"]).reset_index(drop=True)
    explanation = (
        "Cohorts whose +6 window passes the data end show fewer offsets "
        "(right-censored, not zero); shares divide by the full cohort.")
    return result, explanation


def q91_p95_flags(trusted, customers, products, ctx):
    """Q91: orders above city p95 delivery_days; city vs global flags."""
    base = _enriched(trusted, customers, products, ctx)
    mask = base["delivery_days"].astype(str).str.match(
        r"^\d+(\.\d+)?$", na=False)
    base = base.assign(
        days=pd.to_numeric(base["delivery_days"].where(mask),
                           errors="coerce"))
    dated = base[base["days"].notna()].copy()
    city_p95 = dated.groupby("city_std")["days"].quantile(
        0.95, interpolation="linear")
    glob_p95 = float(dated["days"].quantile(0.95, interpolation="linear"))
    dated["city_p95"] = dated["city_std"].map(city_p95)
    dated["flag_city"] = dated["days"] > dated["city_p95"]
    dated["flag_global"] = dated["days"] > glob_p95
    changed = int((dated["flag_city"] != dated["flag_global"]).sum())
    result = dated[dated["flag_city"]].sort_values(
        ["order_id"]).reset_index(drop=True)
    result = result[["order_id", "city_std", "days", "city_p95"]]
    explanation = (
        f"City p95 flags {int(dated['flag_city'].sum())} orders; global "
        f"p95 ({glob_p95:.1f}d) flags {int(dated['flag_global'].sum())}; "
        f"{changed} orders change. A delivery manager uses city p95 "
        "(local traffic/warehouse reality), not the global bar.")
    return {"flagged": result, "n_city": int(dated["flag_city"].sum()),
            "n_global": int(dated["flag_global"].sum()),
            "n_changed": changed}, explanation


def q92_dup_email_pairs(trusted, customers, products, ctx):
    """Q92: customer pairs sharing normalised email; differing columns."""
    _ = trusted
    cust = customers.copy()
    cust["email_n"] = cust["email"].astype(str).str.strip().str.lower()
    cust = cust[cust["email_n"] != ""]
    merged = cust.merge(cust, on="email_n", suffixes=("_a", "_b"))
    pairs = merged[merged["customer_id_a"].astype(str)
                   < merged["customer_id_b"].astype(str)]
    rows = []
    for _, r in pairs.iterrows():
        diffs = [c for c in ("customer_name", "city", "phone",
                             "signup_date")
                 if str(r[c + "_a"]).strip() != str(r[c + "_b"]).strip()]
        rows.append({"customer_a": r["customer_id_a"],
                     "customer_b": r["customer_id_b"],
                     "email": r["email_n"],
                     "differs_on": ",".join(diffs),
                     "same_phone": bool(str(r["phone_a"]).strip()
                                        and str(r["phone_a"]).strip()
                                        == str(r["phone_b"]).strip()),
                     "same_email_diff_phone": bool(
                         str(r["phone_a"]).strip()
                         != str(r["phone_b"]).strip())})
    result = pd.DataFrame(rows, columns=["customer_a", "customer_b",
                                           "email", "differs_on",
                                           "same_phone",
                                           "same_email_diff_phone"]
                          ).sort_values(
        ["customer_a", "customer_b"]).reset_index(drop=True)
    same_phone = result[result["same_phone"]]
    explanation = (
        f"{len(result)} pairs share an email; "
        f"{len(same_phone)} share phone too. Same phone + different "
        "emails is not merge-safe: phones are shared/reused (family, "
        "typos, placeholders) and say nothing about identity without "
        "name+signup agreement.")
    return result, explanation


def q93_180d_categories(trusted, customers, products, ctx):
    """Q93: distinct categories per customer in last 180 data days."""
    base = _valid_dates(_enriched(trusted, customers, products, ctx))
    base["d"] = pd.to_datetime(base["order_date"])
    end = base["d"].max()
    start = end - pd.Timedelta(days=180)
    window = base[(base["d"] >= start) & (base["d"] <= end)]
    out = (window.groupby("customer_id")["category_std"].nunique()
           .reset_index(name="n_categories"))
    out = out.sort_values(["n_categories", "customer_id"],
                          ascending=[False, True]).reset_index(drop=True)
    explanation = (
        f"Window [{start.date()}, {end.date()}] inclusive both ends; "
        "boundary-day orders count.")
    return {"table": out, "start": str(start.date()),
            "end": str(end.date())}, explanation


def q94_herfindahl(trusted, customers, products, ctx):
    """Q94: Herfindahl of category shares per city; drop-smallest effect."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    grp = (base.groupby(["city_std", "category_std"])["line_value"]
           .sum().reset_index(name="v"))
    tot = grp.groupby("city_std")["v"].sum().rename("tot")
    grp = grp.join(tot, on="city_std")
    grp["share"] = grp["v"] / grp["tot"]
    herf = grp.groupby("city_std")["share"].apply(
        lambda s: round(float((s ** 2).sum()), 4)).reset_index(name="hhi")
    smallest = grp.groupby("city_std")["v"].sum().idxmin()
    out = herf.copy()
    out["note"] = ""
    out.loc[out["city_std"] == smallest, "note"] = "smallest_city"
    result = out.sort_values("city_std").reset_index(drop=True)
    explanation = (
        "HHI = sum of squared category shares (two-level agg). Dropping "
        f"the smallest city ({smallest}) changes no other city's HHI "
        "(each is computed within-city); it only removes its row.")
    return result, explanation


def q110_id_mismatches(trusted, customers, products, ctx):
    """Q110: normalised ids in one source only, split by direction."""
    _ = trusted, ctx
    clean = pd.read_csv(
        _root() / "data" / "clean_orders.csv", dtype=str,
        keep_default_na=False, encoding="utf-8")
    norm = lambda s: s.astype(str).str.strip().str.lower()
    o_ids = set(norm(clean["customer_id"])) - {""}
    c_ids = set(norm(customers["customer_id"])) - {""}
    only_orders = sorted(o_ids - c_ids)
    only_customers = sorted(c_ids - o_ids)
    rows = ([{"customer_id": c, "direction": "orders_only"}
             for c in only_orders]
            + [{"customer_id": c, "direction": "customers_only"}
               for c in only_customers])
    result = pd.DataFrame(rows).sort_values(
        ["direction", "customer_id"]).reset_index(drop=True)
    explanation = (
        "orders_only ids have no city (city lives in customers) so "
        "city-level answers silently drop them; customers_only ids are "
        "registered but never ordered.")
    return result, explanation


def q111_share_shift(trusted, customers, products, ctx):
    """Q111: categories whose order share moved >5pp between halves."""
    base = _valid_dates(_delivered(_enriched(trusted, customers, products,
                                             ctx)))
    base["d"] = pd.to_datetime(base["order_date"])
    lo, hi = base["d"].min(), base["d"].max()
    mid = lo + (hi - lo) / 2
    first = base[base["d"] < mid]
    second = base[base["d"] >= mid]
    s1 = first.groupby("category_std").size() / len(first) * 100
    s2 = second.groupby("category_std").size() / len(second) * 100
    cats = sorted(set(s1.index) | set(s2.index))
    rows = [{"category_std": c,
             "share_first_pct": round(float(s1.get(c, 0.0)), 2),
             "share_second_pct": round(float(s2.get(c, 0.0)), 2),
             "shift_pp": round(float(s2.get(c, 0.0) - s1.get(c, 0.0)), 2)}
            for c in cats]
    result = pd.DataFrame(rows)
    big = result[result["shift_pp"].abs() > 5].sort_values(
        "shift_pp", ascending=False).reset_index(drop=True)
    explanation = (
        f"Range split at midpoint {mid.date()} (< mid vs >= mid); the "
        "second half takes the extra day on odd spans. >5pp movers: "
        f"{len(big)}.")
    return {"all": result, "movers": big}, explanation


def q112_pairs_top5(trusted, customers, products, ctx):
    """Q112: top-5 product pairs same customer+date (canonical order)."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    base = base.drop_duplicates(["customer_id", "order_date", "product_id"])
    merged = base.merge(base, on=["customer_id", "order_date"],
                        suffixes=("_a", "_b"))
    pairs = merged[merged["product_id_a"].astype(str)
                   < merged["product_id_b"].astype(str)]
    cnt = (pairs.groupby(["product_id_a", "product_id_b"]).size()
           .reset_index(name="n").sort_values(
               ["n", "product_id_a", "product_id_b"],
               ascending=[False, True, True]).head(5).reset_index(drop=True))
    result = cnt
    explanation = (
        "Canonical ordering (product_a < product_b) counts each unordered "
        "pair once; without it every pair double-counts (a,b)+(b,a).")
    return result, explanation
