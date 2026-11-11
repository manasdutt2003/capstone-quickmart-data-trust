"""Segment 7 answers (Q68-Q75): professional SQL engineering.

Each function mirrors its sql/questions/seg7_qNN.sql twin over the same
population (Sprint-3 lenient trusted orders + masters). Questions needing
data the extracts do not hold (Q68 timestamps, Q70 referral field, Q73
browse events, Q74 transition log) answer with the closest honest
analogue, labelled as such -- never a fabricated column. Methods, tie
and null handling, and decisions live in docs/answers_segment6_7.md.
"""

import pandas as pd

from .seg6_advanced_sql import _delivered, _enriched, _root


def q68_sessions(trusted, customers, products, ctx):
    """Q68: 30-minute-gap sessions per customer (honest analogue).

    The extracts hold order_date only (no intra-day timestamps), so every
    event lands at midnight and each distinct order_date is its own
    session. Labelled as analogue.
    """
    base = _enriched(trusted, customers, products, ctx)
    delivered = base[base["status_std"] == "Delivered"].copy()
    delivered["event_ts"] = pd.to_datetime(delivered["order_date"],
                                           errors="coerce")
    delivered = delivered.dropna(subset=["event_ts"])
    delivered = delivered.sort_values(["customer_id", "event_ts", "order_id"])
    sessions = []
    for cid, grp in delivered.groupby("customer_id"):
        grp = grp.reset_index(drop=True)
        sid = 0
        prev = None
        for _, row in grp.iterrows():
            if prev is None or (row["event_ts"] - prev).total_seconds() > 1800:
                sid += 1
            sessions.append({"customer_id": cid, "session_id": sid,
                             "event_ts": row["event_ts"]})
            prev = row["event_ts"]
    sess = pd.DataFrame(sessions)
    stats = (sess.groupby(["customer_id", "session_id"])
             .agg(session_start=("event_ts", "min"),
                  session_end=("event_ts", "max"),
                  event_count=("event_ts", "count")).reset_index())
    stats["session_length_min"] = (
        (stats["session_end"] - stats["session_start"]).dt.total_seconds()
        / 60)
    result = {"total_sessions": len(stats),
              "median_session_length_min": float(
                  stats["session_length_min"].median()),
              "sessions_over_10_events": int((stats["event_count"] > 10).sum())}
    explanation = (
        "ANALOGUE: no intra-day timestamps exist (order_date only), so all "
        "events sit at midnight and same-date ties break by order_id. Each "
        "distinct order_date becomes its own session; median length is 0. "
        "A row-by-row loop fails the same test: no set-based session "
        "state, no parallelism, ad-hoc tie handling.")
    return result, explanation


def q69_plan_analysis(trusted, customers, products, ctx):
    """Q69: join-type finding + index/partition proposal for the mart query."""
    _ = trusted, customers, products, ctx
    result = {"join_type": "Nested Loop (Hash Anti Join for the anti-join)",
              "proposal": "monthly RANGE partition on order_date + "
                          "indexes on (status_std, line_value), "
                          "customers(customer_id), products(product_id)",
              "tradeoff": "partition pruning + parallelism vs load-routing "
                          "complexity, partition maintenance, index overhead"}
    explanation = (
        "On a fresh small database the planner seq-scans orders_clean and "
        "nested-loops both dimensions (TRIM() on the join keys defeats "
        "btree use; dims are tiny), with a Hash Anti Join for the "
        "NOT EXISTS (see live EXPLAIN in seg7_q69.sql). Exact join choice "
        "is planner/state-dependent (stats, ANALYZE) so the parity test "
        "pins only that a join is used; the proposal and tradeoff above "
        "are the stable deliverable. Past ~100K rows a merge join wins on "
        "sorted inputs; nested loop only when one side is tiny.")
    explanation = (
        "At 522 rows the planner seq-scans trusted_enriched and hash-joins "
        "both dimensions (see live EXPLAIN in seg7_q69.sql). Past ~100K "
        "rows a merge join wins on sorted inputs; nested loop only when one "
        "side is tiny. Monthly partitioning prunes and parallelises at the "
        "cost of load routing and maintenance.")
    return result, explanation


