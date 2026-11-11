from pathlib import Path

import pandas as pd

from src.datamarts import (
    build_all_datamarts,
    build_cohort_datamart,
    build_customer_datamart,
    build_delivery_datamart,
    build_payment_datamart,
    build_sales_datamart,
)
from src.validation_rules import validate_orders

DATA = Path(__file__).resolve().parents[1] / "data"


def _synthetic_base():
    trusted = pd.DataFrame({
        "order_id": ["O1", "O2", "O3", "O4"],
        "customer_id": ["C1", "C1", "C2", "C3"],
        "product_id": ["P1", "P1", "P2", "P3"],
        "order_date": ["2024-01-15", "2024-01-20", "2024-02-10", "2024-03-01"],
        "quantity": [2, 1, 3, 2],
        "unit_price_paid": [100.0, 100.0, 200.0, 150.0],
        "discount": [0.0, 0.1, 0.0, 0.0],
        "payment_mode": ["UPI", "COD", "UPI", "UPI"],
        "order_status": ["Delivered", "Delivered", "Delivered", "Cancelled"],
        "delivery_days": [2, 3, 1, 0],
    })
    customers = pd.DataFrame({
        "customer_id": ["C1", "C2", "C3"],
        "city": ["Bengaluru", "Chennai", "Bengaluru"],
        "signup_date": ["2023-01-01", "2023-06-15", "2024-01-01"],
    })
    products = pd.DataFrame({
        "product_id": ["P1", "P2", "P3"],
        "category": ["Gadgets", "Tools", "Gadgets"],
    })
    return trusted, customers, products


def test_marts_reconcile():
    trusted, customers, products = _synthetic_base()
    sales = build_sales_datamart(trusted, customers, products)
    grand = sales["revenue"].sum()
    assert abs(sales.groupby("city")["revenue"].sum().sum() - grand) < 0.01
    assert abs(sales.groupby("category")["revenue"].sum().sum() - grand) < 0.01
    assert abs(sales.groupby("order_month")["revenue"].sum().sum() - grand) < 0.01


def test_sales_datamart():
    trusted, customers, products = _synthetic_base()
    sales = build_sales_datamart(trusted, customers, products)
    assert isinstance(sales, pd.DataFrame)
    assert len(sales) > 0
    for col in ["order_month", "city", "category", "order_status", "orders",
                "quantity", "revenue"]:
        assert col in sales.columns
    delivered = sales[sales["order_status"] == "Delivered"]
    assert delivered["revenue"].sum() == 890.0


def test_customer_datamart():
    trusted, customers, _products = _synthetic_base()
    customer = build_customer_datamart(trusted, customers)
    assert isinstance(customer, pd.DataFrame)
    assert len(customer) == 3
    for col in ["customer_id", "city", "total_orders", "total_quantity",
                "total_value", "first_order", "last_order", "signup_date",
                "tenure_days", "frequency_days"]:
        assert col in customer.columns
    c1 = customer[customer["customer_id"] == "C1"].iloc[0]
    assert c1["total_orders"] == 2
    assert c1["total_value"] == 290.0


def test_payment_datamart():
    trusted, customers, products = _synthetic_base()
    payment = build_payment_datamart(trusted, customers, products)
    assert isinstance(payment, pd.DataFrame)
    for col in ["order_month", "city", "payment_mode", "orders", "revenue"]:
        assert col in payment.columns


def test_delivery_datamart():
    trusted, customers, products = _synthetic_base()
    delivery = build_delivery_datamart(trusted, customers, products)
    assert isinstance(delivery, pd.DataFrame)
    for col in ["city", "category", "orders", "avg_delivery_days",
                "median_delivery_days", "min_delivery_days",
                "max_delivery_days", "on_time_pct"]:
        assert col in delivery.columns
    assert len(delivery) > 0


def test_cohort_datamart():
    trusted, customers, _products = _synthetic_base()
    cohort = build_cohort_datamart(trusted, customers)
    assert isinstance(cohort, pd.DataFrame)
    for col in ["signup_month", "order_month", "active_customers", "orders"]:
        assert col in cohort.columns


def test_all_datamarts():
    trusted, customers, products = _synthetic_base()
    datamarts = build_all_datamarts(trusted, customers, products)
    for name in ["sales_datamart", "customer_datamart", "payment_datamart",
                 "delivery_datamart", "cohort_datamart"]:
        assert name in datamarts
        assert isinstance(datamarts[name], pd.DataFrame)


def test_trusted_reconciliation():
    trusted, customers, products = _synthetic_base()
    customers["signup_date"] = ["2023-01-01", "2023-06-15", "2024-01-01"]
    products["unit_price"] = [100.0, 200.0, 150.0]
    res = validate_orders(trusted, customers, products, {}, {}, {}, {})
    total = len(res["trusted_orders"]) + len(res["rejected_orders"]) + \
        len(res["warning_orders"])
    assert total == len(trusted)


def test_no_raw_price_text_in_marts():
    trusted, customers, products = _synthetic_base()
    sales = build_sales_datamart(trusted, customers, products)
    assert "unit_price_paid" not in sales.columns


# Tests that run against generated pipeline artifacts (require pipeline run)
def test_marts_reconcile_on_generated_data():
    sales = pd.read_csv(DATA / "sales_datamart.csv")
    grand = sales["value"].sum()
    assert abs(sales.groupby("city_std")["value"].sum().sum() - grand) < 0.01
    assert abs(sales.groupby("category_std")["value"].sum().sum() - grand) < 0.01
    assert abs(sales.groupby("order_month")["value"].sum().sum() - grand) < 0.01


def test_trusted_reconciliation_on_generated_data():
    trusted = pd.read_csv(DATA / "trusted_orders.csv")
    rejected = pd.read_csv(DATA / "rejected_orders.csv")
    clean = pd.read_csv(DATA / "clean_orders.csv")
    assert len(trusted) + len(rejected) == len(clean)


def test_no_raw_price_text_in_marts_on_generated_data():
    sales = pd.read_csv(DATA / "sales_datamart.csv")
    assert "unit_price_paid" not in sales.columns