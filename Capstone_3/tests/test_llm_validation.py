from pathlib import Path

import pandas as pd
import pytest

from src.llm_reporting import (
    aggregate_inputs,
    assert_no_pii,
    draft_report,
)
from src.llm_reporting import (
    validate_report as validate_llm_report,
)
from src.report_validation import (
    extract_numbers,
    generate_validation_report,
    validate_number,
    validate_report,
    verify_all_claims,
)


class TestExtractNumbers:
    def test_currency_extraction(self):
        text = "Revenue was Rs1,234.56 and Rs789.00"
        numbers = extract_numbers(text)
        currency_nums = [n for n in numbers if n["type"] == "currency"]
        assert len(currency_nums) == 2
        assert 1234.56 in [n["value"] for n in currency_nums]
        assert 789.00 in [n["value"] for n in currency_nums]

    def test_percentage_extraction(self):
        text = "Growth was 95.5% and 100%"
        numbers = extract_numbers(text)
        pct_nums = [n for n in numbers if n["type"] == "percentage"]
        assert len(pct_nums) == 2
        assert 95.5 in [n["value"] for n in pct_nums]
        assert 100.0 in [n["value"] for n in pct_nums]

    def test_plain_number_extraction(self):
        text = "Total 42 orders and 1,234 customers"
        numbers = extract_numbers(text)
        plain_nums = [n for n in numbers if n["type"] == "number"]
        values = [n["value"] for n in plain_nums]
        assert 42.0 in values
        assert 1234.0 in values

    def test_context_capture(self):
        text = "Revenue was Rs100.00 this week"
        numbers = extract_numbers(text)
        for n in numbers:
            assert "Revenue was" in n["context"] or "Rs100" in n["context"]


class TestValidateNumber:
    def setup_method(self):
        self.datamarts = {
            "sales_datamart": pd.DataFrame({
                "revenue": [100.0, 200.0, 300.0],
                "orders": [10, 20, 30],
                "avg_order_value": [10.0, 10.0, 10.0],
            }),
            "customer_datamart": pd.DataFrame({
                "total_value": [150.0, 250.0, 500.0],
            }),
        }

    def test_exact_match(self):
        result = validate_number(200.0, "currency", "Revenue Rs200",
                                 self.datamarts)
        assert result["matched"] is True
        assert result["datamart_value"] == 200.0

    def test_rounded_match(self):
        result = validate_number(100.00, "currency", "Revenue Rs100.00",
                                 self.datamarts)
        assert result["matched"] is True
        assert result["datamart_value"] == 100.0

    def test_no_match(self):
        result = validate_number(999.0, "currency", "Revenue Rs999",
                                 self.datamarts)
        assert result["matched"] is False
        assert result["datamart_value"] is None

    def test_percentage_match(self):
        result = validate_number(10.0, "percentage", "10% growth",
                                 self.datamarts)
        assert result["matched"] is True

    def test_tolerance(self):
        result = validate_number(200.005, "currency", "Revenue Rs200.005",
                                 self.datamarts)
        assert result["matched"] is True
        result = validate_number(200.02, "currency", "Revenue Rs200.02",
                                 self.datamarts)
        assert result["matched"] is False


class TestValidateReport:
    def setup_method(self):
        self.datamarts = {
            "sales_datamart": pd.DataFrame({
                "revenue": [100.0, 200.0, 300.0],
                "orders": [10, 20, 30],
            }),
            "customer_datamart": pd.DataFrame({
                "total_value": [150.0, 250.0, 500.0],
            }),
        }

    def test_all_match(self):
        report = "Revenue was Rs300.00 with 30 orders. Top customer value Rs250.00."
        df = validate_report(report, self.datamarts)
        assert len(df) >= 3
        assert df["matched"].all()

    def test_some_fail(self):
        report = "Revenue was Rs999.00 with 60 orders"
        df = validate_report(report, self.datamarts)
        assert not df["matched"].all()
        assert len(df[~df["matched"]]) >= 1

    def test_context_preserved(self):
        report = "Revenue was Rs300.00"
        df = validate_report(report, self.datamarts)
        for _, row in df.iterrows():
            assert "context" in row
            assert len(row["context"]) > 0


class TestVerifyAllClaims:
    def setup_method(self):
        self.datamarts = {
            "sales_datamart": pd.DataFrame({
                "revenue": [100.0, 200.0, 300.0],
                "orders": [10, 20, 30],
            }),
        }

    def test_all_passed(self):
        report = "Total revenue Rs300.00 with 30 orders"
        df, all_passed = verify_all_claims(self.datamarts, report)
        assert all_passed is True
        assert isinstance(df, pd.DataFrame)

    def test_some_failed(self):
        report = "Total revenue Rs999.00"
        _df, all_passed = verify_all_claims(self.datamarts, report)
        assert all_passed is False

    def test_empty_report(self):
        report = ""
        df, all_passed = verify_all_claims(self.datamarts, report)
        assert all_passed is True
        assert len(df) == 0


class TestGenerateValidationReport:
    def setup_method(self):
        self.datamarts = {
            "sales_datamart": pd.DataFrame({
                "revenue": [100.0, 200.0],
            }),
        }

    def test_report_generation(self, tmp_path):
        validation_df = pd.DataFrame({
            "claimed_value": [100.0, 300.0],
            "matched": [True, False],
            "datamart_value": [100.0, None],
            "difference": [0.0, None],
            "type": ["currency", "currency"],
            "context": ["Revenue Rs100", "Revenue Rs300"],
            "original_context": ["Revenue Rs100", "Revenue Rs300"],
        })
        out_path = tmp_path / "validation_report.md"
        generate_validation_report(validation_df, str(out_path))
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "Report Validation Results" in content
        assert "2" in content
        assert "1" in content
        assert "50%" in content or "50.0%" in content
        assert "Rs100" in content
        assert "Rs300" in content
        assert "PASS" in content
        assert "FAIL" in content


def test_pii_blocked():
    with pytest.raises(ValueError):
        assert_no_pii("contact a@b.com now")


def test_report_validates_and_catches_invention():
    ROOT = Path(__file__).resolve().parents[1]
    marts = {
        "sales": pd.read_csv(ROOT / "data" / "sales_datamart.csv"),
        "customer_value": pd.read_csv(ROOT / "data" / "customer_value_datamart.csv"),
        "delivery": pd.read_csv(ROOT / "data" / "delivery_datamart.csv"),
    }
    agg = aggregate_inputs(marts)
    rep = draft_report(agg, "v1")
    val = validate_llm_report(rep, marts)
    assert (val["status"] == "PASS").all()
    bad = rep + "\nTotal delivered sales were Rs 99,999,999.99 across 1 delivered orders."
    val2 = validate_llm_report(bad, marts)
    assert (val2["status"] == "FAIL").any()