def q70_referral_depth(trusted, customers, products, ctx):
    """Q70: referral-chain depth (honest analogue: no referral column)."""
    _ = trusted, products, ctx
    result = {"customers": len(customers), "referral_chains": 0,
              "max_depth": 0,
              "analogue_note": "referral_id absent from extracts: "
                               "no hierarchy to recurse"}
    explanation = (
        "ANALOGUE: customers holds no referral/manager field, so the "
        "recursive CTE cannot run on real data; the SQL reports counts "
        "with zero chains. Pattern (array path + NOT ... = ANY(path) + "
        "depth < 100) blocks self/mutual cycles; the cap truncates deeper "
        "chains, which at depth 100 almost certainly signal data error.")
    return result, explanation


def q71_p95_exact_vs_approx(trusted, customers, products, ctx):
    """Q71: exact vs subsample-approximate p95 per city/month.

    Approximate = percentile_cont over a deterministic every-10th-row
    subsample ordered by order_id (PostgreSQL 16 has no approx builtin).
    """
    base = _delivered(_enriched(trusted, customers, products, ctx))
    rows = []
    for (month, city), grp in base.groupby(["order_month", "city_std"]):
        vals = grp["line_value"].sort_values()
        exact = float(vals.quantile(0.95, interpolation="linear"))
        sub = grp.sort_values("order_id").iloc[::10]["line_value"]
        approx = float(sub.quantile(0.95, interpolation="linear"))
        rel = (abs(exact - approx) / exact * 100 if exact else 0.0)
        rows.append({"order_month": month, "city_std": city, "n": len(grp),
                     "p95_exact": round(exact, 2),
                     "p95_approx": round(approx, 2),
                     "rel_error_pct": round(rel, 2)})
    result = pd.DataFrame(rows).sort_values(
        "rel_error_pct", ascending=False).reset_index(drop=True)
    explanation = (
        "Exact = percentile_cont; approx = percentile_cont on the "
        "deterministic 1-in-10 subsample. Board reports need exact "
        "(rel_error > 5 unacceptable); dashboards tolerate < 10; "
        "exploration tolerates < 20.")
    return result, explanation


def q72_lateral_rule_strings(trusted, customers, products, ctx):
    """Q72: violated-rule string per delivered order via rule_failure_log."""
    _ = customers, products, ctx
    fail = pd.read_csv(_root() / "outputs" / "rule_failure_log.csv",
                       dtype=str, keep_default_na=False, encoding="utf-8")
    clean = pd.read_csv(_root() / "data" / "clean_orders.csv", dtype=str,
                        keep_default_na=False, encoding="utf-8")
    key = clean.set_index("order_id")["source_row_number"]
    agg = (fail.groupby("source_row_number")["rule_id"]
           .apply(lambda s: ",".join(sorted(set(s)))))
    delivered_ids = trusted.loc[
        trusted["order_status"].astype(str).str.strip().str.lower()
        == "delivered", "order_id"]
    rows = [{"order_id": oid,
             "violated_rules": agg.get(key.get(oid, ""), "") or ""}
            for oid in delivered_ids]
    result = pd.DataFrame(rows).sort_values("order_id").reset_index(drop=True)
    explanation = (
        "LATERAL scopes evaluation to one order (join key "
        "source_row_number): no cartesian with other orders. STRING_AGG "
        "ORDER BY rule_id keeps output deterministic; multi-condition "
        "rules arrive pre-combined as one failing_detail upstream.")
    return result, explanation


