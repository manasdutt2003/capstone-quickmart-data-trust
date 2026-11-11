"""Edge-case tests for Q4: tie, null, boundary values."""

import pandas as pd
import pytest

from src.line_value import line_value
from src.questions.seg6_leadership import (
    q4a_monthly_sales_by_category_city,
    q4b_top5_customers_with_ties,
    q4d_avg_delivery_days_with_impossible,
    q4e_cross_dimensional_finding,
    q4f_three_unknowns,
    q4g_dual_definitions_comparison,
)


def _make_fixture_orders():
    """Create a small fixture with edge cases for Q4."""
    return pd.DataFrame([
        {"order_id": "O1", "customer_id": "C1", "product_id": "P1",
         "order_date": "2024-01-01", "quantity": "2", "unit_price_paid": "100",
         "discount": "0", "payment_mode": "UPI", "order_status": "Delivered",
         "delivery_days": "3", "notes": "", "line_value": 200.0},
        {"order_id": "O2", "customer_id": "C2", "product_id": "P1",
         "order_date": "2024-01-02", "quantity": "1", "unit_price_paid": "200",
         "discount": "0", "payment_mode": "COD", "order_status": "Delivered",
         "delivery_days": "2", "notes": "", "line_value": 200.0},
        {"order_id": "O3", "customer_id": "C3", "product_id": "P1",
         "order_date": "2024-01-03", "quantity": "1", "unit_price_paid": "200",
         "discount": "0", "payment_mode": "UPI", "order_status": "Delivered",
         "delivery_days": "1", "notes": "", "line_value": 200.0},
        {"order_id": "O4", "customer_id": "C4", "product_id": "P1",
         "order_date": "2024-01-04", "quantity": "", "unit_price_paid": "100",
         "discount": "0", "payment_mode": "UPI", "order_status": "Delivered",
         "delivery_days": "3", "notes": "", "line_value": None},
        {"order_id": "O5", "customer_id": "C5", "product_id": "P1",
         "order_date": "2024-01-05", "quantity": "1", "unit_price_paid": "100",
         "discount": "0", "payment_mode": "COD", "order_status": "Delivered",
         "delivery_days": "0", "notes": "", "line_value": 100.0},
        {"order_id": "O6", "customer_id": "C6", "product_id": "P1",
         "order_date": "2024-01-06", "quantity": "1", "unit_price_paid": "100",
         "discount": "0", "payment_mode": "UPI", "order_status": "Delivered",
         "delivery_days": "30", "notes": "", "line_value": 100.0},
        {"order_id": "O7", "customer_id": "C7", "product_id": "P1",
         "order_date": "2024-01-07", "quantity": "1", "unit_price_paid": "100",
         "discount": "0", "payment_mode": "UPI", "order_status": "Delivered",
         "delivery_days": "31", "notes": "", "line_value": 100.0},
        {"order_id": "O8", "customer_id": "C8", "product_id": "P1",
         "order_date": "2024-01-08", "quantity": "1", "unit_price_paid": "100",
         "discount": "0", "payment_mode": "UPI", "order_status": "Delivered",
         "delivery_days": "-1", "notes": "", "line_value": 100.0},
        {"order_id": "O9", "customer_id": "C9", "product_id": "P1",
         "order_date": "2024-01-09", "quantity": "1", "unit_price_paid": "100",
         "discount": "0", "payment_mode": "UPI", "order_status": "Delivered",
         "delivery_days": "", "notes": "", "line_value": 100.0},
        {"order_id": "O10", "customer_id": "C10", "product_id": "P1",
         "order_date": "2024-01-10", "quantity": "1", "unit_price_paid": "100",
         "discount": "0", "payment_mode": "UPI", "order_status": "Delivered",
         "delivery_days": "2", "notes": "", "line_value": 100.0},
        {"order_id": "O11", "customer_id": "C11", "product_id": "P1",
         "order_date": "2024-01-11", "quantity": "1", "unit_price_paid": "100",
         "discount": "0", "payment_mode": "COD", "order_status": "Delivered",
         "delivery_days": "2", "notes": "", "line_value": 100.0},
    ])


