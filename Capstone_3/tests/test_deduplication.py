import pandas as pd

from src.deduplication import (
    RULE_CATALOG,
    apply_all_dedup,
    build_customer_master,
    count_before_after_normalising,
    deduplicate_orders,
    deduplicate_products,
    find_exact_duplicates,
    flag_near_duplicates,
    resolve_order_id_conflicts,
)


def _orders():
    base = {"order_id": "O1", "customer_id": "C1", "product_id": "P1", "order_date": "2024-02-01",
            "quantity": "2", "unit_price_paid": "100", "discount": "0", "payment_mode": "UPI",
            "order_status": "Delivered", "delivery_days": "3", "notes": "ok"}
    return pd.DataFrame([base, dict(base), dict(base, order_status="Cancelled")])


def test_exact_and_conflict_removed():
    o = _orders()
    st = pd.Series(["Delivered", "Delivered", "Cancelled"], index=o.index)
    clean, reg = deduplicate_orders(o, st, {})
    assert len(clean) == 1  # D01 removes copy, D02 keeps priority survivor
    assert set(reg["rule_id"]).issubset({"D01", "D02", "D05"})


def test_deterministic_rerun():
    o = _orders()
    st = pd.Series(["Delivered", "Delivered", "Cancelled"], index=o.index)
    c1, _ = deduplicate_orders(o, st, {})
    c2, _ = deduplicate_orders(o.sample(frac=1, random_state=1), st, {})
    assert sorted(c1["order_status"]) == sorted(c2["order_status"])


def test_customer_fuzzy_merge():
    c = pd.DataFrame([
        {"customer_id": "C1", "customer_name": "A", "email": "A@b.com", "city": "Pune",
         "phone": "9999999999", "signup_date": "2024-01-01"},
        {"customer_id": "C2", "customer_name": "A", "email": " a@B.com ", "city": "Pune",
         "phone": "9999999999", "signup_date": "2024-06-01"},
        {"customer_id": "C3", "customer_name": "B", "email": "NA", "city": "Pune",
         "phone": "", "signup_date": "2024-01-01"},
    ])
    master, _reg, remap = build_customer_master(c)
    assert len(master) == 2  # placeholders never merge
    assert remap.get("C2") == "C1"


class TestProductDeduplication:
    def test_same_product_different_id_format_merged(self):
        df = pd.DataFrame({
            "product_id": ["P01", "p01", "P-01"],
            "product_name": ["Widget", "Widget", "Widget"],
            "category": ["Gadgets", "Gadgets", "Gadgets"],
            "unit_price": ["100", "100", "100"],
            "stock_qty": ["10", "10", "10"],
            "_source_row": [1, 2, 3],
        })
        master, registry = deduplicate_products(df)
        assert len(master) == 1
        assert len(registry) == 2
        assert set(registry["rule_id"]) == {"D04"}

    def test_different_products_same_norm_id_not_merged(self):
        df = pd.DataFrame({
            "product_id": ["P01", "P01"],
            "product_name": ["Widget A", "Widget B"],
            "category": ["Gadgets", "Tools"],
            "unit_price": ["100", "200"],
            "stock_qty": ["10", "5"],
            "_source_row": [1, 2],
        })
        master, registry = deduplicate_products(df)
        assert len(master) == 2
        assert (registry["loser_key"] == "CONFLICT").any()


class TestNearDuplicates:
    def test_near_duplicates_flagged_not_removed(self):
        df = pd.DataFrame({
            "customer_id": ["C1", "C2"],
            "customer_name": ["Suresh Reddy", "Suresh  Reddy"],
            "city": ["Pune", "Pune"],
            "_source_row": [1, 2],
        })
        flags = flag_near_duplicates(df, threshold=0.9)
        assert len(flags) == 1
        assert flags.iloc[0]["rule_id"] == "D06"

    def test_distinct_names_not_flagged(self):
        df = pd.DataFrame({
            "customer_id": ["C1", "C2"],
            "customer_name": ["Suresh Reddy", "Anita Desai"],
            "city": ["Pune", "Chennai"],
            "_source_row": [1, 2],
        })
        assert len(flag_near_duplicates(df, threshold=0.9)) == 0


