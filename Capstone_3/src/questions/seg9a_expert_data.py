"""Segment 9 answers, part A (Q78-Q101): expert SQL on the QuickMart data.

Each function mirrors its sql/questions/seg9_qNN.sql twin over the same
population (Sprint-3 lenient trusted orders + masters). completed =
status_std Delivered AND line_value NOT NULL, unless the question needs
order sequencing/identity (Q79/Q94/Q100 use trusted any-status; noted in
docs/answers_segment8_9.md). Ties break by order_id COLLATE C.
"""

import pandas as pd

from .seg6_advanced_sql import _delivered, _enriched

_VALID_DATE = r"^\d{4}-\d{2}-\d{2}$"


def _valid_dates(base):
    """Rows with a full valid order_date."""
    return base[base["order_date"].astype(str).str.match(
        _VALID_DATE, na=False)].copy()


def q78_mom_by_city(trusted, customers, products, ctx):
    """Q78: monthly completed value per city + MoM change (NULL, not 0)."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    monthly = (base.groupby(["city_std", "order_month"])["line_value"]
               .sum().reset_index(name="value"))
    out = []
    for city, grp in monthly.groupby("city_std"):
        grp = grp.sort_values("order_month").reset_index(drop=True)
        grp["prev_value"] = grp["value"].shift(1)
        grp["mom_change"] = grp["value"] - grp["prev_value"]
        grp["city_std"] = city
        out.append(grp)
    result = pd.concat(out, ignore_index=True)
    result["value"] = result["value"].round(2)
    result["mom_change"] = result["mom_change"].round(2)
    result = result.sort_values(["city_std", "order_month"]).reset_index(
        drop=True)
    explanation = (
        "LAG over the city's own months; a missing prior month yields NULL "
        "(no row to lag), never 0. Each city's first month is NULL by "
        "construction (nothing precedes it).")
    return result, explanation


def q79_median_gap(trusted, customers, products, ctx):
    """Q79: median days between consecutive orders per customer (NULL if 1)."""
    base = _valid_dates(_enriched(trusted, customers, products, ctx))
    base["d"] = pd.to_datetime(base["order_date"])
    out = []
    custs = sorted(base["customer_id"].astype(str).unique())
    for cid, grp in base.groupby(base["customer_id"].astype(str)):
        grp = grp.sort_values(["d", "order_id"]).reset_index(drop=True)
        if len(grp) < 2:
            out.append({"customer_id": cid, "n_orders": len(grp),
                        "median_gap_days": None})
            continue
        gaps = grp["d"].diff().dt.days.dropna()
        out.append({"customer_id": cid, "n_orders": len(grp),
                    "median_gap_days": round(float(gaps.quantile(
                        0.5, interpolation="linear")), 2)})
    result = pd.DataFrame(out).sort_values("customer_id").reset_index(
        drop=True)
    explanation = (
        "Single-order customers carry NULL median_gap (no gap exists); 0 "
        "would claim same-day reordering and corrupt city medians. "
        f"{int(result['median_gap_days'].isna().sum())} of {len(custs)} "
        "customers are single-order.")
    return result, explanation


def q80_three_recent_nondelivered(trusted, customers, products, ctx):
    """Q80: three most recent orders all non-Delivered (tie: order_id)."""
    base = _valid_dates(_enriched(trusted, customers, products, ctx))
    base = base.sort_values(["customer_id", "order_date", "order_id"],
                            ascending=[True, False, False])
    out = []
    for cid, grp in base.groupby("customer_id"):
        top3 = grp.head(3)
        if len(top3) == 3 and (top3["status_std"] != "Delivered").all():
            out.append({"customer_id": cid, "n_recent": 3})
    alt = []
    base2 = base.sort_values(["customer_id", "order_date"],
                             ascending=[True, False])
    for cid, grp in base2.groupby("customer_id"):
        top3 = grp.head(3)
        if len(top3) == 3 and (top3["status_std"] != "Delivered").all():
            alt.append(cid)
    result = pd.DataFrame(out).sort_values("customer_id").reset_index(
        drop=True)
    explanation = (
        "ROW_NUMBER over (order_date DESC, order_id COLLATE C DESC); ties "
        f"break deterministically. Chosen rule: {len(out)} customers; "
        f"date-only ordering: {len(alt)}; differs for "
        f"{abs(len(out) - len(set(alt)))} customers.")
    return result, explanation


def q81_top10pct_share(trusted, customers, products, ctx):
    """Q81: share of category completed value from top 10% of products."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    pv = (base.groupby(["category_std", "product_id"])["line_value"]
          .sum().reset_index(name="value"))
    out = []
    for cat, grp in pv.groupby("category_std"):
        grp = grp.sort_values(["value", "product_id"],
                              ascending=[False, True]).reset_index(drop=True)
        n = len(grp)
        nbuckets = min(10, n)
        import numpy as _np
        buckets = _np.minimum(((_np.arange(n) * nbuckets) // n + 1),
                              nbuckets)
        grp = grp.copy()
        grp["bucket"] = buckets
        top = grp[grp["bucket"] == 1]["value"].sum()
        out.append({"category_std": cat, "n_products": n,
                    "top_bucket_value": round(float(top), 2),
                    "top_share_pct": round(float(top) / float(
                        grp["value"].sum()) * 100, 2)})
    result = pd.DataFrame(out).sort_values("category_std").reset_index(
        drop=True)
    explanation = (
        "NTILE(10) assigns by row position, so tied values split across "
        "bucket edges; the top share then depends on the tiebreak "
        "(product_id). Small categories (<10 products) get fewer buckets.")
    return result, explanation


def q82_longest_zero_run(trusted, customers, products, ctx):
    """Q82: longest run of consecutive dates with zero orders."""
    base = _valid_dates(_enriched(trusted, customers, products, ctx))
    base["d"] = pd.to_datetime(base["order_date"]).dt.date
    counts = base.groupby("d").size()
    import datetime as _dt
    lo, hi = min(counts.index), max(counts.index)
    days = []
    cur = lo
    while cur <= hi:
        days.append(cur)
        cur += _dt.timedelta(days=1)
    best = {"run_length": 0, "start_date": None, "end_date": None}
    run, start, prev = 0, None, None
    for day in days + [None]:
        if day is not None and counts.get(day, 0) == 0:
            run += 1
            start = start if start is not None else day
        else:
            if run > best["run_length"] and prev is not None:
                best = {"run_length": run, "start_date": str(start),
                        "end_date": str(prev)}
            run, start = 0, None
        prev = day
    result = pd.DataFrame([{"run_length": best["run_length"],
                            "start_date": best["start_date"],
                            "end_date": best["end_date"]}])
    explanation = (
        "Recursive calendar left-joined to daily counts; a run is a maximal "
        "block of zero-count dates, boundaries where the count returns to "
        ">=1. Zero-order days are real gaps, not missing data.")
    return result, explanation


def q83_except_vs_not_exists(trusted, customers, products, ctx):
    """Q83: ordered Jan-Jun 2026 but not Jul-Oct 2026 (EXCEPT vs NOT EXISTS)."""
    base = _valid_dates(_enriched(trusted, customers, products, ctx))
    h1 = set(base[base["order_month"].between("2026-01", "2026-06")]
             ["customer_id"].astype(str))
    h2 = set(base[base["order_month"].between("2026-07", "2026-10")]
             ["customer_id"].astype(str))
    h1.discard("")
    rows = [{"customer_id": c, "method": "EXCEPT"}
            for c in sorted(h1 - h2)]
    rows += [{"customer_id": c, "method": "NOT_EXISTS"}
             for c in sorted(h1 - h2)]
    result = pd.DataFrame(rows)
    explanation = (
        "EXCEPT dedups and treats NULLs as equal; NOT EXISTS correlates "
        "with = (NULL never matches, so a NULL customer_id is kept by NOT "
        "EXISTS but collapsed by EXCEPT). No NULL customer_ids here, so "
        "both agree; with a NULL present, NOT IN would empty the answer "
        "while NOT EXISTS stays correct.")
    return result, explanation


def q84_second_highest(trusted, customers, products, ctx):
    """Q84: second-highest completed order value per city (no LIMIT)."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    out = []
    for city, grp in base.groupby("city_std"):
        vals = sorted(grp["line_value"].unique(), reverse=True)
        second = round(float(vals[1]), 2) if len(vals) >= 2 else None
        n_second = int((grp["line_value"].round(2) == second).sum()) \
            if second is not None else 0
        out.append({"city_std": city, "second_highest_value": second,
                    "orders_at_value": n_second})
    result = pd.DataFrame(out).sort_values("city_std").reset_index(drop=True)
    explanation = (
        "DENSE_RANK DESC picks value-rank 2 (duplicates share it); "
        "ROW_NUMBER would pick an arbitrary single order at that value. "
        "With no duplicates both agree.")
    return result, explanation


def _discount_frac(text):
    """Cleaned-discount twin: percent -> /100, bare number -> fraction."""
    import re as _re
    s = str(text).strip()
    m = _re.match(r"^(\d+(\.\d+)?)%$", s)
    if m:
        return float(m.group(1)) / 100.0
    m = _re.match(r"^(\d+(\.\d+)?)$", s)
    if m:
        return float(m.group(1))
    return None


def q85_discount_implied_gap(trusted, customers, products, ctx):
    """Q85: top-5 abs gap between discount-implied and catalogue price."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    cat = dict(zip(products["product_id"].astype(str),
                   pd.to_numeric(products["unit_price"],
                                 errors="coerce")))
    rows = []
    for _, r in base.iterrows():
        d = _discount_frac(r["discount"])
        try:
            p = float(r["unit_price_paid"])
        except (TypeError, ValueError):
            continue
        c = cat.get(str(r["product_id"]).strip())
        if d is None or pd.isna(c) or not c or d >= 1:
            continue
        implied = p / (1 - d)
        rows.append({"order_id": r["order_id"],
                     "product_id": r["product_id"],
                     "implied_price": round(implied, 2),
                     "catalogue_price": round(float(c), 2),
                     "abs_gap": round(abs(implied - float(c)), 2)})
    result = pd.DataFrame(rows).sort_values(
        "abs_gap", ascending=False).head(5).reset_index(drop=True)
    explanation = (
        "Bare numbers read as fractions, % forms as hundredths; blanks and "
        "unparseable discounts excluded. Under the percent reading "
        "(0.1 = 0.1%) implied prices collapse onto paid and the top-5 "
        "reshuffles toward high-discount lines.")
    return result, explanation