def _make_fixture_customers():
    return pd.DataFrame([
        {"customer_id": "C1", "city": "Bengaluru", "signup_date": "2023-01-01"},
        {"customer_id": "C2", "city": "Chennai", "signup_date": "2023-01-01"},
        {"customer_id": "C3", "city": "Hyderabad", "signup_date": "2023-01-01"},
        {"customer_id": "C4", "city": "Pune", "signup_date": "2023-01-01"},
        {"customer_id": "C5", "city": "Mysuru", "signup_date": "2023-01-01"},
        {"customer_id": "C6", "city": "Bengaluru", "signup_date": "2023-01-01"},
        {"customer_id": "C7", "city": "Chennai", "signup_date": "2023-01-01"},
        {"customer_id": "C8", "city": "Hyderabad", "signup_date": "2023-01-01"},
        {"customer_id": "C9", "city": "Pune", "signup_date": "2023-01-01"},
        {"customer_id": "C10", "city": "Bengaluru", "signup_date": "2023-01-01"},
        {"customer_id": "C11", "city": "Chennai", "signup_date": "2023-01-01"},
    ])


def _make_fixture_products():
    return pd.DataFrame([
        {"product_id": "P1", "category": "Electronics", "stock_qty": "100", "unit_price": "150"},
    ])


def _load_mappings():
    from pathlib import Path

    from src.normalise import load_mapping
    ROOT = Path(__file__).resolve().parents[1]
    return {
        "city_map": load_mapping(ROOT / "config" / "city_mapping.csv"),
        "cat_map": load_mapping(ROOT / "config" / "category_mapping.csv"),
        "status_map": load_mapping(ROOT / "config" / "status_mapping.csv"),
        "pay_map": load_mapping(ROOT / "config" / "payment_mapping.csv"),
    }


