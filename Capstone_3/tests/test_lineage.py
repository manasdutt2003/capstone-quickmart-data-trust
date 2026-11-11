"""Tests for the row lineage contract (Sprint 3, deliverable 3)."""

import pandas as pd

from src.cleaning import clean_all
from src.deduplication import deduplicate_orders
from src.lineage import (
    REQUIRED_LINEAGE_COLUMNS,
    ensure_lineage,
)
from src.validation_rules import Context, evaluate_all, validate_orders


def _raw_orders():
    return pd.DataFrame([{
        "order_id": "O1", "customer_id": "C1", "product_id": "P1",
        "order_date": "2024-02-01", "quantity": "2", "unit_price_paid": "100",
        "discount": "0", "payment_mode": "UPI", "order_status": "Delivered",
        "delivery_days": "3", "notes": "",
    }, {
        "order_id": "O1", "customer_id": "C1", "product_id": "P1",
        "order_date": "2024-02-01", "quantity": "2", "unit_price_paid": "100",
        "discount": "0", "payment_mode": "UPI", "order_status": "Delivered",
        "delivery_days": "3", "notes": "",
    }])


def _raw_customers():
    return pd.DataFrame([{
        "customer_id": "C1", "customer_name": "A", "email": "a@b.com",
        "city": "Pune", "phone": "9999999999", "signup_date": "2024-01-01",
    }])


def _raw_products():
    return pd.DataFrame([{
        "product_id": "P1", "product_name": "X", "category": "Grocery",
        "unit_price": "100", "stock_qty": "5",
    }])


def _cleaned_orders():
    c, p, o = clean_all(_raw_customers(), _raw_products(), _raw_orders(),
                        {}, {}, {}, {},
                        source_files={"customers": "customers.csv",
                                      "products": "products.csv",
                                      "orders": "orders.csv"})
    return c, p, o


def test_contract_columns_exact():
    assert REQUIRED_LINEAGE_COLUMNS == ("source_file", "source_row_number",
                                        "dedup_rule_applied", "rules_passed",
                                        "rules_failed")


def test_ensure_adds_defaults_without_dropping():
    df = pd.DataFrame([{"a": 1}])
    out = ensure_lineage(df)
    assert list(out.columns) == ["a"] + list(REQUIRED_LINEAGE_COLUMNS)
    assert out.loc[0, "source_file"] == "UNKNOWN"
    assert out.loc[0, "source_row_number"] == -1
    assert out.loc[0, "a"] == 1


def test_ensure_preserves_existing_values():
    df = pd.DataFrame([{"source_file": "orders.csv", "source_row_number": 7,
                        "dedup_rule_applied": "D01", "rules_passed": "R01",
                        "rules_failed": "R05"}])
    out = ensure_lineage(df, source_file="other.csv")
    assert out.loc[0, "source_file"] == "orders.csv"
    assert out.loc[0, "source_row_number"] == 7
    assert out.loc[0, "dedup_rule_applied"] == "D01"


def test_cleaning_attaches_lineage():
    _c, _p, o = _cleaned_orders()
    for col in REQUIRED_LINEAGE_COLUMNS:
        assert col in o.columns
    assert (o["source_file"] == "orders.csv").all()
    assert (o["source_row_number"] == o["_source_row"]).all()


def test_cleaning_stamps_origin_lineage():
    # Cleaning is the origin of lineage: it always stamps source_row_number
    # from _source_row, even if the raw frame carried junk values (raw
    # frames never carry real lineage; _source_row defines row identity).
    raw = _raw_orders()
    raw["source_file"] = "stale.csv"
    raw["source_row_number"] = [10, 11]
    _c, _p, o = clean_all(_raw_customers(), _raw_products(), raw,
                          {}, {}, {}, {},
                          source_files={"orders": "orders.csv"})
    assert (o["source_file"] == "orders.csv").all()
    assert (o["source_row_number"] == o["_source_row"]).all()


def test_dedup_keeps_lineage():
    _c, _p, o = _cleaned_orders()
    clean, _reg = deduplicate_orders(o, {}, {})
    for col in REQUIRED_LINEAGE_COLUMNS:
        assert col in clean.columns
    assert len(clean) == 1  # exact duplicate removed, survivor keeps lineage
    assert clean.iloc[0]["source_file"] == "orders.csv"


def test_validation_keeps_lineage():
    _c, _p, o = _cleaned_orders()
    customers = pd.DataFrame([{"customer_id": "C1",
                               "signup_date": "2024-01-01"}])
    products = pd.DataFrame([{"product_id": "P1", "unit_price": "100"}])
    res = validate_orders(o, customers, products, {}, {}, {}, {})
    for key in ("trusted_orders", "rejected_orders", "warning_orders"):
        for col in REQUIRED_LINEAGE_COLUMNS:
            assert col in res[key].columns


def test_evaluate_all_carries_source_row():
    _c, _p, o = _cleaned_orders()
    ctx = Context(customers=pd.DataFrame(), products=pd.DataFrame(),
                  city_map={}, cat_map={}, pay_map={}, status_map={})
    out = evaluate_all(o, ctx)
    assert set(out["source_row_number"]).issubset(set(o["source_row_number"]))