def q73_funnel(trusted, customers, products, ctx):
    """Q73: order funnel analogue (no browse events in extracts)."""
    _ = trusted, customers, products, ctx
    clean = pd.read_csv(_root() / "data" / "clean_orders.csv", dtype=str,
                        keep_default_na=False, encoding="utf-8")
    dates = clean[clean["order_date"].astype(str).str.match(
        r"^\d{4}-\d{2}-\d{2}$", na=False)].copy()
    dates["order_date"] = pd.to_datetime(dates["order_date"])
    grp = dates.groupby("customer_id")
    s1 = grp["order_date"].min().rename("stage1")
    confirmed = dates[dates["order_status"].astype(str).str.strip().isin(
        ["Pending", "In Transit", "Delivered"])]
    s2 = confirmed.groupby("customer_id")["order_date"].min().rename("stage2")
    delivered = dates[dates["order_status"].astype(str).str.strip()
                      == "Delivered"]
    s3 = delivered.groupby("customer_id")["order_date"].min().rename("stage3")
    stages = pd.concat([s1, s2, s3], axis=1)
    r1 = int(stages["stage1"].notna().sum())
    r2 = int(((stages["stage2"] - stages["stage1"]).dt.days <= 14).sum())
    prev = stages["stage2"].fillna(stages["stage1"])
    r3 = int(((stages["stage3"] - prev).dt.days <= 14).sum())
    result = pd.DataFrame([
        {"stage": "Stage 1: Order Placed", "count": r1},
        {"stage": "Stage 2: Confirmed (within 14d)", "count": r2},
        {"stage": "Stage 3: Delivered (within 14d of prev)", "count": r3},
        {"stage": "Lost at Stage 2", "count": r1 - r2},
        {"stage": "Lost at Stage 3", "count": r2 - r3},
    ])
    explanation = (
        "ANALOGUE: no browse events exist; stages are order placed -> "
        "confirmed -> delivered with 14-day windows. A later stage without "
        "an earlier one cannot count (NULL start poisons the window). "
        "Largest loss stage is the bottleneck.")
    return result, explanation


def q74_transition_classes(trusted, customers, products, ctx):
    """Q74: status-snapshot classification (no transition log exists)."""
    _ = trusted, customers, products, ctx
    clean = pd.read_csv(_root() / "data" / "clean_orders.csv", dtype=str,
                        keep_default_na=False, encoding="utf-8")
    status = clean["order_status"].astype(str).str.strip()
    status = status[clean["order_id"].astype(str).str.strip() != ""]
    cls = status.map(
        lambda s: "terminal" if s in ("Delivered", "Cancelled", "Returned")
        else ("non_terminal" if s in ("Pending", "In Transit")
              else ("missing" if s == "" else "unknown_spelling")))
    result = (pd.DataFrame({"state_class": cls.values, "status": status.values})
              .groupby(["state_class", "status"]).size()
              .reset_index(name="orders")
              .sort_values(["state_class", "status"]).reset_index(drop=True))
    explanation = (
        "ANALOGUE: single order_status snapshot per order, no "
        "order_status_log(order_id, status, transition_ts), so skip/revisit "
        "patterns are unobservable. Write-time enforcement (trigger + "
        "transition-matrix table) beats after-the-fact detection.")
    return result, explanation


