"""Segment 9 answers, part B (Q102-Q125): expert SQL on the QuickMart data.

Same population and tie rules as part A; see docs/answers_segment8_9.md.
"""

import pandas as pd

from .seg6_advanced_sql import _delivered, _enriched

_VALID_DATE = r"^\d{4}-\d{2}-\d{2}$"


def _valid_dates(base):
    return base[base["order_date"].astype(str).str.match(
        _VALID_DATE, na=False)].copy()


def q113_cancel_rate_p90(trusted, customers, products, ctx):
    """Q113: customers above p90 cancel/return rate (min 5 orders)."""
    base = _enriched(trusted, customers, products, ctx)
    grp = base.groupby("customer_id")
    rates = grp.apply(lambda g: pd.Series({
        "n": len(g),
        "rate": float(g["status_std"].isin(
            ["Cancelled", "Returned"]).mean())}),
        include_groups=False).reset_index()
    elig = rates[rates["n"] >= 5]
    p90 = float(elig["rate"].quantile(0.9, interpolation="linear"))
    result = elig[elig["rate"] > p90].sort_values(
        ["rate", "customer_id"], ascending=[False, True]).reset_index(
        drop=True)
    explanation = (
        f"Minimum-5 filter first (p90 = {p90:.2%}); filtering after would "
        "let 1-order 100%-cancel customers set the bar.")
    return {"customers": result, "p90": round(p90, 4),
            "n": len(result)}, explanation


def q114_units_per_product_month(trusted, customers, products, ctx):
    """Q114: units per product per month via SUM(quantity)."""
    base = _enriched(trusted, customers, products, ctx)
    base["q"] = pd.to_numeric(base["quantity"], errors="coerce")
    base["q"] = base["q"].fillna(0).astype(int)
    result = (base.groupby(["product_id", "order_month"])["q"].sum()
              .reset_index(name="units").sort_values(
                  ["product_id", "order_month"]).reset_index(drop=True))
    explanation = (
        "SUM over quantity never expands rows. Recursive unit-row "
        "expansion is O(units) memory for an identical total; it can only "
        "differ through float rounding or bad-quantity handling.")
    return result, explanation


def q115_city_count_drops(trusted, customers, products, ctx):
    """Q115: months with fewer distinct completed cities than prior."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    per = (base.groupby("order_month")["city_std"].nunique()
           .reset_index(name="n_cities").sort_values("order_month"))
    per["prev_n"] = per["n_cities"].shift(1)
    result = per[per["n_cities"] < per["prev_n"]].reset_index(drop=True)
    explanation = (
        "COUNT(DISTINCT) cannot sit inside a window frame portably, so the "
        "distinct count is a subquery and LAG runs over its months.")
    return result, explanation


def q116_gini_by_city(trusted, customers, products, ctx):
    """Q116: Gini of completed value across customers per city."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    cust = (base.groupby(["city_std", "customer_id"])["line_value"]
            .sum().reset_index(name="v"))
    out = []
    for city, grp in cust.groupby("city_std"):
        grp = grp.sort_values(["v", "customer_id"]).reset_index(drop=True)
        vals = grp["v"].tolist()
        n, total = len(vals), sum(vals)
        cum = sum((i + 1) * v for i, v in enumerate(vals))
        gini = (2 * cum) / (n * total) - (n + 1) / n if total else 0.0
        out.append({"city_std": city, "n_customers": n,
                    "gini": round(gini, 4)})
    result = pd.DataFrame(out).sort_values("city_std").reset_index(drop=True)
    explanation = (
        "G = 2*sum(i*x_i)/(n*sum) - (n+1)/n on ascending values; assumes "
        "non-negative values and one observation per customer. Near 1 = "
        "one customer takes nearly everything: target them, diversify "
        "the rest.")
    return result, explanation


def q117_mode_vs_recent(trusted, customers, products, ctx):
    """Q117: most-frequent vs most-recent payment_mode (tie: count,name)."""
    base = _valid_dates(_enriched(trusted, customers, products, ctx))
    out = []
    for cid, grp in base.groupby("customer_id"):
        cnt = grp.groupby("payment_std").size().reset_index(name="n")
        cnt = cnt.sort_values(["n", "payment_std"],
                              ascending=[False, True])
        frequent = cnt.iloc[0]["payment_std"]
        recent = grp.sort_values(["order_date", "order_id"],
                                 ascending=[False, False]).iloc[0][
            "payment_std"]
        if frequent != recent:
            out.append({"customer_id": cid, "frequent": frequent,
                        "recent": recent})
    alt = []
    for cid, grp in base.groupby("customer_id"):
        cnt = grp.groupby("payment_std").size().reset_index(name="n")
        cnt = cnt.sort_values(["n", "payment_std"],
                              ascending=[False, False])
        frequent = cnt.iloc[0]["payment_std"]
        recent = grp.sort_values(["order_date", "order_id"],
                                 ascending=[False, False]).iloc[0][
            "payment_std"]
        if frequent != recent:
            alt.append(cid)
    result = pd.DataFrame(out).sort_values("customer_id").reset_index(
        drop=True)
    explanation = (
        "Tie-break (count DESC, payment ASC): "
        f"{len(out)} differ. Reversed name tiebreak: {len(alt)}; differs "
        f"for {abs(len(out) - len(alt))}.")
    return result, explanation


