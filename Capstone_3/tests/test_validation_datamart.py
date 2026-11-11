"""Tests for the validation datamart, co-occurrence and concentration."""

import pandas as pd

from src.dimensions import DIMENSIONS, enrich_dimensions
from src.validation_datamart import (
    build_validation_datamart,
    concentration,
    cooccurrence,
)
from src.validation_rules import Context, evaluate_all


def _ctx():
    customers = pd.DataFrame([
        {"customer_id": "C1", "city": "Pune", "signup_date": "2024-01-01"},
        {"customer_id": "C2", "city": "Chennai", "signup_date": "2024-01-01"},
    ])
    products = pd.DataFrame([
        {"product_id": "P1", "category": "Grocery", "unit_price": "100",
         "stock_qty": "10"},
        {"product_id": "P2", "category": "Snacks", "unit_price": "50",
         "stock_qty": "10"},
    ])
    return Context(customers=customers, products=products,
                   city_map={"Pune": "Pune", "Chennai": "Chennai"},
                   cat_map={"Grocery": "Grocery", "Snacks": "Snacks"},
                   pay_map={"UPI": "UPI"}, status_map={})


def _orders():
    rows = [
        {"order_id": "O1", "customer_id": "C1", "product_id": "P1",
         "order_date": "2024-02-01", "quantity": "2",
         "unit_price_paid": "100", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3", "notes": "ok"},
        {"order_id": "O2", "customer_id": "GHOST", "product_id": "P1",
         "order_date": "2024-02-01", "quantity": "1",
         "unit_price_paid": "50", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "2", "notes": "ok"},
        {"order_id": "O3", "customer_id": "C2", "product_id": "P2",
         "order_date": "2024-03-01", "quantity": "3",
         "unit_price_paid": "50", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "1", "notes": "ok"},
    ]
    df = pd.DataFrame(rows)
    df["_source_row"] = [1, 2, 3]
    df["source_file"] = "orders.csv"
    df["source_row_number"] = [1, 2, 3]
    df["dedup_rule_applied"] = ""
    df["rules_passed"] = ""
    df["rules_failed"] = ""
    for col in list(df.columns):
        if not col.startswith("raw_") and col not in (
                "_source_row", "source_file", "source_row_number",
                "dedup_rule_applied", "rules_passed", "rules_failed"):
            df[f"raw_{col}"] = df[col]
    return df


def _mart():
    orders = _orders()
    ctx = _ctx()
    long_ = evaluate_all(orders, ctx)
    mart = build_validation_datamart(orders, long_, ctx.customers,
                                     ctx.products, ctx)
    return orders, ctx, long_, mart


def test_grain_is_rule_x_dimension_x_value():
    _orders_df, _ctx, _long, mart = _mart()
    assert list(mart.columns) == ["rule_id", "dimension", "dimension_value",
                                  "failing_orders", "value_removed"]
    assert not mart.duplicated(
        subset=["rule_id", "dimension", "dimension_value"]).any()


def test_splits_sum_to_rule_totals():
    _orders_df, _ctx, long_, mart = _mart()
    failing = long_[long_["result"] != "PASS"]
    for rule in failing["rule_id"].unique():
        total = int((failing["rule_id"] == rule).sum())
        for dim in DIMENSIONS:
            split = mart[(mart["rule_id"] == rule)
                         & (mart["dimension"] == dim)]["failing_orders"].sum()
            assert int(split) == total, (rule, dim)


def test_unmatched_bucket_present():
    _orders_df, _ctx, _long, mart = _mart()
    city_rows = mart[(mart["dimension"] == "city")]
    assert "UNMATCHED" in set(city_rows["dimension_value"])


def test_value_removed_uses_single_line_value():
    _orders_df, _ctx, _long, mart = _mart()
    # O2 (GHOST) fails R01 with line value 1*50 = 50.0 in UNMATCHED city.
    row = mart[(mart["rule_id"] == "R01")
               & (mart["dimension"] == "city")
               & (mart["dimension_value"] == "UNMATCHED")]
    assert len(row) == 1
    assert int(row.iloc[0]["failing_orders"]) == 1
    assert float(row.iloc[0]["value_removed"]) == 50.0


def test_cooccurrence_diagonal_symmetry_lift():
    long_ = pd.DataFrame([
        {"source_row_number": 1, "rule_id": "R01", "result": "FAIL",
         "failing_detail": "x"},
        {"source_row_number": 2, "rule_id": "R01", "result": "FAIL",
         "failing_detail": "x"},
        {"source_row_number": 1, "rule_id": "R02", "result": "FAIL",
         "failing_detail": "x"},
        {"source_row_number": 2, "rule_id": "R02", "result": "FAIL",
         "failing_detail": "x"},
        {"source_row_number": 3, "rule_id": "R03", "result": "FAIL",
         "failing_detail": "x"},
        {"source_row_number": 4, "rule_id": "R03", "result": "PASS",
         "failing_detail": ""},
    ])
    joint, lift = cooccurrence(long_)
    assert joint.loc["R01", "R01"] == 2
    assert joint.loc["R03", "R03"] == 1
    assert joint.loc["R01", "R02"] == joint.loc["R02", "R01"] == 2
    assert lift.loc["R01", "R02"] == 2.0
    assert lift.loc["R01", "R03"] == 0.0


def test_concentration_thresholds():
    dims = pd.DataFrame({
        "source_row_number": list(range(1, 101)),
        "city": ["A"] * 40 + ["B"] * 60,
    })
    failing = list(range(1, 31)) + list(range(41, 51))
    out = concentration(failing, dims, "city")
    by_val = {r["dimension_value"]: r for _, r in out.iterrows()}
    assert by_val["A"]["flagged"] == True
    assert by_val["A"]["ratio"] == 1.88 or by_val["A"]["ratio"] == 1.87
    assert by_val["B"]["flagged"] == False


def test_concentration_min_rows_gate():
    dims = pd.DataFrame({
        "source_row_number": list(range(1, 101)),
        "city": ["C"] * 5 + ["D"] * 95,
    })
    out = concentration([1, 2, 3, 4, 5], dims, "city")
    assert out[out["dimension_value"] == "C"]["flagged"].iloc[0] == False


def test_enrich_dimensions_never_drops():
    orders, ctx = _orders(), _ctx()
    dims = enrich_dimensions(orders, ctx.customers, ctx.products, ctx)
    assert len(dims) == len(orders)
    for dim in DIMENSIONS:
        assert dim in dims.columns