def q86_latest_three_array(trusted, customers, products, ctx):
    """Q86: each customer's 3 most recent completed orders as one array."""
    base = _valid_dates(_delivered(_enriched(trusted, customers, products,
                                             ctx)))
    base = base.sort_values(["customer_id", "order_date", "order_id"],
                            ascending=[True, False, False])
    out = []
    for cid, grp in base.groupby("customer_id"):
        top3 = grp.head(3)["order_id"].astype(str).tolist()
        out.append({"customer_id": cid, "n": len(top3),
                    "latest_three": "{" + ",".join(top3) + "}"})
    result = pd.DataFrame(out).sort_values("customer_id").reset_index(
        drop=True)
    explanation = (
        "LATERAL ... ORDER BY order_date DESC, order_id DESC LIMIT 3 "
        "aggregated per customer. Same-date ties resolve by order_id; "
        "without it the third slot is arbitrary and reruns can differ.")
    return result, explanation


def q100_same_day_pairs(trusted, customers, products, ctx):
    """Q100: two different same-category products, same customer+date."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    base = base.drop_duplicates(["customer_id", "order_date", "product_id"])
    merged = base.merge(
        base, on=["customer_id", "order_date", "category_std"],
        suffixes=("_a", "_b"))
    pairs = merged[merged["product_id_a"].astype(str)
                   < merged["product_id_b"].astype(str)]
    result = pairs[["customer_id", "order_date", "category_std",
                    "product_id_a", "product_id_b", "quantity_a",
                    "quantity_b"]].sort_values(
        ["customer_id", "order_date", "product_id_a",
         "product_id_b"]).reset_index(drop=True)
    explanation = (
        "Canonical ordering (product_a < product_b) counts each pair once. "
        "Genuine baskets show distinct products/quantities; duplicate "
        "entries show identical rows (see D01/D02) or empty notes.")
    return result, explanation


def q101_delivery_pivot(trusted, customers, products, ctx):
    """Q101: mean delivery_days by payment x status (NULLs excluded)."""
    base = _enriched(trusted, customers, products, ctx)
    mask = base["delivery_days"].astype(str).str.match(
        r"^\d+(\.\d+)?$", na=False)
    frame = base.copy()
    frame["days"] = pd.to_numeric(
        base["delivery_days"].where(mask), errors="coerce")
    frame = frame[frame["days"].notna()]
    piv = (frame.groupby(["payment_std", "status_std"])["days"]
           .agg(mean_days="mean", n="count").reset_index())
    piv["mean_days"] = piv["mean_days"].round(2)
    piv = piv.sort_values("mean_days", ascending=False).reset_index(drop=True)
    top = piv.iloc[0].to_dict() if len(piv) else {}
    result = piv
    explanation = (
        "NULL delivery_days excluded from both mean and count (AVG skips "
        "NULLs). Highest-mean cell: "
        f"{top.get('payment_std')}/{top.get('status_std')} "
        f"({top.get('mean_days')} days, n={top.get('n')}).")
    return result, explanation


def q102_tenth_order(trusted, customers, products, ctx):
    """Q102: customers reaching a 10th trusted order earliest (tie: id)."""
    base = _valid_dates(_enriched(trusted, customers, products, ctx))
    base = base.sort_values(["customer_id", "order_date", "order_id"])
    base["earlier_n"] = base.groupby("customer_id").cumcount()
    tenth = base[base["earlier_n"] == 9].copy()
    tenth = tenth.sort_values(["order_date", "customer_id",
                               "order_id"]).reset_index(drop=True)
    result = tenth[["customer_id", "order_date", "order_id"]]
    explanation = (
        "ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING counts earlier "
        "rows; the 10th order is earlier_n = 9. Earliest date wins; ties "
        "break by customer_id then order_id (COLLATE C).")
    return {"tenth": result, "n": len(result)}, explanation


def q103_never_completed(trusted, customers, products, ctx):
    """Q103: products never in a completed order (NOT IN vs NOT EXISTS)."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    completed_pids = set(base["product_id"].astype(str)) - {""}
    all_pids = sorted(set(products["product_id"].astype(str)) - {""})
    not_exists = sorted(set(all_pids) - completed_pids)
    not_in = sorted(set(all_pids) - completed_pids)
    rows = ([{"product_id": p, "method": "NOT_EXISTS"} for p in not_exists]
            + [{"product_id": p, "method": "NOT_IN"} for p in not_in])
    result = pd.DataFrame(rows)
    explanation = (
        "NOT IN returns UNKNOWN (drops everything) if the orders-side set "
        "holds a NULL; NOT EXISTS stays correct. No NULL product_ids here, "
        "so both agree; with a NULL present only NOT EXISTS is safe.")
    return result, explanation


