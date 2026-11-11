import pandas as pd

from src.issue_registry import (
    build_issue_registry,
    build_quality_datamart,
    build_quality_scorecard,
)
from src.quality_checks import RULE_CATALOG, run_all_checks


class TestIssueRegistry:
    def setup_method(self):
        self.customers = pd.DataFrame({
            "customer_id": ["C001", "C001", "C002"],
            "customer_name": ["John", "John", "Jane"],
            "email": ["john@test.com", "john@test.com", "invalid"],
            "city": ["Bengaluru", "BLR", "Chennai"],
            "phone": ["1234567890", "123", "0987654321"],
            "signup_date": ["2023-01-01", "2023-06-15", "unknown"],
            "_source_row": [1, 2, 3],
        })
        self.products = pd.DataFrame({
            "product_id": ["P001", "P001", "P002"],
            "product_name": ["Widget", "Widget", "Gadget"],
            "category": ["Gadgets", "Gadgets", ""],
            "unit_price": ["100", "NA", "200"],
            "stock_qty": ["10", "-5", "5"],
            "_source_row": [1, 2, 3],
        })
        self.orders = pd.DataFrame({
            "order_id": ["O001", "O001", "O002"],
            "customer_id": ["C001", "C001", "C099"],
            "product_id": ["P001", "P001", "P001"],
            "order_date": ["2024-01-15", "2024-01-15", "2027-01-01"],
            "quantity": ["2", "2", "3"],
            "unit_price_paid": ["100", "100", "200"],
            "discount": ["0", "0", "0"],
            "payment_mode": ["UPI", "UPI", ""],
            "order_status": ["Delivered", "Delivered", "MISSING"],
            "delivery_days": ["2", "2", "5"],
            "notes": ["", "", ""],
            "_source_row": [1, 2, 3],
        })
        self.checks = run_all_checks(self.customers, self.products,
                                     self.orders)

    def test_build_issue_registry(self):
        registry = build_issue_registry(self.checks, RULE_CATALOG)
        assert isinstance(registry, pd.DataFrame)
        assert len(registry) == len(RULE_CATALOG)
        for col in ["rule_id", "table", "column", "predicate", "fail_count",
                    "treatment", "pass_count"]:
            assert col in registry.columns
        cust_dup = registry[registry["rule_id"] == "QC_CUST_ID_DUP"].iloc[0]
        assert cust_dup["fail_count"] == 2
        assert cust_dup["treatment"] == "QUARANTINE"

    def test_registry_has_all_rules(self):
        registry = build_issue_registry(self.checks, RULE_CATALOG)
        assert set(registry["rule_id"]) == {r["rule_id"] for r in RULE_CATALOG}

    def test_registry_treatments_valid(self):
        registry = build_issue_registry(self.checks, RULE_CATALOG)
        assert set(registry["treatment"]).issubset({"QUARANTINE", "NORMALISE",
                                                    "COUNT"})

    def test_registry_columns(self):
        registry = build_issue_registry(self.checks, RULE_CATALOG)
        assert (registry["count"] >= 0).all()
        assert (registry["treatment"] != "").all()


class TestQualityDatamart:
    def setup_method(self):
        self.customers = pd.DataFrame({
            "customer_id": ["C001", "C002"],
            "customer_name": ["John", "Jane"],
            "email": ["john@test.com", "jane@test.com"],
            "city": ["Bengaluru", "Chennai"],
            "phone": ["1234567890", "0987654321"],
            "signup_date": ["2023-01-01", "2023-06-15"],
            "_source_row": [1, 2],
        })
        self.products = pd.DataFrame({
            "product_id": ["P001", "P002"],
            "product_name": ["Widget", "Gadget"],
            "category": ["Gadgets", "Tools"],
            "unit_price": [100.0, 200.0],
            "stock_qty": [10, 5],
            "_source_row": [1, 2],
        })
        self.orders = pd.DataFrame({
            "order_id": ["O001", "O002", "O003"],
            "customer_id": ["C001", "C001", "C002"],
            "product_id": ["P001", "P001", "P002"],
            "order_date": ["2024-01-15", "2024-01-15", "2024-02-20"],
            "quantity": [2, 2, 3],
            "unit_price_paid": [100.0, 100.0, 200.0],
            "discount": [0.0, 0.0, 0.0],
            "payment_mode": ["UPI", "UPI", "COD"],
            "order_status": ["Delivered", "Delivered", "Cancelled"],
            "delivery_days": [2, 2, 0],
            "notes": ["", "", ""],
            "_source_row": [1, 2, 3],
        })
        self.city_map = {"Bengaluru": "Bengaluru", "Chennai": "Chennai"}
        self.cat_map = {"Gadgets": "Gadgets", "Tools": "Tools"}
        self.pay_map = {"UPI": "UPI", "COD": "COD"}
        self.status_map = {"Delivered": "Delivered",
                           "Cancelled": "Cancelled"}
        self.checks = run_all_checks(self.customers, self.products,
                                     self.orders)

    def test_quality_datamart_columns(self):
        dm = build_quality_datamart(self.orders, self.checks, self.customers,
                                    self.products, self.city_map,
                                    self.cat_map, self.pay_map,
                                    self.status_map)
        for col in ["order_month", "city_std", "category_std", "payment_std",
                    "status_std", "n_issues", "is_broken_fk", "is_dup_id"]:
            assert col in dm.columns
        for rule_id in ["QC_ORD_ID_DUP", "QC_ORD_CUST_FK_BROKEN",
                        "QC_ORD_PROD_FK_BROKEN", "QC_ORD_DATE_INVALID",
                        "QC_ORD_DATE_FUTURE", "QC_ORD_QTY_INVALID",
                        "QC_ORD_PRICE_INVALID", "QC_ORD_DISC_INVALID",
                        "QC_ORD_STATUS_MISSING", "QC_ORD_PAYMENT_MISSING",
                        "QC_ORD_DELIVERY_INVALID"]:
            assert (f"flag_{rule_id}") in dm.columns

    def test_quality_datamart_values(self):
        dm = build_quality_datamart(self.orders, self.checks, self.customers,
                                    self.products, self.city_map,
                                    self.cat_map, self.pay_map,
                                    self.status_map)
        assert len(dm) == 3
        assert dm["n_issues"].sum() >= 0
        assert dm["is_broken_fk"].sum() == 0
        assert dm["is_dup_id"].sum() == 0

    def test_city_standardization(self):
        dm = build_quality_datamart(self.orders, self.checks, self.customers,
                                    self.products, self.city_map,
                                    self.cat_map, self.pay_map,
                                    self.status_map)
        assert "Bengaluru" in dm["city_std"].values
        assert "Chennai" in dm["city_std"].values

    def test_profile_sums(self):
        from src.profiling import profile_table
        prof = profile_table(self.orders, "orders")
        row = prof[prof["column"] == "quantity"].iloc[0]
        assert row["missing"] + row["usable"] == row["rows"]

    def test_broken_fk_and_future_flagged(self):
        orders = self.orders.copy()
        orders.loc[0, "customer_id"] = "GHOST"
        orders.loc[0, "order_date"] = "2027-01-01"
        masks = run_all_checks(self.customers, self.products, orders)
        assert bool(masks["QC_ORD_CUST_FK_BROKEN"].iloc[0])
        assert bool(masks["QC_ORD_DATE_FUTURE"].iloc[0])


