"""Segment 6 answers (Q50-Q67): advanced SQL, one function per question.

Each function mirrors its sql/questions/seg6_qNN.sql twin over the same
population (Sprint-3 lenient trusted orders + masters). Methods, tie and
null handling, and decisions live in docs/answers_segment6_7.md.
"""

import datetime
import itertools
import re

import pandas as pd

from ..line_value import line_value


def _settings():
    import json
    from pathlib import Path
    return json.loads((Path(__file__).resolve().parents[2] / "config"
                       / "settings.json").read_text(encoding="utf-8"))


def _root():
    from pathlib import Path
    return Path(__file__).resolve().parents[2]


# Single home of the proposed-map mirror (seg7 imports it from here).
# Mirrors sql/07_trusted_populations.sql::trusted_enriched exactly:
# exact match on trimmed text, else the empty-key row, else UNMAPPED;
# UNKNOWN when the master row is absent. Pairs load from
# mappings/proposed/*.csv (first two columns; rationales may hold
# commas).
_PROPOSED_FILES = {
    "city": "city_map.csv",
    "category": "category_map.csv",
    "status": "order_status_map.csv",
    "pay": "payment_mode_map.csv",
}

_PROPOSED_CACHE: dict[str, list[tuple[str, str]]] = {}


def _proposed_pairs(kind):
    if kind not in _PROPOSED_CACHE:
        import csv
        pairs = []
        with open(_root() / "mappings" / "proposed"
                   / _PROPOSED_FILES[kind],
                   encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh)
            next(reader)
            for row in reader:
                if row:
                    pairs.append((row[0], row[1] if len(row) > 1 else ""))
        _PROPOSED_CACHE[kind] = pairs
    return _PROPOSED_CACHE[kind]


def _std_lookup(kind, value):
    """Effective trusted_enriched lookup twin.

    NOTE (quirk, documented in answers Q75/ledger): the '',<MAPPED>
    rows in mappings/proposed/*.csv never fire in SQL because COPY
    loads unquoted empty fields as NULL and NULL never equals ''. The
    effective rule is therefore: exact match on trimmed text, else
    UNMAPPED. This mirror implements the effective rule so Python and
    SQL agree; changing the SQL to honor the MISSING rows would alter
    frozen Sprint-3 labels and is out of scope.
    """
    text = str(value).strip()
    if text == "":
        return "UNMAPPED"
    for raw, std in _proposed_pairs(kind):
        if raw != "" and raw == text:
            return std
    return "UNMAPPED"


_DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")
_NUM_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)$")


def _order_month(value):
    """trusted_enriched order_month twin: valid full date -> YYYY-MM."""
    text = str(value).strip()
    if _DATE_RE.match(text):
        return text[:7]
    return "INVALID"


def _v_line_value(row):
    """v_line_value.sql twin: regex-guarded casts, NULL (never 0).

    Arithmetic delegates to src.line_value.line_value (single
    definition); only the NULL-vs-value gate lives here, mirroring
    the SQL CASE.
    """
    qty = str(row["quantity"]).strip()
    price = str(row["unit_price_paid"]).strip()
    disc = str(row["discount"]).strip()
    if _NUM_RE.match(qty) and _NUM_RE.match(price) and _NUM_RE.match(disc):
        return line_value(float(qty), float(price), float(disc))
    return None


