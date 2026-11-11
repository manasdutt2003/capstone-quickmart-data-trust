"""Segment 8 answers (Q76-Q77): expert SQL engineering.

Q76/Q77 are mechanism questions answered by proof/counterexample on the
extracts (plus a crafted tie where the extracts cannot exhibit the
mechanism). Each function mirrors its sql/questions/seg8_qNN.sql twin.
Methods and trade-offs live in docs/answers_segment8_9.md.
"""

import pandas as pd


def q76_lateral_equivalence():
    """Q76: LATERAL latest-payment vs window/DISTINCT ON under ties.

    Counterexample: two rows tie on (order_id, order_date) with
    different payment_mode. A LATERAL ... LIMIT 1 with no ORDER BY is
    arbitrary on the tie; DISTINCT ON with ORDER BY payment_mode and
    ROW_NUMBER with the same ordering both pick deterministically and
    agree. Equivalence holds iff the ordering is total.
    """
    tied = pd.DataFrame([
        {"order_id": "O-TIE", "order_date": "2024-01-01",
         "payment_mode": "UPI"},
        {"order_id": "O-TIE", "order_date": "2024-01-01",
         "payment_mode": "COD"},
    ])
    distinct_on_pick = min(tied["payment_mode"].tolist())
    ranked = tied.sort_values("payment_mode").reset_index(drop=True)
    window_pick = ranked.loc[0, "payment_mode"]
    result = pd.DataFrame([{
        "finding": "counterexample: two rows tie on (order_id, order_date)",
        "distinct_on_pick": distinct_on_pick,
        "window_pick": window_pick,
        "agree_with_tiebreak": bool(distinct_on_pick == window_pick),
        "rule": ("LATERAL ... LIMIT 1 with no ORDER BY is arbitrary on "
                 "ties - add ORDER BY payment_mode to make all three "
                 "equivalent"),
    }])
    explanation = (
        "PROOF BY COUNTEREXAMPLE: on the tied pair, DISTINCT ON "
        "(ORDER BY payment_mode) and ROW_NUMBER (same ordering) both pick "
        "COD deterministically and agree; a LATERAL LIMIT 1 without ORDER "
        "BY may return either row, so the rewrite is NOT equivalent under "
        "ties. It becomes equivalent iff the ORDER BY is total "
        "(unique key last, e.g. order_id COLLATE C). Past the size "
        "threshold the planner switches the LATERAL to a hashed/merged "
        "per-group scan, which surfaces the arbitrariness.")
    return result, explanation


def q77_float_sum_order(trusted, customers, products, ctx):
    """Q77: float money sums in ascending vs descending order_id order.

    Sums line_value::float8 per city in both accumulation orders and
    reports the cent-level difference. Order-independence comes from
    NUMERIC accumulation (exact decimal), a pre-sort, or math.fsum.
    """
    from .seg6_advanced_sql import _delivered, _enriched

    base = _delivered(_enriched(trusted, customers, products, ctx))
    rows = []
    for city, grp in base.groupby("city_std"):
        asc = grp.sort_values("order_id")["line_value"].tolist()
        desc = grp.sort_values("order_id", ascending=False)["line_value"].tolist()
        s_asc, s_desc = 0.0, 0.0
        for v in asc:
            s_asc += float(v)
        for v in desc:
            s_desc += float(v)
        diff = abs(s_asc - s_desc)
        rows.append({"city_std": city,
                     "sum_asc": round(s_asc, 2),
                     "sum_desc": round(s_desc, 2),
                     "diff": round(diff, 2),
                     "differs_at_cent": bool(round(diff, 2) >= 0.01)})
    result = pd.DataFrame(rows).sort_values("city_std").reset_index(drop=True)
    explanation = (
        "Binary floating point addition is commutative but NOT associative: "
        "accumulation order changes rounding. Fix = NUMERIC or pre-sort "
        "(order-independent, costs sort + slower exact arithmetic) or "
        "math.fsum (exact-ish, still binary, slower). Crafted proof: "
        "(0.1+0.2)+0.3 = 0.6000000000000001 vs 0.1+(0.2+0.3) = 0.6.")
    return result, explanation
