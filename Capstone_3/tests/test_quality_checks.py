import pandas as pd

from src.quality_checks import (
    RULE_CATALOG,
    check_customers,
    check_orders,
    check_products,
    run_all_checks,
)


class TestQualityChecks:
    def setup_method(self):
        self.customers = pd.DataFrame({
            "customer_id": ["C001", "C001", "C002", "C003"],
            "customer_name": ["John", "John", "Jane", ""],
            "email": ["john@test.com", "john@test.com", "invalid",
                      "jane@test.com"],
            "city": ["Bengaluru", "BLR", "Chennai", ""],
            "phone": ["1234567890", "123", "0987654321", "NA"],
            "signup_date": ["2023-01-01", "2023-06-15", "unknown",
                            "2023-03-01"],
            "_source_row": [1, 2, 3, 4],
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
            "order_id": ["O001", "O001", "O002", "O003"],
            "customer_id": ["C001", "C001", "C099", "C002"],
            "product_id": ["P001", "P001", "P001", "P999"],
            "order_date": ["2024-01-15", "2024-01-15", "2027-01-01",
                           "2024-02-20"],
            "quantity": ["2", "2", "-1", "3"],
            "unit_price_paid": ["100", "100", "-50", "200"],
            "discount": ["0", "0", "0", "invalid"],
            "payment_mode": ["UPI", "UPI", "", "COD"],
            "order_status": ["Delivered", "Delivered", "MISSING", "Cancelled"],
            "delivery_days": ["2", "2", "45", "0"],
            "notes": ["", "", "", ""],
            "_source_row": [1, 2, 3, 4],
        })

    def test_customer_checks(self):
        checks = check_customers(self.customers)
        assert "QC_CUST_ID_DUP" in checks
        assert checks["QC_CUST_ID_DUP"].sum() == 2
        assert "QC_CUST_EMAIL_INVALID" in checks
        assert checks["QC_CUST_EMAIL_INVALID"].sum() == 1
        assert "QC_CUST_CITY_MISSING" in checks
        assert checks["QC_CUST_CITY_MISSING"].sum() == 1
        assert "QC_CUST_PHONE_INVALID" in checks
        assert checks["QC_CUST_PHONE_INVALID"].sum() == 1
        assert "QC_CUST_SIGNUP_UNPARSEABLE" in checks
        assert checks["QC_CUST_SIGNUP_UNPARSEABLE"].sum() == 1

    def test_product_checks(self):
        checks = check_products(self.products)
        assert "QC_PROD_ID_DUP" in checks
        assert checks["QC_PROD_ID_DUP"].sum() == 2
        assert "QC_PROD_PRICE_INVALID" in checks
        assert checks["QC_PROD_PRICE_INVALID"].sum() == 1
        assert "QC_PROD_STOCK_INVALID" in checks
        assert checks["QC_PROD_STOCK_INVALID"].sum() == 1
        assert "QC_PROD_CAT_MISSING" in checks
        assert checks["QC_PROD_CAT_MISSING"].sum() == 1

    def test_order_checks(self):
        checks = check_orders(self.orders, self.customers, self.products)
        assert "QC_ORD_ID_DUP" in checks
        assert checks["QC_ORD_ID_DUP"].sum() == 2
        assert "QC_ORD_CUST_FK_BROKEN" in checks
        assert checks["QC_ORD_CUST_FK_BROKEN"].sum() == 1
        assert "QC_ORD_PROD_FK_BROKEN" in checks
        assert checks["QC_ORD_PROD_FK_BROKEN"].sum() == 1
        assert "QC_ORD_DATE_FUTURE" in checks
        assert checks["QC_ORD_DATE_FUTURE"].sum() == 1
        assert "QC_ORD_QTY_INVALID" in checks
        assert checks["QC_ORD_QTY_INVALID"].sum() == 1
        assert "QC_ORD_PRICE_INVALID" in checks
        assert checks["QC_ORD_PRICE_INVALID"].sum() == 1
        assert "QC_ORD_STATUS_MISSING" in checks
        assert checks["QC_ORD_STATUS_MISSING"].sum() == 1
        assert "QC_ORD_PAYMENT_MISSING" in checks
        assert checks["QC_ORD_PAYMENT_MISSING"].sum() == 1
        assert "QC_ORD_DELIVERY_INVALID" in checks
        assert checks["QC_ORD_DELIVERY_INVALID"].sum() == 1

    def test_run_all_checks(self):
        checks = run_all_checks(self.customers, self.products, self.orders)
        for rule in ["QC_CUST_ID_DUP", "QC_CUST_NAME_MISSING",
                     "QC_CUST_EMAIL_INVALID", "QC_CUST_CITY_MISSING",
                     "QC_CUST_PHONE_INVALID", "QC_CUST_SIGNUP_UNPARSEABLE",
                     "QC_PROD_ID_DUP", "QC_PROD_NAME_MISSING",
                     "QC_PROD_CAT_MISSING", "QC_PROD_PRICE_INVALID",
                     "QC_PROD_STOCK_INVALID", "QC_ORD_ID_DUP",
                     "QC_ORD_CUST_FK_BROKEN", "QC_ORD_PROD_FK_BROKEN",
                     "QC_ORD_DATE_INVALID", "QC_ORD_DATE_FUTURE",
                     "QC_ORD_QTY_INVALID", "QC_ORD_PRICE_INVALID",
                     "QC_ORD_DISC_INVALID", "QC_ORD_STATUS_MISSING",
                     "QC_ORD_PAYMENT_MISSING", "QC_ORD_DELIVERY_INVALID"]:
            assert rule in checks, f"Missing rule: {rule}"

    def test_rule_catalog_completeness(self):
        rule_ids = {r["rule_id"] for r in RULE_CATALOG}
        assert len(rule_ids) == 22
        assert "QC_ORD_ID_DUP" in rule_ids

    def test_rule_catalog_fields(self):
        for rule in RULE_CATALOG:
            assert "rule_id" in rule
            assert "table" in rule
            assert "column" in rule
            assert "predicate" in rule
            assert "treatment" in rule
            assert rule["treatment"] in ["QUARANTINE", "NORMALISE", "COUNT"]