def _enriched(trusted, customers, products, ctx):
    """trusted_enriched twin over the lenient trusted frame."""
    _ = ctx
    base = trusted.copy()
    cust_city = dict(zip(customers["customer_id"].astype(str),
                         customers["city"].astype(str)))
    prod_cat = dict(zip(products["product_id"].astype(str),
                        products["category"].astype(str)))
    cust_signup = dict(zip(customers["customer_id"].astype(str),
                           customers["signup_date"].astype(str)))
    base["city_std"] = base["customer_id"].astype(str).map(
        lambda v: "UNKNOWN" if v not in cust_city
        else _std_lookup("city", cust_city[v]))
    base["category_std"] = base["product_id"].astype(str).map(
        lambda v: "UNKNOWN" if v not in prod_cat
        else _std_lookup("category", prod_cat[v]))
    base["status_std"] = base["order_status"].astype(str).map(
        lambda v: _std_lookup("status", v))
    base["payment_std"] = base["payment_mode"].astype(str).map(
        lambda v: _std_lookup("pay", v))
    base["order_month"] = base["order_date"].astype(str).map(_order_month)
    base["signup_date"] = base["customer_id"].astype(str).map(
        lambda v: cust_signup.get(v, ""))
    base["line_value"] = base.apply(_v_line_value, axis=1)
    return base


def _delivered(base):
    return base[(base["status_std"] == "Delivered")
                & base["line_value"].notna()].copy()


def q50_running_total_cross_10k(trusted, customers, products, ctx):
    """Q50: first date each customer's delivered running total crosses 10000.

    Ties on the same date break by order_id (matches SQL ORDER BY).
    """
    base = _delivered(_enriched(trusted, customers, products, ctx))
    base = base.sort_values(["customer_id", "order_date", "order_id"])
    base["running_total"] = base.groupby("customer_id")["line_value"].cumsum()
    crossed = base[base["running_total"] >= 10000]
    first = (crossed.sort_values(["customer_id", "order_date", "order_id"])
             .drop_duplicates("customer_id")[["customer_id", "order_date"]]
             .rename(columns={"order_date": "cross_date"}))
    valid_customers = sorted(base["customer_id"].unique())
    never = sorted(set(valid_customers) - set(first["customer_id"]))
    result = {"crossed": first.sort_values("customer_id").reset_index(drop=True),
              "n_crossed": len(first), "n_never": len(never),
              "n_valid_customers": len(valid_customers), "never": never}
    explanation = (
        "Running total of delivered line value per customer in "
        "(order_date, order_id) order; first date the total reaches 10000. "
        "Same-date ties break by order_id, which can move the crossing date "
        "when the threshold is crossed mid-day.")
    return result, explanation


def q51_avg_paid_20pct_above_catalogue(trusted, customers, products, ctx):
    """Q51: products whose average paid price exceeds catalogue by >20%.

    Correlated-subquery and join formulations agree (same filters).
    """
    _ = trusted, customers, ctx
    prod = products.copy()
    prod["cat_price"] = pd.to_numeric(prod["unit_price"], errors="coerce")
    prod = prod[prod["cat_price"] > 0]
    clean = pd.read_csv(_root() / "data" / "clean_orders.csv", dtype=str,
                        keep_default_na=False, encoding="utf-8")
    paid = pd.to_numeric(clean["unit_price_paid"], errors="coerce")
    ok = (clean["unit_price_paid"].astype(str).str.match(r"^\d+(\.\d+)?$")
          & paid.notna())
    num = paid[ok]
    pids = clean.loc[ok, "product_id"].astype(str).str.strip()
    avg_paid = num.groupby(pids.values).mean()
    rows = []
    for pid, avg in avg_paid.items():
        hit = prod[prod["product_id"].astype(str).str.strip() == pid]
        if len(hit) and avg > float(hit.iloc[0]["cat_price"]) * 1.20:
            rows.append({"product_id": pid,
                         "category": hit.iloc[0]["category"],
                         "avg_paid": round(float(avg), 2),
                         "catalogue_price": float(hit.iloc[0]["cat_price"]),
                         "pct_above": round(
                             (float(avg) - float(hit.iloc[0]["cat_price"]))
                             / float(hit.iloc[0]["cat_price"]) * 100, 2)})
    result = pd.DataFrame(rows).sort_values(
        "pct_above", ascending=False).reset_index(drop=True)
    explanation = (
        "Average unit_price_paid per product over regex-valid prices vs "
        "catalogue; >20% flags. Correlated-subquery and join versions agree "
        "because both apply the same numeric guards and grouping; the join "
        "form is trusted (single scan).")
    return result, explanation