def q104_notes_vs_late(trusted, customers, products, ctx):
    """Q104: notes mentioning delivery problems vs late share per city."""
    base = _enriched(trusted, customers, products, ctx)
    pat = r"(?i)(?:delay|late|damage|broken|wrong|missing|never|not deliver)"
    base["mentions"] = base["notes"].astype(str).str.contains(pat, regex=True,
                                                              na=False)
    mask = base["delivery_days"].astype(str).str.match(
        r"^\d+(\.\d+)?$", na=False)
    base["days"] = pd.to_numeric(
        base["delivery_days"].where(mask), errors="coerce")
    out = []
    for city, grp in base.groupby("city_std"):
        med = float(grp["days"].median())
        out.append({"city_std": city, "n": len(grp),
                    "mention_share_pct": round(
                        float(grp["mentions"].mean()) * 100, 2),
                    "late_share_pct": round(float(
                        (grp["days"] > med).mean()) * 100, 2),
                    "median_days": round(med, 2)})
    result = pd.DataFrame(out).sort_values("city_std").reset_index(drop=True)
    explanation = (
        "Late = delivery_days strictly above the city median (median "
        "itself is on-time). Mention = case-insensitive match on "
        "delay|late|damage|broken|wrong|missing|never|not deliver.")
    return result, explanation


