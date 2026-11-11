import re
from pathlib import Path

import pandas as pd
import pytest

from src.llm_reporting import (
    aggregate_metrics,
    assert_no_pii,
    build_prompt,
    draft_report,
    generate_mock_report,
)
from src.report_validation import (
    extract_numbers,
    validate_number,
    validate_report,
)

ROOT = Path(__file__).resolve().parents[1]


def _datamarts():
    sales = pd.DataFrame({
        "order_month": ["2024-01", "2024-01", "2024-02"],
        "city": ["Bengaluru", "Chennai", "Bengaluru"],
        "category": ["Gadgets", "Tools", "Gadgets"],
        "order_status": ["Delivered", "Delivered", "Delivered"],
        "orders": [2, 1, 3],
        "revenue": [200.0, 150.0, 450.0],
    })
    customer = pd.DataFrame({
        "customer_id": ["C001", "C002", "C003"],
        "city": ["Bengaluru", "Chennai", "Bengaluru"],
        "total_orders": [2, 1, 3],
        "total_value": [300.0, 150.0, 450.0],
        "tenure_days": [30, 15, 60],
    })
    payment = pd.DataFrame({
        "order_month": ["2024-01", "2024-01", "2024-02"],
        "payment_mode": ["UPI", "COD", "UPI"],
        "revenue": [200.0, 150.0, 450.0],
    })
    delivery = pd.DataFrame({
        "city": ["Bengaluru", "Chennai"],
        "category": ["Gadgets", "Tools"],
        "avg_delivery_days": [2.5, 3.0],
        "on_time_pct": [90.0, 80.0],
    })
    return {"sales_datamart": sales, "customer_datamart": customer,
            "payment_datamart": payment, "delivery_datamart": delivery,
            "cohort_datamart": pd.DataFrame()}


class TestReporting:
    def test_aggregate_metrics(self):
        metrics = aggregate_metrics(_datamarts())
        assert "total_revenue" in metrics
        assert metrics["total_revenue"] == 800.0
        assert metrics["total_orders"] == 6
        assert abs(metrics["avg_order_value"] - 800.0 / 6) < 0.01
        assert "top_cities" in metrics
        assert "Bengaluru" in metrics["top_cities"]
        assert "Chennai" in metrics["top_cities"]
        assert "top_categories" in metrics
        assert "Gadgets" in metrics["top_categories"]
        assert "top_customers" in metrics
        assert len(metrics["top_customers"]) == 3
        assert "limitations" in metrics
        assert len(metrics["limitations"]) >= 3

    def test_build_prompt(self):
        metrics = aggregate_metrics(_datamarts())
        prompt = build_prompt(metrics)
        assert "business analyst" in prompt
        assert "QuickMart" in prompt
        assert "Total Revenue" in prompt
        assert "Rs" in prompt
        assert "LIMITATIONS" in prompt or "limitations" in prompt.lower()

    def test_generate_mock_report(self):
        metrics = aggregate_metrics(_datamarts())
        report = generate_mock_report(metrics)
        assert "QuickMart Weekly Leadership Brief" in report
        assert "Rs800.00" in report
        assert "Bengaluru" in report
        assert "Gadgets" in report
        assert "Recommendations" in report or "recommendations" in report.lower()
        assert "Risks" in report or "risks" in report.lower()