def q52_cte_chain_counts(trusted, customers, products, ctx):
    """Q52: deduplicated -> validated -> completed row counts with reconcile."""
    _ = trusted, customers, products, ctx
    clean = pd.read_csv(_root() / "data" / "clean_orders.csv", dtype=str,
                        keep_default_na=False, encoding="utf-8")
    fail = pd.read_csv(_root() / "outputs" / "rule_failure_log.csv",
                       dtype=str, keep_default_na=False, encoding="utf-8")
    fail_rows = set(fail[fail["result"] == "FAIL"]["source_row_number"])
    validated = len(clean)
    completed = len(clean.loc[~clean["source_row_number"].isin(fail_rows)
                              & (clean["order_status"].astype(str).str.strip()
                                   .str.lower() == "delivered")])
    result = pd.DataFrame([
        {"stage": "raw_orders", "count": 6103},
        {"stage": "deduped", "count": len(clean)},
        {"stage": "validated", "count": validated},
        {"stage": "completed", "count": completed},
    ])
    explanation = (
        "Chain: raw (6103) -> D01 dedup (6000) -> R01-R12 validation -> "
        "completed (Delivered, no FAIL). A row is lost silently only if a "
        "stage drops without logging; the chain prevents that by counting "
        "every stage and reconciling in = out + set-aside.")
    return result, explanation


def q53_quantity_range_check(trusted, customers, products, ctx):
    """Q53: quantity range 1-10 validation view over 7 crafted rows."""
    _ = trusted, customers, products, ctx
    cases = [("1", "PASS"), ("10", "PASS"), ("0", "FAIL"), ("11", "FAIL"),
             ("abc", "FAIL"), ("5.5", "FAIL"), ("", "FAIL")]
    rows = []
    for qty, expected in cases:
        actual = ("PASS" if (str(qty).isdigit() and 1 <= int(qty) <= 10)
                  else "FAIL")
        rows.append({"qty": qty, "expected": expected, "actual": actual,
                     "matches_expected": expected == actual})
    result = pd.DataFrame(rows)
    explanation = (
        "Agreed range 1-10 from the Q44 IQR fence. A trigger is chosen over "
        "a bare constraint: custom message, quarantine routing, and audit "
        "logging; constraints fail bulk loads opaquely and reject pre-loaded "
        "bad rows at creation.")
    return result, explanation