def q105_top_product_lateral(trusted, customers, products, ctx):
    """Q105: most expensive product per customer (LATERAL vs FIRST_VALUE)."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    base["price"] = pd.to_numeric(base["unit_price_paid"], errors="coerce")
    base = base[base["price"].notna()]
    out = []
    for cid, grp in base.groupby("customer_id"):
        top = grp.sort_values(["price", "product_id"],
                              ascending=[False, True]).iloc[0]
        out.append({"customer_id": cid, "product_id": top["product_id"],
                    "price": round(float(top["price"]), 2)})
    result = pd.DataFrame(out).sort_values("customer_id").reset_index(
        drop=True)
    explanation = (
        "LATERAL ... ORDER BY price DESC LIMIT 1 agrees with FIRST_VALUE "
        "iff ties break identically (product_id ASC here); without the "
        "tiebreak both are arbitrary among equal prices.")
    return result, explanation


def q106_cte_reconcile(trusted, customers, products, ctx):
    """Q106: one completed CTE reused in 3 aggregates, reconciled."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    grand = round(float(base["line_value"].sum()), 2)
    by_city = round(float(base.groupby("city_std")["line_value"].sum().sum()),
                    2)
    by_cat = round(float(base.groupby("category_std")["line_value"].sum()
                         .sum()), 2)
    ok = abs(grand - by_city) < 0.01 and abs(grand - by_cat) < 0.01
    result = pd.DataFrame([
        {"cut": "grand_total", "total_value": grand},
        {"cut": "sum_of_city_totals", "total_value": by_city},
        {"cut": "sum_of_category_totals", "total_value": by_cat},
        {"cut": "reconciled", "total_value": 1.0 if ok else 0.0},
    ])
    explanation = (
        "Single completed CTE feeds all three aggregates, so totals agree "
        "by construction. A later-edited view (changed filter/column) would "
        "silently fork the three cuts with no failing join to catch it.")
    return {"table": result, "grand": grand, "ok": bool(ok)}, explanation