class TestNormalisationCounts:
    def test_counts_before_and_after_normalising(self):
        from src.normalise import norm_email
        s = pd.Series(["A@B.com", " a@b.com ", "NA", "c@d.com"])
        counts = count_before_after_normalising(s, norm_email)
        assert counts["distinct_before"] == 4
        assert counts["distinct_after"] == 3
        assert counts["rows_changed_by_normalisation"] == 3
        assert counts["removals_reconcile"] is True


class TestOrderLineDuplicates:
    def test_line_key_needs_all_fields(self):
        orders = pd.DataFrame({
            "order_id": ["O1", "O2"],
            "customer_id": ["C1", "C1"],
            "product_id": ["P1", "P1"],
            "order_date": ["2024-02-01", "2024-02-01"],
            "quantity": ["2", "3"],
            "unit_price_paid": ["100", "100"],
            "discount": ["0", "0"],
            "payment_mode": ["UPI", "UPI"],
            "order_status": ["Delivered", "Delivered"],
            "delivery_days": ["3", "3"],
            "notes": ["ok", "ok"],
        })
        clean, reg = deduplicate_orders(orders, {})
        assert len(clean) == 2
        assert len(reg) == 0


class TestFullPipeline:
    def test_apply_all_dedup_returns_all_outputs(self):
        customers = pd.DataFrame({
            "customer_id": ["C001", "C002"],
            "customer_name": ["John", "John"],
            "email": ["john@test.com", "john@test.com"],
            "city": ["Bengaluru", "Bengaluru"],
            "phone": ["111", "222"],
            "signup_date": ["2023-01-01", "2023-06-01"],
            "_source_row": [1, 2],
        })
        products = pd.DataFrame({
            "product_id": ["P01", "p01"],
            "product_name": ["Widget", "Widget"],
            "category": ["Gadgets", "Gadgets"],
            "unit_price": ["100", "100"],
            "stock_qty": ["10", "10"],
            "_source_row": [1, 2],
        })
        orders = pd.DataFrame({
            "order_id": ["O001", "O001"],
            "customer_id": ["C002", "C002"],
            "product_id": ["p01", "p01"],
            "order_date": ["2024-01-01", "2024-01-01"],
            "quantity": ["2", "2"],
            "unit_price_paid": ["100", "100"],
            "discount": ["0", "0"],
            "payment_mode": ["UPI", "UPI"],
            "order_status": ["Delivered", "Delivered"],
            "delivery_days": ["2", "2"],
            "notes": ["", ""],
            "_source_row": [1, 2],
        })
        result = apply_all_dedup(customers, products, orders)
        for key in ["customer_master", "product_master", "clean_orders",
                    "duplicate_registry", "id_remap"]:
            assert key in result
        assert len(result["customer_master"]) == 1
        assert len(result["product_master"]) == 1
        assert len(result["clean_orders"]) == 1
        assert len(result["duplicate_registry"]) > 0


class TestRuleCatalog:
    def test_all_rules_present(self):
        assert {r.rule_id for r in RULE_CATALOG} == \
            {"D01", "D02", "D03", "D04", "D05", "D06"}

    def test_all_rules_have_required_fields(self):
        for rule in RULE_CATALOG:
            d = rule.as_dict()
            for field in ["rule_id", "name", "description", "rationale",
                          "detection_logic", "edge_cases", "example",
                          "removal_strategy", "entity"]:
                assert field in d
            assert isinstance(d["edge_cases"], list)

    def test_find_exact_duplicates(self):
        assert int(find_exact_duplicates(_orders()).sum()) >= 1

    def test_resolve_conflicts_deterministic(self):
        o = _orders()
        st = pd.Series(["Delivered", "Delivered", "Cancelled"],
                       index=o.index)
        assert resolve_order_id_conflicts(o, st).sum() == 1