class TestQualityScorecard:
    def setup_method(self):
        self.customers = pd.DataFrame({
            "customer_id": ["C001", "C001", "C002"],
            "customer_name": ["John", "John", "Jane"],
            "email": ["john@test.com", "john@test.com", "invalid"],
            "city": ["Bengaluru", "BLR", "Chennai"],
            "phone": ["1234567890", "123", "0987654321"],
            "signup_date": ["2023-01-01", "2023-06-15", "unknown"],
            "_source_row": [1, 2, 3],
        })
        self.products = pd.DataFrame({
            "product_id": ["P001", "P001", "P002"],
            "product_name": ["Widget", "Widget", "Gadget"],
            "category": ["Gadgets", "Gadgets", ""],
            "unit_price": ["100", "NA", "200"],
            "stock_qty": ["10", "-5", "5"],
            "_source_row": [1, 2, 3],
        })
        self.orders = pd.DataFrame({
            "order_id": ["O001", "O001", "O002"],
            "customer_id": ["C001", "C001", "C099"],
            "product_id": ["P001", "P001", "P001"],
            "order_date": ["2024-01-15", "2024-01-15", "2027-01-01"],
            "quantity": ["2", "2", "3"],
            "unit_price_paid": ["100", "100", "200"],
            "discount": ["0", "0", "0"],
            "payment_mode": ["UPI", "UPI", ""],
            "order_status": ["Delivered", "Delivered", "MISSING"],
            "delivery_days": ["2", "2", "5"],
            "notes": ["", "", ""],
            "_source_row": [1, 2, 3],
        })
        self.checks = run_all_checks(self.customers, self.products,
                                     self.orders)

    def test_scorecard_structure(self):
        scorecard = build_quality_scorecard(self.customers, self.products,
                                            self.orders, self.checks)
        assert isinstance(scorecard, pd.DataFrame)
        assert len(scorecard) == 3
        for col in ["table", "rows", "columns", "total_cells", "checks_run",
                    "failed_cells", "quality_score_pct"]:
            assert col in scorecard.columns

    def test_scorecard_values(self):
        scorecard = build_quality_scorecard(self.customers, self.products,
                                            self.orders, self.checks)
        for _, row in scorecard.iterrows():
            assert 0 <= row["quality_score_pct"] <= 100
            assert row["rows"] > 0
            assert row["checks_run"] > 0


def test_registry_columns():
    c = pd.DataFrame([{"customer_id": "C1", "customer_name": "A", "email": "bad",
                       "city": "", "phone": "123", "signup_date": "unknown"}])
    p = pd.DataFrame([{"product_id": "P1", "product_name": "X", "category": "",
                       "unit_price": "NA", "stock_qty": "-5"}])
    o = pd.DataFrame([{"order_id": "O1", "customer_id": "ZZ", "product_id": "QQ",
                       "order_date": "bad", "quantity": "0", "unit_price_paid": "",
                       "discount": "junk", "payment_mode": "", "order_status": "",
                       "delivery_days": "45", "notes": ""}])
    checks = run_all_checks(c, p, o, "2026-10-11")
    reg = build_issue_registry(checks, RULE_CATALOG)
    assert {"extract", "column", "count", "treatment", "reason"}.issubset(reg.columns)
    assert (reg["count"] >= 0).all()
    assert (reg["treatment"] != "").all()