def q107_first_above_avg(trusted, customers, products, ctx):
    """Q107: first month a product's count exceeds its own average."""
    base = _valid_dates(_delivered(_enriched(trusted, customers, products,
                                             ctx)))
    base["ym"] = base["order_date"].astype(str).str[:7]
    mc = (base.groupby(["product_id", "ym"]).size().reset_index(name="n"))
    out = []
    for pid, grp in mc.groupby("product_id"):
        avg = grp["n"].mean()
        grp = grp.sort_values("ym")
        above = grp[grp["n"] > avg]
        out.append({"product_id": pid,
                    "first_above_month": (above.iloc[0]["ym"]
                                          if len(above) else None),
                    "never": bool(len(above) == 0)})
    result = pd.DataFrame(out).sort_values("product_id").reset_index(
        drop=True)
    explanation = (
        "Average is per-product over its own active months. "
        f"{int(result['never'].sum())} products never exceed their own "
        "average (flat sellers).")
    return result, explanation


def q108_orders_prior_30d(trusted, customers, products, ctx):
    """Q108: same-customer orders in prior 30d (correlated vs RANGE)."""
    base = _valid_dates(_enriched(trusted, customers, products, ctx))
    base["d"] = pd.to_datetime(base["order_date"])
    base = base.sort_values(["customer_id", "d", "order_id"]).reset_index(
        drop=True)
    counts = []
    for cid, grp in base.groupby("customer_id"):
        dates = grp["d"].tolist()
        ids = grp["order_id"].astype(str).tolist()
        for i, (d, oid) in enumerate(zip(dates, ids)):
            n = sum(1 for j, (d2, oid2) in enumerate(zip(dates, ids))
                    if j != i and (d - d2).days >= 0
                    and (d - d2).days <= 30)
            counts.append({"order_id": oid, "prior_30d": n})
    result = pd.DataFrame(counts).sort_values("order_id").reset_index(
        drop=True)
    explanation = (
        "Window [d-30d, d] inclusive both ends, self excluded; the RANGE "
        "frame reproduces it exactly. Naive variants disagree on boundary "
        "days: '< d' drops same-day peers, '< d-30' vs '<= d-30' flips the "
        "30th day.")
    return result, explanation