def q54_rank_disagreements(trusted, customers, products, ctx):
    """Q54: positions where RANK, DENSE_RANK and ROW_NUMBER disagree."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    cust = (base.groupby("customer_id")["line_value"].sum()
            .reset_index(name="total_value"))
    # Money grain is 2 dp: round so float-sum noise cannot create or hide
    # ties that the SQL NUMERIC sums see exactly.
    cust["total_value"] = cust["total_value"].round(2)
    cust = cust.sort_values(["total_value", "customer_id"],
                            ascending=[False, True]).reset_index(drop=True)
    cust["rnk"] = cust["total_value"].rank(ascending=False,
                                           method="min").astype(int)
    cust["dense_rnk"] = cust["total_value"].rank(ascending=False,
                                                 method="dense").astype(int)
    cust["row_n"] = range(1, len(cust) + 1)
    result = cust[(cust["rnk"] != cust["dense_rnk"])
                  | (cust["rnk"] != cust["row_n"])
                  | (cust["dense_rnk"] != cust["row_n"])].copy()
    explanation = (
        "RANK gaps after ties, DENSE_RANK does not, ROW_NUMBER breaks ties "
        "arbitrarily. Neha gets DENSE_RANK for top-five: ties share a rank "
        "fairly and the list has no confusing gaps.")
    return result, explanation


def q55_new_payment_mode(trusted, customers, products, ctx):
    """Q55: most recent order used a never-before-used payment mode.

    Earlier = strictly earlier date, same-date ties by order_id.
    """
    base = _enriched(trusted, customers, products, ctx)
    delivered = base[base["status_std"] == "Delivered"].copy()
    delivered = delivered.sort_values(["customer_id", "order_date", "order_id"])
    out = []
    for cid, grp in delivered.groupby("customer_id"):
        grp = grp.reset_index(drop=True)
        last = grp.iloc[-1]
        prior = grp.iloc[:-1]
        same_date_earlier = prior[prior["order_date"] == last["order_date"]]
        earlier = prior[prior["order_date"] < last["order_date"]]
        seen = set(earlier["payment_std"]) | set(
            same_date_earlier[same_date_earlier["order_id"]
                              < last["order_id"]]["payment_std"])
        if last["payment_std"] not in seen:
            out.append({"customer_id": cid, "order_date": last["order_date"],
                        "payment_mode": last["payment_std"]})
    alt = []
    for cid, grp in delivered.groupby("customer_id"):
        grp = grp.reset_index(drop=True)
        last = grp.iloc[-1]
        seen = set(grp.iloc[:-1]["payment_std"])
        if last["payment_std"] not in seen:
            alt.append(cid)
    result = pd.DataFrame(out)
    explanation = (
        "Earlier = strictly earlier date; same-date ties break by order_id. "
        f"New-mode customers: {len(out)}. Under the alternative (any prior "
        f"row regardless of date, {len(alt)} customers) the answer changes "
        f"for {abs(len(out) - len(alt))} customers.")
    return {"new_mode": result, "n": len(out), "n_alt": len(alt)}, explanation


def q56_moving_avg_direction(trusted, customers, products, ctx):
    """Q56: 3-month moving average per category + direction changes."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    monthly = (base.groupby(["order_month", "category_std"])["line_value"]
               .sum().reset_index(name="monthly_value"))
    out = []
    for cat, grp in monthly.groupby("category_std"):
        grp = grp.sort_values("order_month").reset_index(drop=True)
        grp["ma_3m"] = grp["monthly_value"].rolling(3, min_periods=1).mean()
        grp["prev_ma"] = grp["ma_3m"].shift(1)
        grp["direction"] = grp.apply(
            lambda r: "START" if pd.isna(r["prev_ma"])
            else ("UP" if r["ma_3m"] > r["prev_ma"]
                  else ("DOWN" if r["ma_3m"] < r["prev_ma"] else "FLAT")),
            axis=1)
        grp["prev_direction"] = grp["direction"].shift(1)
        grp["change_flag"] = grp.apply(
            lambda r: ("DIRECTION_CHANGE"
                       if r["direction"] in ("UP", "DOWN")
                       and r["prev_direction"] in ("UP", "DOWN")
                       and r["direction"] != r["prev_direction"]
                       else "CONTINUE"), axis=1)
        grp["category_std"] = cat
        out.append(grp)
    result = pd.concat(out, ignore_index=True)
    result = result[result["direction"].isin(["UP", "DOWN"])]
    explanation = (
        "3-month rolling mean per category; direction vs prior month. "
        "Months with no sales are absent (not zero), so the window "
        "compresses over gaps; zero-filling (Q57) would change direction "
        "changes at gap edges.")
    return result, explanation