from src.profiling import profile_table
from src.quality_checks import quality_fail_masks


def _frames():
    c = pd.DataFrame([{"customer_id": "C1", "customer_name": "A", "email": "a@b.com",
                       "city": "Pune", "phone": "9999999999", "signup_date": "2024-01-01"}])
    p = pd.DataFrame([{"product_id": "P1", "product_name": "X", "category": "Grocery",
                       "unit_price": "100", "stock_qty": "10"}])
    o = pd.DataFrame([{"order_id": "O1", "customer_id": "C1", "product_id": "P1",
                       "order_date": "2024-02-01", "quantity": "2", "unit_price_paid": "100",
                       "discount": "0", "payment_mode": "UPI", "order_status": "Delivered",
                       "delivery_days": "3", "notes": "ok"}])
    return c, p, o


def test_profile_sums():
    _c, _p, o = _frames()
    prof = profile_table(o, "orders")
    row = prof[prof["column"] == "quantity"].iloc[0]
    assert row["missing"] + row["usable"] == row["rows"]


def test_clean_row_has_no_fails():
    c, p, o = _frames()
    masks = quality_fail_masks(c, p, o, "2026-10-11")
    assert all(int(m.sum()) == 0 for m in masks.values())


def test_broken_fk_and_future_flagged():
    c, p, o = _frames()
    o.loc[0, "customer_id"] = "GHOST"
    o.loc[0, "order_date"] = "2027-01-01"
    masks = quality_fail_masks(c, p, o, "2026-10-11")
    assert bool(masks["QC_ORD_CUST_FK_BROKEN"].iloc[0])
    assert bool(masks["QC_ORD_DATE_FUTURE"].iloc[0])
