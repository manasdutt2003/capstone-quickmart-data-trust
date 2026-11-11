import pandas as pd

from src.validation_rules import evaluate


def _setup(status="Delivered", pay="UPI", qty="2", date="2024-02-01", dd="3"):
    c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2024-01-01"}])
    p = pd.DataFrame([{"product_id": "P1", "unit_price": "100"}])
    o = pd.DataFrame([{"order_id": "O1", "customer_id": "C1",
                       "product_id": "P1", "order_date": date,
                       "quantity": qty, "unit_price_paid": "100",
                       "discount": "0", "payment_mode": pay,
                       "order_status": status, "delivery_days": dd,
                       "notes": ""}])
    return o, c, p


def test_happy_path_passes():
    o, c, p = _setup()
    _v, fail, lv = evaluate(o, c, p, pd.Series(["Delivered"], index=o.index),
                            pd.Series(["UPI"], index=o.index), "2026-10-11")
    assert not bool(fail.iloc[0])
    assert float(lv.iloc[0]) == 200.0


def test_boundary_and_negative():
    o, c, p = _setup(qty="0")
    _, fail, _ = evaluate(o, c, p, pd.Series(["Delivered"], index=o.index),
                          pd.Series(["UPI"], index=o.index), "2026-10-11")
    assert bool(fail.iloc[0])
    o2, _, _ = _setup(qty="100")
    _, fail2, _ = evaluate(o2, c, p, pd.Series(["Delivered"], index=o2.index),
                           pd.Series(["UPI"], index=o2.index), "2026-10-11")
    assert not bool(fail2.iloc[0])


def test_referential_and_business_rules():
    o, c, p = _setup(date="2023-01-01")
    v, fail, _ = evaluate(o, c, p, pd.Series(["Delivered"], index=o.index),
                          pd.Series(["UPI"], index=o.index), "2026-10-11")
    assert v.loc[o.index[0], "R03"] == False
    assert bool(fail.iloc[0])