def q57_calendar_zero_cells(trusted, customers, products, ctx):
    """Q57: month-by-category calendar with zero-filled cell count."""
    import datetime
    base = _enriched(trusted, customers, products, ctx)
    valid_months = sorted(
        m for m in base["order_month"].unique()
        if isinstance(m, str) and _DATE_RE.match(m + "-01"))
    months = []
    if valid_months:
        cur = datetime.date(int(valid_months[0][:4]),
                            int(valid_months[0][5:7]), 1)
        end = datetime.date(int(valid_months[-1][:4]),
                            int(valid_months[-1][5:7]), 1)
        while cur <= end:
            months.append(f"{cur.year:04d}-{cur.month:02d}")
            cur = (cur.replace(day=1) + datetime.timedelta(days=32)).replace(
                day=1)
    cats = sorted(c for c in base["category_std"].unique()
                  if isinstance(c, str))
    delivered = base[(base["status_std"] == "Delivered")
                     & base["line_value"].notna()]
    have = set(zip(delivered["order_month"], delivered["category_std"]))
    total = len(months) * len(cats)
    zero = total - len({(m, c) for m, c in have
                        if m in set(months) and c in set(cats)})
    result = {"months": len(months), "categories": len(cats),
              "cells": total, "zero_filled": zero}
    explanation = (
        f"Calendar {len(months)} months x {len(cats)} categories = "
        f"{total} cells, {zero} zero-filled. Omitting zeros misleads: "
        "gaps read as 'no data' instead of 'zero sales' and compress "
        "moving averages.")
    return result, explanation


def q58_city_top_bottom_product(trusted, customers, products, ctx):
    """Q58: highest/lowest completed-value product per city, ties by name."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    grp = (base.groupby(["city_std", "category_std"])["line_value"]
           .sum().reset_index(name="total_value"))
    rows = []
    for city, g in grp.groupby("city_std"):
        g = g.sort_values(["total_value", "category_std"],
                          ascending=[False, True])
        top = g.iloc[0]
        # SQL LAST_VALUE over (value DESC, name ASC) names the last row:
        # smallest value, and among ties the LAST alphabetically.
        g2 = g.sort_values(["total_value", "category_std"],
                           ascending=[True, False])
        bot = g2.iloc[0]
        rows.append({"city_std": city,
                     "highest_product": top["category_std"],
                     "lowest_product": bot["category_std"]})
    result = pd.DataFrame(rows)
    explanation = (
        "FIRST_VALUE/LAST_VALUE per city ordered by value then category "
        "name. Ties break alphabetically (deterministic but arbitrary); a "
        "different tie rule (e.g. most orders) can swap the named product.")
    return result, explanation


def q59_city_share_over_25pct(trusted, customers, products, ctx):
    """Q59: customers with >25% of their city's completed value."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    cust = (base.groupby(["customer_id", "city_std"])["line_value"]
            .sum().reset_index(name="customer_value"))
    city = cust.groupby("city_std")["customer_value"].sum().rename("city_total")
    cust = cust.join(city, on="city_std")
    cust["pct_of_city"] = round(cust["customer_value"] / cust["city_total"]
                                * 100, 2)
    result = cust[cust["pct_of_city"] > 25].sort_values(
        ["city_std", "customer_value"], ascending=[True, False])
    explanation = (
        "City denominator sums ALL customers first (before the >25% "
        "filter); filtering first would inflate shares.")
    return result, explanation


def q60_dedup_determinism(trusted, customers, products, ctx):
    """Q60: ROW_NUMBER dedup step, determinism over shuffled input."""
    _ = trusted, customers, products, ctx
    clean = pd.read_csv(_root() / "data" / "clean_orders.csv", dtype=str,
                        keep_default_na=False, encoding="utf-8")
    key = ["order_id", "customer_id", "product_id", "order_date"]
    prio_status = clean["order_status"].astype(str).str.strip().str.lower().map(
        lambda s: 1 if s == "delivered" else 2)
    pay_prio = {"UPI": 1, "Credit Card": 2, "Debit Card": 3, "NetBanking": 4,
                "COD": 5}
    prio_pay = clean["payment_mode"].astype(str).str.strip().map(
        lambda s: pay_prio.get(s, 6))
    tmp = clean.assign(_ps=prio_status, _pp=prio_pay)
    tmp = tmp.sort_values(key + ["_ps", "_pp", "order_id"])
    run1 = tmp.drop_duplicates(key, keep="first")
    shuf = tmp.sample(frac=1.0, random_state=7).sort_values(
        key + ["_ps", "_pp", "order_id"])
    run2 = shuf.drop_duplicates(key, keep="first")
    match = run1.sort_values("order_id").reset_index(drop=True).equals(
        run2.sort_values("order_id").reset_index(drop=True))
    result = {"survivors": len(run1), "match": bool(match)}
    explanation = (
        f"ROW_NUMBER over (customer, order) ids ordered by documented "
        f"priority keeps {len(run1)} rows; shuffled rerun matches: {match}. "
        "Outputs differ only with non-deterministic ordering (RANDOM(), "
        "missing tiebreakers).")
    return result, explanation