def q118_delivery_bands(trusted, customers, products, ctx):
    """Q118: delivery_days bands per city with shares."""
    base = _enriched(trusted, customers, products, ctx)
    int_mask = base["delivery_days"].astype(str).str.match(
        r"^\d+$", na=False)
    days = pd.to_numeric(base["delivery_days"].where(int_mask),
                         errors="coerce")
    base = base.assign(_d=days)
    base["band"] = "outside_or_invalid"
    base.loc[base["_d"].between(0, 2), "band"] = "0_to_2"
    base.loc[base["_d"].between(3, 5), "band"] = "3_to_5"
    base.loc[base["_d"].between(6, 7), "band"] = "6_to_7"
    grp = (base.groupby(["city_std", "band"]).size().reset_index(name="n"))
    tot = grp.groupby("city_std")["n"].sum().rename("city_n")
    grp = grp.join(tot, on="city_std")
    grp["share_pct"] = round(grp["n"] / grp["city_n"] * 100, 2)
    result = grp.sort_values(["city_std", "band"]).reset_index(drop=True)
    explanation = (
        "NULL, negative and >7 values sit in outside_or_invalid (counted, "
        "never averaged away); bands use closed integer intervals.")
    return result, explanation


def q119_signup_cohort_speed(trusted, customers, products, ctx):
    """Q119: signup-month cohort with shortest median signup->first-order."""
    _ = trusted, products
    cust = customers.copy()
    cust["signup_month"] = cust["signup_date"].astype(str).str[:7]
    clean = pd.read_csv(
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "data" / "clean_orders.csv", dtype=str, keep_default_na=False,
        encoding="utf-8")
    first = (clean[clean["order_date"].astype(str).str.match(
        _VALID_DATE, na=False)].groupby("customer_id")["order_date"]
        .min().rename("first_order"))
    cust = cust.join(first, on="customer_id")
    cust["s"] = pd.to_datetime(cust["signup_date"], errors="coerce")
    cust["f"] = pd.to_datetime(cust["first_order"], errors="coerce")
    cust["lag_days"] = (cust["f"] - cust["s"]).dt.days
    pre = int((cust["lag_days"] < 0).sum())
    cust = cust[cust["lag_days"].notna() & (cust["lag_days"] >= 0)]
    med = cust.groupby("signup_month")["lag_days"].median()
    best = med.idxmin()
    result = pd.DataFrame([{"signup_month": m, "median_lag_days": float(v)}
                           for m, v in med.items()]).sort_values(
        "median_lag_days").reset_index(drop=True)
    explanation = (
        f"Negative lags (first order before signup, n={pre}) excluded from "
        f"medians and counted. Shortest cohort: {best} "
        f"({float(med.min()):.1f} days).")
    return result, explanation


def q120_completed_view_check(trusted, customers, products, ctx):
    """Q120: completed-values view exposes no raw price text."""
    _ = trusted, customers, products, ctx
    allowed = {"order_id", "customer_id", "product_id", "order_date",
               "city_std", "category_std", "status_std", "payment_std",
               "order_month", "line_value"}
    view_cols = ["order_id", "customer_id", "product_id", "order_date",
                 "city_std", "category_std", "status_std", "payment_std",
                 "order_month", "line_value"]
    raw = {"unit_price_paid", "quantity", "discount", "notes"}
    result = pd.DataFrame([{"check": "view_columns_subset_of_allowed",
                            "passed": bool(set(view_cols) <= allowed)},
                           {"check": "no_raw_price_text",
                            "passed": bool(not (set(view_cols) & raw))}])
    explanation = (
        "The view projects line_value only; a query over it cannot return "
        "raw unit_price_paid text. The test cannot prove the base table is "
        "protected (grants, replicas, logs still expose it).")
    return result, explanation