class TestQ4EdgeCases:
    @pytest.fixture(scope="class")
    def ctx(self):
        orders = _make_fixture_orders()
        customers = _make_fixture_customers()
        products = _make_fixture_products()
        maps = _load_mappings()
        return {
            "orders": orders,
            "customers": customers,
            "products": products,
            "city_map": maps["city_map"],
            "cat_map": maps["cat_map"],
            "status_map": maps["status_map"],
            "pay_map": maps["pay_map"],
        }

    def test_q4a_handles_null_line_value(self, ctx):
        """Q4a should handle NULL line_value gracefully (excluded from sums)."""
        sales, recon, _ = q4a_monthly_sales_by_category_city(
            ctx["orders"], ctx["customers"], ctx["products"],
            ctx["city_map"], ctx["cat_map"], ctx["status_map"], ctx["pay_map"]
        )
        assert len(sales) > 0
        assert recon["ok"] == True
        assert recon["grand_total"] > 0

    def test_q4b_tie_handling(self, ctx):
        """Q4b should handle ties in value, frequency, tenure with dense rank."""
        result, _ = q4b_top5_customers_with_ties(
            ctx["orders"], ctx["customers"], ctx["products"],
            ctx["city_map"], ctx["cat_map"], ctx["status_map"], ctx["pay_map"]
        )
        stats = result["all_stats"]
        tie_rows = stats[stats["value_tie"]]
        assert len(tie_rows) >= 2
        c2 = stats[stats["customer_id"] == "C2"].iloc[0]
        c3 = stats[stats["customer_id"] == "C3"].iloc[0]
        assert c2["rank_value"] == c3["rank_value"]
        assert c2["value_tie"] == True
        assert c3["value_tie"] == True

    def test_q4b_frequency_tie(self, ctx):
        """Q4b should handle tie in frequency (C10 and C11 both have 1 order)."""
        result, _ = q4b_top5_customers_with_ties(
            ctx["orders"], ctx["customers"], ctx["products"],
            ctx["city_map"], ctx["cat_map"], ctx["status_map"], ctx["pay_map"]
        )
        stats = result["all_stats"]
        c10 = stats[stats["customer_id"] == "C10"].iloc[0]
        c11 = stats[stats["customer_id"] == "C11"].iloc[0]
        assert c10["rank_frequency"] == c11["rank_frequency"]
        assert c10["frequency_tie"] == True
        assert c11["frequency_tie"] == True

    def test_q4d_impossible_delivery_flagged(self, ctx):
        """Q4d should flag impossible delivery days separately."""
        delivery, _ = q4d_avg_delivery_days_with_impossible(
            ctx["orders"], ctx["customers"], ctx["products"],
            ctx["city_map"], ctx["cat_map"], ctx["status_map"], ctx["pay_map"]
        )
        assert "impossible_orders" in delivery.columns
        assert "negative_orders" in delivery.columns
        assert "over_30_orders" in delivery.columns
        assert "missing_orders" in delivery.columns
        total_impossible = delivery["impossible_orders"].sum()
        assert total_impossible >= 3

    def test_q4d_negative_and_over_30_separated(self, ctx):
        """Q4d should separate negative and over_30 counts."""
        delivery, _ = q4d_avg_delivery_days_with_impossible(
            ctx["orders"], ctx["customers"], ctx["products"],
            ctx["city_map"], ctx["cat_map"], ctx["status_map"], ctx["pay_map"]
        )
        assert delivery["negative_orders"].sum() >= 1
        assert delivery["over_30_orders"].sum() >= 1

    def test_q4e_cross_dim_finding(self, ctx):
        """Q4e should find cross-dimensional concentrations."""
        finding, _ = q4e_cross_dimensional_finding(
            ctx["orders"], ctx["customers"], ctx["products"],
            ctx["city_map"], ctx["cat_map"], ctx["status_map"], ctx["pay_map"]
        )
        assert "pct_of_city_cat_month" in finding.columns
        if len(finding) > 0:
            assert finding["pct_of_city_cat_month"].between(0, 100).all()

    def test_q4f_three_unknowns(self, ctx):
        """Q4f should return three unknowns with masked examples."""
        items, _ = q4f_three_unknowns(ctx["orders"], ctx["customers"], ctx["products"])
        assert len(items) == 3
        for item in items:
            assert "unknown" in item
            assert "rows_affected" in item
            assert "example_customer" in item
            assert "unsafe_decision" in item
            if item["example_customer"]:
                assert "*" in item["example_customer"]

    def test_q4g_dual_definitions_on_valid_inputs(self, ctx):
        """Q4g: canonical and legacy should agree on valid inputs."""
        comparison, _ = q4g_dual_definitions_comparison(
            ctx["orders"], ctx["customers"], ctx["products"],
            ctx["city_map"], ctx["cat_map"], ctx["status_map"], ctx["pay_map"]
        )
        # The fixture has 1 invalid row (O4: empty quantity) where canonical=NULL, legacy=0.0
        # On valid rows, both should agree
        assert comparison["canonical_sum"] == comparison["legacy_sum"]
        assert comparison["difference"] == 0.0
        # 1 row differs (the invalid one)
        assert comparison["rows_differ"] == 1

    def test_line_value_null_propagation(self):
        """Canonical line_value returns None if any input is None."""
        assert line_value(None, 100, 0.0) is None
        assert line_value(1, None, 0.0) is None
        assert line_value(1, 100, None) is None
        assert line_value(0, 100, 0.0) == 0.0
        assert line_value(1, -1, 0.0) == -1.0

    def test_line_value_zero_fill_legacy(self):
        """Legacy calculate_line_value returns 0.0 for invalid inputs."""
        from src.commission import calculate_line_value
        row = {"quantity": "", "unit_price_paid": "100", "discount": "0"}
        assert calculate_line_value(row) == 0.0
        row = {"quantity": "1", "unit_price_paid": "", "discount": "0"}
        assert calculate_line_value(row) == 0.0
        row = {"quantity": "1", "unit_price_paid": "100", "discount": ""}
        assert calculate_line_value(row) == 100.0

    def test_line_value_boundary_discount(self):
        """Discount parsing at boundaries."""
        from src.normalise import parse_discount_frac
        assert parse_discount_frac("0%") == 0.0
        assert parse_discount_frac("0") == 0.0
        assert parse_discount_frac("100%") == 1.0
        assert parse_discount_frac("0.1") == 0.1
        assert parse_discount_frac("") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])