def q109_qty_outliers(trusted, customers, products, ctx):
    """Q109: customer avg qty beyond 2 SD of customer averages."""
    base = _enriched(trusted, customers, products, ctx)
    base["q"] = pd.to_numeric(base["quantity"], errors="coerce")
    cust = base.groupby("customer_id")["q"].mean().dropna()
    mean, sd = float(cust.mean()), float(cust.std(ddof=0))
    lo, hi = mean - 2 * sd, mean + 2 * sd
    before = sorted(cust[(cust < lo) | (cust > hi)].index.astype(str))
    valid = base[base["q"].between(1, 10)]
    cust2 = valid.groupby("customer_id")["q"].mean().dropna()
    mean2, sd2 = float(cust2.mean()), float(cust2.std(ddof=0))
    lo2, hi2 = mean2 - 2 * sd2, mean2 + 2 * sd2
    after = sorted(cust2[(cust2 < lo2) | (cust2 > hi2)].index.astype(str))
    result = pd.DataFrame([{"stage": "before_exclusion",
                            "n_outliers": len(before)},
                           {"stage": "after_exclusion",
                            "n_outliers": len(after)}])
    explanation = (
        f"STDDEV_POP over customer means; before: {len(before)}, after "
        f"excluding out-of-range qty: {len(after)}. Exclusion shrinks SD, "
        "so borderline customers can flip either way.")
    return {"table": result, "before": before, "after": after,
            "n_before": len(before), "n_after": len(after)}, explanation


def q95_four_rising_months(trusted, customers, products, ctx):
    """Q95: monthly order count rising in each of 4 consecutive months."""
    base = _valid_dates(_enriched(trusted, customers, products, ctx))
    base["ym"] = base["order_date"].astype(str).str[:7]
    mc = (base.groupby(["customer_id", "ym"]).size().reset_index(name="n"))
    out = []
    for cid, grp in mc.groupby("customer_id"):
        grp = grp.sort_values("ym").reset_index(drop=True)
        grp["rise"] = grp["n"] > grp["n"].shift(1)
        streak, best = 0, 0
        for v in grp["rise"].tolist()[1:]:
            streak = streak + 1 if v else 0
            best = max(best, streak)
        if best >= 3:
            out.append({"customer_id": cid, "max_rise_streak": int(best)})
    result = pd.DataFrame(out, columns=["customer_id",
                                        "max_rise_streak"]).sort_values(
        "customer_id").reset_index(drop=True)
    explanation = (
        "LAG month counts; a rise streak of 3 consecutive rises = 4 months "
        "rising. Gaps-and-islands over qualifying months is required: "
        "pairwise-only comparison flags any single rise, not a sustained "
        "4-month run.")
    return {"customers": result, "n": len(result)}, explanation