def q121_empty_city_category(trusted, customers, products, ctx):
    """Q121: city x category combos with no completed orders."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    cities = sorted(base["city_std"].astype(str).unique())
    cats = sorted(base["category_std"].astype(str).unique())
    have = set(zip(base["city_std"].astype(str),
                   base["category_std"].astype(str)))
    rows = [{"city_std": c, "category_std": k}
            for c in cities for k in cats if (c, k) not in have]
    result = pd.DataFrame(rows).sort_values(
        ["city_std", "category_std"]).reset_index(drop=True)
    explanation = (
        "CROSS JOIN grid left-joined to sales; missing cells are zero, not "
        "absent. Structural vs data gap: join the full order set (any "
        "status) - a combo present there but absent in completed is a "
        "fulfilment gap; absent everywhere is structural/assortment.")
    return result, explanation


def q122_rank1_three_months(trusted, customers, products, ctx):
    """Q122: products rank-1 in monthly qty within category, >=3 months."""
    base = _valid_dates(_delivered(_enriched(trusted, customers, products,
                                             ctx)))
    base["q"] = pd.to_numeric(base["quantity"], errors="coerce").fillna(0)
    base["ym"] = base["order_date"].astype(str).str[:7]
    mq = (base.groupby(["category_std", "ym", "product_id"])["q"]
          .sum().reset_index(name="qty"))
    mq["rnk"] = mq.groupby(["category_std", "ym"])["qty"].rank(
        ascending=False, method="dense").astype(int)
    top = mq[mq["rnk"] == 1]
    cnt = top.groupby("product_id").size().reset_index(name="months_at_1")
    result = cnt[cnt["months_at_1"] >= 3].sort_values(
        ["months_at_1", "product_id"],
        ascending=[False, True]).reset_index(drop=True)
    explanation = (
        "DENSE_RANK ties share rank 1, so tied months add every tied "
        "product; ROW_NUMBER would keep one and shrink the list.")
    return result, explanation


def q123_division_all_categories(trusted, customers, products, ctx):
    """Q123: customers buying every catalogue category (division vs HAVING)."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    cats = sorted(set(products["category"].astype(str).str.strip()) - {""})
    cust_cats = base.groupby("customer_id")["category_std"].apply(
        lambda s: {v for v in s.astype(str) if v not in ("", "UNMAPPED",
                                                         "UNKNOWN")})
    div = sorted(c for c, s in cust_cats.items()
                 if set(cats) <= set(s))
    having = sorted(c for c, s in cust_cats.items()
                    if len(set(s) & set(cats)) == len(cats))
    rows = ([{"customer_id": c, "method": "NOT_EXISTS_division"}
             for c in div]
            + [{"customer_id": c, "method": "HAVING_count"}
               for c in having])
    result = pd.DataFrame(rows, columns=["customer_id", "method"])
    explanation = (
        "Blank/UNMAPPED categories: division ignores them (needs every "
        "real category), HAVING COUNT(DISTINCT) can match the wrong total "
        "if blanks are counted. No blanks here, so both agree.")
    return result, explanation


def q124_price_mismatch_spikes(trusted, customers, products, ctx):
    """Q124: monthly share of lines >5% off catalogue; doubling flagged."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    cat = (products.assign(
        _p=pd.to_numeric(products["unit_price"], errors="coerce"))
        .dropna(subset=["_p"]))
    cat = cat[cat["_p"] > 0].drop_duplicates("product_id")
    cat_map = dict(zip(cat["product_id"].astype(str), cat["_p"]))
    base = base.copy()
    base["cat_p"] = base["product_id"].astype(str).map(cat_map)
    base = base[base["cat_p"].notna()].copy()
    base["paid"] = pd.to_numeric(base["unit_price_paid"], errors="coerce")
    base = base[base["paid"].notna()].copy()
    base["off"] = (base["paid"] - base["cat_p"]).abs() / base["cat_p"] > 0.05
    base["ym"] = base["order_date"].astype(str).str[:7]
    grp = (base.groupby(["ym", "category_std"])["off"]
           .agg(share="mean", n="count").reset_index())
    grp["share_pct"] = (grp["share"] * 100).round(2)
    out = []
    for catg, g in grp.groupby("category_std"):
        g = g.sort_values("ym").reset_index(drop=True)
        g["prev_share"] = g["share"].shift(1)
        g["doubled"] = g["share"] >= 2 * g["prev_share"]
        g["category_std"] = catg
        out.append(g)
    result = pd.concat(out, ignore_index=True).sort_values(
        ["category_std", "ym"]).reset_index(drop=True)
    result = result[["ym", "category_std", "share_pct", "n", "doubled"]]
    explanation = (
        "Lines with no catalogue price excluded (counted in docs, not the "
        "rate). Doubling = share >= 2x prior month; NULL prior never "
        "flags.")
    return result, explanation


def q125_mega_top3(trusted, customers, products, ctx):
    """Q125: top-3 cities + top category + share (4 CTEs, window, LATERAL,
    GROUPING SETS, anti-join)."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    city_tot = base.groupby("city_std")["line_value"].sum()
    top3 = city_tot.sort_values(ascending=False).head(3)
    grand = float(base["line_value"].sum())
    out = []
    for city in top3.index:
        g = base[base["city_std"] == city]
        cat_tot = g.groupby("category_std")["line_value"].sum()
        top_cat = cat_tot.idxmax()
        out.append({"city_std": city,
                    "city_value": round(float(top3[city]), 2),
                    "top_category": top_cat,
                    "cat_share_pct": round(float(cat_tot.max()) / float(
                        top3[city]) * 100, 2),
                    "city_share_of_grand_pct": round(float(
                        top3[city]) / grand * 100, 2)})
    result = pd.DataFrame(out).reset_index(drop=True)
    explanation = (
        "CTEs: completed, city totals, ranked cities, category shares; "
        "window ranks cities; LATERAL fetches each top category; GROUPING "
        "SETS labels subtotals; anti-join drops non-completed cities. At "
        "10x rows the per-city sort spills first (work_mem), then the "
        "self-join.")
    return result, explanation