class TestReportValidation:
    def setup_method(self):
        self.datamarts = {
            "sales_datamart": pd.DataFrame({
                "revenue": [100.0, 200.0, 300.0],
                "orders": [10, 20, 30],
            }),
            "customer_datamart": pd.DataFrame({
                "total_value": [150.0, 250.0],
            }),
        }

    def test_extract_numbers(self):
        text = "Total revenue was Rs300.00 with 30 orders. Average was Rs100.00."
        numbers = extract_numbers(text)
        assert len(numbers) >= 3
        values = [n["value"] for n in numbers]
        assert 300.0 in values
        assert 30.0 in values
        assert 100.0 in values

    def test_validate_number_match(self):
        result = validate_number(100.0, "currency", "Revenue was Rs100",
                                 {"test": pd.DataFrame({"rev": [100.0]})})
        assert result["matched"] is True
        assert result["datamart_value"] == 100.0

    def test_validate_number_no_match(self):
        result = validate_number(999.0, "currency", "Revenue was Rs999",
                                 {"test": pd.DataFrame({"rev": [100.0]})})
        assert result["matched"] is False

    def test_validate_report(self):
        report = "Total revenue was Rs300.00 with 30 orders. Average was Rs100.00."
        validation_df = validate_report(report, {
            "test": pd.DataFrame({"revenue": [300.0, 200.0],
                                  "orders": [30, 20], "avg": [100.0, 100.0]})
        })
        assert len(validation_df) >= 3
        assert validation_df["matched"].all()

    def test_validate_report_with_failure(self):
        report = "Total revenue was Rs999.00"
        validation_df = validate_report(report, {
            "test": pd.DataFrame({"revenue": [600.0]})
        })
        assert not validation_df["matched"].all()


def test_chart_matches_table():
    sales = pd.DataFrame({
        "order_month": ["2024-01", "2024-02"],
        "city": ["Bengaluru", "Bengaluru"],
        "category": ["Gadgets", "Gadgets"],
        "order_status": ["Delivered", "Delivered"],
        "orders": [2, 3],
        "revenue": [200.0, 450.0],
    })
    monthly = sales.groupby("order_month")["revenue"].sum().sort_index()
    assert len(monthly) > 0 and monthly.sum() > 0


def test_chart_matches_table_on_generated_data():
    pytest.importorskip("matplotlib")
    sales = pd.read_csv(ROOT / "data" / "sales_datamart.csv")
    monthly = sales.groupby("order_month")["value"].sum().sort_index()
    assert (ROOT / "charts" / "monthly_sales.png").exists()
    assert len(monthly) > 0 and monthly.sum() > 0


def test_no_pii_in_outputs():
    pat = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    text = draft_report({"grand_value": 100.0, "grand_orders": 2,
                         "by_city": {"Bengaluru": 100.0},
                         "by_category": {"Grocery": 100.0},
                         "avg_delivery": 3.0}, "v1")
    assert not pat.search(text)


def test_pii_blocked():
    with pytest.raises(ValueError):
        assert_no_pii("contact a@b.com now")


def test_report_validates_and_catches_invention():
    sales = pd.DataFrame({
        "order_month": ["2024-01"],
        "city_std": ["Bengaluru"],
        "category_std": ["Grocery"],
        "orders": [2],
        "value": [772182.0],
    })
    customer_value = pd.DataFrame({
        "customer_id": ["C1"],
        "city_std": ["Bengaluru"],
        "orders": [2],
        "value": [772182.0],
    })
    delivery = pd.DataFrame({
        "city_std": ["Bengaluru"],
        "category_std": ["Grocery"],
        "orders": [2],
        "avg_days": [3.0],
        "median_days": [3.0],
    })
    marts = {"sales": sales, "customer_value": customer_value,
             "delivery": delivery}
    agg = {"grand_value": 772182.0, "grand_orders": 2,
           "by_city": {"Bengaluru": 772182.0},
           "by_category": {"Grocery": 772182.0},
           "avg_delivery": 3.0}
    rep = draft_report(agg, "v1")
    from src.llm_reporting import validate_report as vr
    val = vr(rep, marts)
    assert (val["status"] == "PASS").all()
    bad = rep + "\nTotal delivered sales were Rs 99,999,999.99 across 1 delivered orders."
    val2 = vr(bad, marts)
    assert (val2["status"] == "FAIL").any()
    # Check PII not in generated reports using the same pattern as test_no_pii_in_outputs
    pat = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    for f in ["reports/generated_report.md", "reports/executive_report.md"]:
        text = (ROOT / f).read_text(encoding="utf-8")
        assert not pat.search(text), f"PII in {f}"