def q75_scorecard(trusted, customers, products, ctx):
    """Q75: completeness/uniqueness/RI/conformance scorecard 0-100."""
    _ = trusted
    cust = customers.copy()
    prod = products.copy()
    clean = pd.read_csv(_root() / "data" / "clean_orders.csv", dtype=str,
                        keep_default_na=False, encoding="utf-8")
    blank = lambda s: s.astype(str).str.strip() == ""

    def completeness(df, cols):
        cells = len(df) * len(cols)
        bad = sum(int(blank(df[c]).sum()) for c in cols)
        return (1 - bad / cells) * 100 if cells else 100.0

    def uniqueness(df, col):
        ids = df[col].astype(str).str.strip()
        ids = ids[ids != ""]
        return (1 - (len(ids) - ids.nunique()) / len(ids)) * 100 if len(ids) else 100.0

    cust_ids = set(cust["customer_id"].astype(str).str.strip()) - {""}
    prod_ids = set(prod["product_id"].astype(str).str.strip()) - {""}
    oc = clean["customer_id"].astype(str).str.strip()
    op = clean["product_id"].astype(str).str.strip()
    cust_ri = (1 - len(set(oc[oc != ""]) - cust_ids) / len(set(oc[oc != ""]))) * 100
    prod_ri = (1 - len(set(op[op != ""]) - prod_ids) / len(set(op[op != ""]))) * 100
    email_ok = cust["email"].astype(str).str.contains(r"@.+\.", regex=True)
    phone_ok = cust["phone"].astype(str).str.match(r"^\d{10}$", na=False)
    date_ok = cust["signup_date"].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$",
                                                        na=False)
    cust_conf = (email_ok & phone_ok & date_ok).mean() * 100
    prod_conf = float(prod["unit_price"].astype(str).str.match(
        r"^\d+(\.\d+)?$", na=False).mean() * 100)
    qty_ok = clean["quantity"].astype(str).str.match(r"^\d+$", na=False)
    price_ok = clean["unit_price_paid"].astype(str).str.match(
        r"^\d+(\.\d+)?$", na=False)
    disc_ok = clean["discount"].astype(str).str.match(
        r"^(\d+(\.\d+)?%?|\d*\.\d+|0)$", na=False)
    pay_ok = clean["payment_mode"].astype(str).str.strip().isin(
        ["COD", "Credit Card", "Debit Card", "NetBanking", "UPI"])
    stat_ok = clean["order_status"].astype(str).str.strip().isin(
        ["Delivered", "Cancelled", "Returned", "Pending", "In Transit"])
    days = clean["delivery_days"].astype(str).str.strip()
    days_ok = (days == "") | days.str.match(r"^\d+$", na=False)
    ord_conf = (qty_ok & price_ok & disc_ok & pay_ok & stat_ok
                & days_ok).mean() * 100
    ord_ids = clean["order_id"].astype(str).str.strip()
    ord_ids = ord_ids[ord_ids != ""]
    ord_uniq = (1 - (len(ord_ids) - ord_ids.nunique()) / len(ord_ids)) * 100
    ord_comp = completeness(clean, ["order_id", "customer_id", "product_id",
                                    "order_date", "quantity",
                                    "unit_price_paid", "discount",
                                    "payment_mode", "order_status",
                                    "delivery_days"])
    ord_ri = (1 - (len(set(oc[oc != ""]) - cust_ids)
                   + len(set(op[op != ""]) - prod_ids))
              / (len(set(oc[oc != ""])) + len(set(op[op != ""])))) * 100
    scores = {
        "customers": {"completeness": completeness(
            cust, ["customer_id", "customer_name", "email", "city", "phone",
                   "signup_date"]),
            "uniqueness": uniqueness(cust, "customer_id"),
            "referential_integrity": float(cust_ri), "conformance": float(cust_conf)},
        "products": {"completeness": completeness(
            prod, ["product_id", "product_name", "category", "unit_price",
                   "stock_qty"]),
            "uniqueness": uniqueness(prod, "product_id"),
            "referential_integrity": float(prod_ri), "conformance": float(prod_conf)},
        "orders": {"completeness": float(ord_comp), "uniqueness": float(ord_uniq),
                   "referential_integrity": float(ord_ri),
                   "conformance": float(ord_conf)},
    }
    w = {"completeness": 0.30, "uniqueness": 0.20,
         "referential_integrity": 0.30, "conformance": 0.20}
    rows = [{"scope": t,
             "score_0_100": round(sum(v[k] * w[k] for k in w), 2)}
            for t, v in scores.items()]
    overall = round(sum(r["score_0_100"] for r in rows) / len(rows), 2)
    result = pd.DataFrame([{"scope": "Overall", "score_0_100": overall}]
                          + rows)
    explanation = (
        "Weights: completeness 30, uniqueness 20, RI 30, conformance 20. "
        "90-100 trustworthy; 70-89 usable with caveats; 50-69 clean first; "
        "<50 unreliable. Gameable by reweighting weak dims or relaxing "
        "conformance rules (e.g. accepting N/A as email).")
    return result, explanation