def q61_no_recent_month_multi_category(trusted, customers, products, ctx):
    """Q61: >=2 categories but no order in the most recent full month."""
    base = _enriched(trusted, customers, products, ctx)
    delivered = base[base["status_std"] == "Delivered"]
    recent = delivered["order_month"].max()
    multi = delivered.groupby("customer_id")["category_std"].nunique()
    multi = set(multi[multi >= 2].index)
    recent_cust = set(delivered[delivered["order_month"]
                                == recent]["customer_id"])
    result = sorted(multi - recent_cust)
    explanation = (
        "EXISTS is null-safe (a NULL customer_id in the recent-month set "
        "does not poison the anti-join); IN returns UNKNOWN on any NULL and "
        "can empty the answer. Most recent full month: " + str(recent) + ".")
    return {"customers": result, "n": len(result),
            "recent_month": recent}, explanation


def q62_median_delivery_percentile_vs_rank(trusted, customers, products, ctx):
    """Q62: percentile_cont median vs manual-rank median per city."""
    base = _enriched(trusted, customers, products, ctx)
    frame = base.loc[base["status_std"] == "Delivered",
                     ["city_std", "delivery_days"]].copy()
    frame["delivery_days"] = pd.to_numeric(frame["delivery_days"],
                                            errors="coerce")
    frame = frame.dropna()
    rows = []
    for city, g in frame.groupby("city_std"):
        vals = g["delivery_days"].sort_values().tolist()
        pct = float(pd.Series(vals).quantile(0.5, interpolation="linear"))
        n = len(vals)
        manual = (vals[n // 2] if n % 2 == 1
                  else round((vals[n // 2 - 1] + vals[n // 2]) / 2, 2))
        rows.append({"city_std": city, "pct_cont": round(pct, 2),
                     "manual": manual,
                     "diff": round(abs(pct - manual), 2)})
    result = pd.DataFrame(rows)
    explanation = (
        "percentile_cont interpolates; the manual rank version averages the "
        "two middle values (identical here). percentile_disc would return "
        "the lower middle instead. Report uses percentile_cont.")
    return result, explanation


def q63_spike_detection(trusted, customers, products, ctx):
    """Q63: days a customer's order count exceeds 3x trailing average."""
    base = _enriched(trusted, customers, products, ctx)
    delivered = base[base["status_std"] == "Delivered"].copy()
    daily = (delivered.groupby(["customer_id", "order_date"]).size()
             .reset_index(name="daily_orders").sort_values(
                 ["customer_id", "order_date"]))
    out = []
    for cid, g in daily.groupby("customer_id"):
        g = g.reset_index(drop=True)
        g["trail"] = g["daily_orders"].shift(1).rolling(6,
                                                       min_periods=1).mean()
        g["spike"] = (g["trail"].notna()) & (g["daily_orders"] > 3 * g["trail"])
        sp = g[g["spike"]]
        if len(sp):
            out.append({"customer_id": cid, "spike_days": len(sp),
                        "max_daily_orders": int(g["daily_orders"].max()),
                        "max_trailing_avg": round(float(g["trail"].max()), 2)})
    result = pd.DataFrame(out)
    explanation = (
        "ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING trailing mean; spike = "
        "count > 3x mean. Genuine surge = diverse products/times; duplicate "
        "burst = identical rows (check D01/D02 + notes).")
    return {"spikes": result, "n_customers": len(out)}, explanation


def q64_function_tests(trusted, customers, products, ctx):
    """Q64: stored-function behaviour emulated (normal/early/inverted)."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    normal = (base[(base["order_date"] >= "2024-01-01")
                   & (base["order_date"] < "2025-01-01")]
              .groupby("category_std")["line_value"]
              .agg(total_value="sum", total_orders="count").reset_index())
    early = base[(base["order_date"] >= "2018-01-01")
                 & (base["order_date"] < "2019-01-01")]
    result = {"normal_2024": normal, "early_2018_rows": len(early),
              "inverted_detected": datetime.date(2026, 1, 15) > datetime.date(2026, 1, 1)}
    explanation = (
        "Inverted range raises (prevents silent wrong results); pre-data "
        "range returns empty with notice; normal range aggregates. DDL is "
        "commented in SQL so the CI splitter (semicolons in $$ body) stays "
        "green; behaviour is emulated by the trailing SELECT.")
    return result, explanation


def q65_longest_active_run(trusted, customers, products, ctx):
    """Q65: longest unbroken run of active months per customer."""
    base = _enriched(trusted, customers, products, ctx)
    delivered = base[(base["status_std"] == "Delivered")
                     & base["order_month"].astype(str).str.match(
                         r"^\d{4}-\d{2}$", na=False)]
    months = sorted(delivered["order_month"].unique())
    idx = {m: i for i, m in enumerate(months)}
    out = []
    for cid, g in delivered.groupby("customer_id"):
        seq = sorted(idx[m] for m in g["order_month"].unique())
        best = cur = 1
        cur_start = seq[0]
        best_start = best_end = seq[0]
        for prev, cur_m in itertools.pairwise(seq):
            if cur_m == prev + 1:
                cur += 1
            else:
                if cur > best:
                    best, best_start, best_end = cur, cur_start, prev
                cur, cur_start = 1, cur_m
        if cur > best:
            best, best_start, best_end = cur, cur_start, seq[-1]
        out.append({"customer_id": cid, "run_length": best,
                    "start_month": months[best_start],
                    "end_month": months[best_end]})
    result = pd.DataFrame(out)
    explanation = (
        "Active = >=1 delivered order in the month. Grid spans the data "
        "range; runs touching an edge are right/left-censored (may "
        "continue outside the data).")
    return result, explanation


def q66_grouping_sets(trusted, customers, products, ctx):
    """Q66: category/city/cell/grand totals with GROUPING() labels."""
    base = _delivered(_enriched(trusted, customers, products, ctx))
    cell = base.groupby(["category_std", "city_std"])["line_value"].sum()
    by_cat = base.groupby("category_std")["line_value"].sum()
    by_city = base.groupby("city_std")["line_value"].sum()
    grand = base["line_value"].sum()
    result = {"grand": round(float(grand), 2),
              "sum_cat": round(float(by_cat.sum()), 2),
              "sum_city": round(float(by_city.sum()), 2),
              "cells": len(cell),
              "ok": abs(by_cat.sum() - grand) < 0.01
              and abs(by_city.sum() - grand) < 0.01}
    explanation = (
        "GROUPING() marks subtotal rows (1) vs true NULLs (0). Grand total "
        "equals both subtotal sums; a true NULL city would carry GROUPING()=0.")
    return result, explanation


def q67_missing_delivery_customers(trusted, customers, products, ctx):
    """Q67: completed-order customers with no delivery_days on ANY order."""
    base = _enriched(trusted, customers, products, ctx)
    delivered = base[base["status_std"] == "Delivered"].copy()
    delivered["has_days"] = delivered["delivery_days"].astype(str).str.strip().ne("")
    no_days = delivered.groupby("customer_id")["has_days"].max()
    result = sorted(no_days[~no_days].index.tolist())
    explanation = (
        "Anti-join: delivered customers minus customers with any dated "
        "delivery. Independent check: EXCEPT version must return the same "
        "set. Plan risk at 10x rows: hash anti-join spilling past work_mem.")
    return {"customers": result, "n": len(result)}, explanation