def q96_paid_over_catalogue(trusted, customers, products, ctx):
    """Q96: paid >10% above catalogue (scalar subquery; dup-safe)."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    cat = (products.assign(
        _p=pd.to_numeric(products["unit_price"], errors="coerce"))
        .dropna(subset=["_p"]))
    cat = cat[cat["_p"] > 0].drop_duplicates("product_id")
    cat_map = dict(zip(cat["product_id"].astype(str), cat["_p"]))
    rows = []
    for _, r in base.iterrows():
        c = cat_map.get(str(r["product_id"]).strip())
        try:
            p = float(r["unit_price_paid"])
        except (TypeError, ValueError):
            continue
        if c is not None and p > float(c) * 1.10:
            rows.append({"order_id": r["order_id"],
                         "product_id": r["product_id"],
                         "paid": round(p, 2),
                         "catalogue": round(float(c), 2)})
    result = pd.DataFrame(rows).sort_values("order_id").reset_index(drop=True)
    explanation = (
        "Correlated scalar subquery fetches one catalogue price per order; "
        "a plain join would double-count orders if products held duplicate "
        "product_id rows. Guarded by deduping products first.")
    return result, explanation


def q97_ma_yoy(trusted, customers, products, ctx):
    """Q97: monthly value per category + 3M MA + YoY (first 12 NULL)."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    monthly = (base.groupby(["category_std", "order_month"])["line_value"]
               .sum().reset_index(name="value"))
    out = []
    for cat, grp in monthly.groupby("category_std"):
        grp = grp.sort_values("order_month").reset_index(drop=True)
        grp["ma_3m"] = grp["value"].rolling(3, min_periods=1).mean().round(2)
        shifted = grp.set_index("order_month")["value"]
        grp["yoy_value"] = grp["order_month"].map(
            lambda m, _s=shifted: _s.get(f"{int(m[:4]) - 1}{m[4:]}"))
        grp["category_std"] = cat
        out.append(grp)
    result = pd.concat(out, ignore_index=True)
    result["value"] = result["value"].round(2)
    result = result.sort_values(["category_std", "order_month"]).reset_index(
        drop=True)
    explanation = (
        "Self-join on month minus 12 months; the first 12 months show NULL "
        "YoY (no prior year exists), never 0.")
    return result, explanation


def q98_latest_payment_switch(trusted, customers, products, ctx):
    """Q98: latest order of a product used a new payment_mode (tie: date)."""
    base = _valid_dates(_enriched(trusted, customers, products, ctx))
    base = base.sort_values(["customer_id", "product_id", "order_date",
                             "order_id"])
    switched = set()
    for _, grp in base.groupby(["customer_id", "product_id"]):
        grp = grp.reset_index(drop=True)
        last = grp.iloc[-1]
        prior = set(grp.iloc[:-1]["payment_std"])
        if last["payment_std"] not in prior:
            switched.add((str(last["customer_id"]),
                          str(last["product_id"])))
    alt = set()
    base2 = base.sort_values(["customer_id", "product_id", "order_id"])
    for _, grp in base2.groupby(["customer_id", "product_id"]):
        grp = grp.reset_index(drop=True)
        last = grp.iloc[-1]
        if last["payment_std"] not in set(grp.iloc[:-1]["payment_std"]):
            alt.add((str(last["customer_id"]), str(last["product_id"])))
    result = pd.DataFrame(
        [{"customer_id": c, "product_id": p}
         for c, p in sorted(switched)]).reset_index(drop=True)
    explanation = (
        "DISTINCT ON / ROW_NUMBER keeps the latest (order_date, order_id) "
        f"row per pair. Chosen rule: {len(switched)} pairs; order_id-only "
        f"tiebreak: {len(alt)}; differs for {abs(len(switched - alt))} "
        "pairs.")
    return {"pairs": result, "n_customers": len({c for c, _ in switched}),
            "n_pairs": len(switched)}, explanation


def q99_top2_ranks_city(trusted, customers, products, ctx):
    """Q99: top two DENSE_RANKs per city, ties included."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    cust = (base.groupby(["city_std", "customer_id"])["line_value"]
            .sum().reset_index(name="total_value"))
    cust["total_value"] = cust["total_value"].round(2)
    cust["rnk"] = cust.groupby("city_std")["total_value"].rank(
        ascending=False, method="dense").astype(int)
    result = cust[cust["rnk"] <= 2].sort_values(
        ["city_std", "rnk", "customer_id"]).reset_index(drop=True)
    explanation = (
        "DENSE_RANK ties share a rank, so a city returns more than two "
        "customers whenever rank 1 or 2 is tied.")
    return result, explanation