def _pop_orders():
    rows = [
        {"order_id": "O1", "customer_id": "C1", "product_id": "P1",
         "order_date": "2024-02-01", "quantity": "2",
         "unit_price_paid": "100", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3", "notes": "ok"},
        {"order_id": "O2", "customer_id": "GHOST", "product_id": "P1",
         "order_date": "2024-02-01", "quantity": "2",
         "unit_price_paid": "100", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3", "notes": "ok"},
        {"order_id": "O3", "customer_id": "C1", "product_id": "P1",
         "order_date": "2024-02-01", "quantity": "2",
         "unit_price_paid": "100", "discount": "0", "payment_mode": "UNMAPPED",
         "order_status": "Delivered", "delivery_days": "3", "notes": "ok"},
        {"order_id": "O4", "customer_id": "C1", "product_id": "P1",
         "order_date": "2024-02-01", "quantity": "0",
         "unit_price_paid": "100", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3", "notes": "ok"},
    ]
    df = pd.DataFrame(rows)
    df["_source_row"] = [1, 2, 3, 4]
    df["source_file"] = "orders.csv"
    df["source_row_number"] = [1, 2, 3, 4]
    df["dedup_rule_applied"] = ""
    df["rules_passed"] = ""
    df["rules_failed"] = ""
    for col in list(df.columns):
        if not col.startswith("raw_") and col not in (
                "_source_row", "source_file", "source_row_number",
                "dedup_rule_applied", "rules_passed", "rules_failed"):
            df[f"raw_{col}"] = df[col]
    return df


def _pop_ctx():
    from src.validation_rules import Context
    customers = pd.DataFrame([{"customer_id": "C1", "city": "Pune",
                               "signup_date": "2024-01-01"}])
    products = pd.DataFrame([{"product_id": "P1", "category": "Grocery",
                              "unit_price": "100", "stock_qty": "10"}])
    return Context(customers=customers, products=products,
                   city_map={"Pune": "Pune"}, cat_map={"Grocery": "Grocery"},
                   pay_map={"UPI": "UPI", "UNMAPPED": "UNMAPPED"},
                   status_map={"Delivered": "Delivered"})


def _populations():
    from src.trusted import build_populations
    orders = _pop_orders()
    return build_populations(orders, _pop_ctx()), orders


class TestPopulations:
    def test_closure_total(self):
        pops, orders = _populations()
        got = set(pops["trusted"]["source_row_number"].astype(str))
        want = set(orders["source_row_number"].astype(str))
        dropped = set(pops["rejected"]["source_row_number"].astype(str))
        assert got | dropped == want
        assert got & dropped == set()

    def test_recommended_is_lenient(self):
        pops, _orders = _populations()
        pd.testing.assert_frame_equal(pops["trusted"], pops["lenient"])
        assert len(pops["trusted"]) == 2  # O1 clean, O3 warning-only
        assert len(pops["rejected"]) == 2  # O2 R01, O4 R05
        assert len(pops["strict"]) == 1  # O1 only

    def test_rejected_have_failed_rule(self):
        pops, _orders = _populations()
        assert (pops["rejected"]["failed_rule_ids"] != "").all()
        log = pops["rule_failure_log"]
        for _, row in pops["rejected"].iterrows():
            assert row["source_row_number"] in set(log["source_row_number"])

    def test_strict_subset_chain(self):
        pops, _orders = _populations()
        s_strict = set(pops["strict"]["source_row_number"])
        s_lenient = set(pops["lenient"]["source_row_number"])
        assert s_strict <= s_lenient

    def test_lineage_present_on_all_outputs(self):
        from src.lineage import REQUIRED_LINEAGE_COLUMNS
        pops, _orders = _populations()
        for key in ("strict", "lenient", "trusted", "rejected"):
            for col in REQUIRED_LINEAGE_COLUMNS:
                assert col in pops[key].columns

    def test_determinism_same_sha(self):
        import hashlib

        from src.trusted import build_populations, population_csv_text
        orders = _pop_orders()
        ctx = _pop_ctx()
        first = build_populations(orders, ctx)
        shuffled = orders.sample(frac=1, random_state=3)
        second = build_populations(shuffled, ctx)
        for key in ("strict", "lenient", "trusted", "rejected",
                    "rule_failure_log"):
            h1 = hashlib.sha256(
                population_csv_text(first[key]).encode("utf-8")).hexdigest()
            h2 = hashlib.sha256(
                population_csv_text(second[key]).encode("utf-8")).hexdigest()
            assert h1 == h2

    def test_reconciliation_closes(self):
        from src.reconcile import reconcile
        pops, orders = _populations()
        ctx = _pop_ctx()
        rec = reconcile(orders, pops, pops["eval_long"], ctx.customers,
                        ctx.products, ctx, len(orders), len(orders))
        assert len(rec["waterfall"]) > 0
        assert (rec["join_log"]["dropped"] == 0).all()

    def test_waterfall_reconciles(self):
        pops, orders = _populations()
        from src.trusted import build_waterfall
        table = build_waterfall(len(orders), len(orders), orders,
                                pops["eval_long"], pops["strict"],
                                pops["lenient"])
        rule_rows = table[table["stage"].str.startswith("R")]
        assert int(rule_rows["rows_removed"].sum()) == \
            len(orders) - len(pops["trusted"])

    def test_pii_absent_from_outputs(self):
        from pathlib import Path

        from src.llm_reporting import PII_PATTERNS
        root = Path(__file__).resolve().parents[1]
        for name in ("trusted_orders.csv", "rejected_orders.csv",
                     "rule_failure_log.csv", "strict_trusted_orders.csv",
                     "lenient_trusted_orders.csv"):
            text = (root / "outputs" / name).read_text(encoding="utf-8")
            header = text.splitlines()[0].split(",")
            for banned in ("customer_name", "email", "phone"):
                assert banned not in header
            for pat in PII_PATTERNS:
                assert not pat.search(text), f"PII pattern in {name}"