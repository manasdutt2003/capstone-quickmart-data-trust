import pandas as pd

from src.commission import (
    COMMISSION_RATE,
    build_commission_datamart,
    calculate_commission,
    calculate_line_value,
    commission_breakdown,
    enrich_with_commission,
    export_commission_datamart,
    standardize_dimensions,
)
from src.deduplication import commission_frame


def test_commission_reconciles():
    o = pd.DataFrame([{"order_id": "O1"}, {"order_id": "O2"}])
    lv = pd.Series([100.0, 200.0])
    cf = commission_frame(o, lv, 0.08)
    assert abs(cf["commission"].sum() - 24.0) < 1e-6
    assert (cf["commission"] == (cf["line_value"] * 0.08).round(2)).all()
class TestLineValueCalculation:
    def test_basic_line_value(self):
        row = pd.Series({"quantity": "2", "unit_price_paid": "100",
                         "discount": "0"})
        assert calculate_line_value(row) == 200.0

    def test_line_value_with_discount_percent(self):
        row = pd.Series({"quantity": "2", "unit_price_paid": "100",
                         "discount": "10%"})
        assert calculate_line_value(row) == 180.0

    def test_line_value_with_discount_fraction(self):
        row = pd.Series({"quantity": "2", "unit_price_paid": "100",
                         "discount": "0.1"})
        assert calculate_line_value(row) == 180.0

    def test_line_value_with_discount_whole_number(self):
        row = pd.Series({"quantity": "2", "unit_price_paid": "100",
                         "discount": "15"})
        assert calculate_line_value(row) == 170.0

    def test_line_value_missing_quantity(self):
        row = pd.Series({"quantity": "", "unit_price_paid": "100",
                         "discount": "0"})
        assert calculate_line_value(row) == 0.0

    def test_line_value_missing_price(self):
        row = pd.Series({"quantity": "2", "unit_price_paid": "",
                         "discount": "0"})
        assert calculate_line_value(row) == 0.0

    def test_line_value_negative_quantity(self):
        row = pd.Series({"quantity": "-2", "unit_price_paid": "100",
                         "discount": "0"})
        assert calculate_line_value(row) == 0.0

    def test_line_value_negative_price(self):
        row = pd.Series({"quantity": "2", "unit_price_paid": "-100",
                         "discount": "0"})
        assert calculate_line_value(row) == 0.0


class TestCommissionCalculation:
    def test_commission_rate(self):
        assert COMMISSION_RATE == 0.08

    def test_calculate_commission(self):
        assert calculate_commission(100.0) == 8.0
        assert calculate_commission(180.0) == 14.4
        assert calculate_commission(0.0) == 0.0

    def test_commission_rounding(self):
        assert calculate_commission(123.45) == 9.88


class TestEnrichWithCommission:
    def test_adds_columns(self):
        df = pd.DataFrame({"quantity": ["2", "3"],
                           "unit_price_paid": ["100", "200"],
                           "discount": ["0", "10%"]})
        enriched = enrich_with_commission(df)
        assert "line_value" in enriched.columns
        assert "commission" in enriched.columns
        assert enriched.iloc[0]["line_value"] == 200.0
        assert enriched.iloc[0]["commission"] == 16.0
        assert enriched.iloc[1]["line_value"] == 540.0
        assert enriched.iloc[1]["commission"] == 43.2


class TestStandardizeDimensions:
    def setup_method(self):
        self.city_map = {"Bengaluru": "Bengaluru", "Chennai": "Chennai"}
        self.customers = pd.DataFrame({"customer_id": ["C001", "C002"],
                                       "city": ["Bengaluru", "Chennai"]})
        self.products = pd.DataFrame({"product_id": ["P001"],
                                      "category": ["Gadgets"]})

    def _enrich(self, df):
        return standardize_dimensions(
            df, self.city_map, {"Gadgets": "Gadgets"}, {"UPI": "UPI"},
            {"Delivered": "Delivered"}, self.customers,
            pd.DataFrame({"product_id": ["P001"],
                          "category": ["Gadgets"]}))

    def test_adds_standardized_columns(self):
        df = pd.DataFrame({
            "customer_id": ["C001", "C002"], "product_id": ["P001", "P001"],
            "order_date": ["2024-01-15", "2024-02-20"],
            "payment_mode": ["UPI", "COD"],
            "order_status": ["Delivered", "Cancelled"]})
        enriched = self._enrich(df)
        for col in ["city_std", "category_std", "payment_std", "status_std",
                    "order_month"]:
            assert col in enriched.columns

    def test_city_mapping_from_customers(self):
        df = pd.DataFrame({
            "customer_id": ["C001"], "product_id": ["P001"],
            "order_date": ["2024-01-15"], "payment_mode": ["UPI"],
            "order_status": ["Delivered"]})
        assert self._enrich(df).iloc[0]["city_std"] == "Bengaluru"

    def test_order_month_extraction(self):
        df = pd.DataFrame({
            "customer_id": ["C001"], "product_id": ["P001"],
            "order_date": ["2024-01-15"], "payment_mode": ["UPI"],
            "order_status": ["Delivered"]})
        assert self._enrich(df).iloc[0]["order_month"] == "2024-01"


class TestCommissionBreakdown:
    def test_breakdown_by_single_column(self):
        df = pd.DataFrame({
            "city_std": ["Bengaluru", "Bengaluru", "Chennai"],
            "commission": [10.0, 20.0, 15.0],
            "line_value": [100.0, 200.0, 150.0],
            "order_id": ["O1", "O2", "O3"]})
        result = commission_breakdown(df, ["city_std"])
        assert len(result) == 2
        bengaluru = result[result["city_std"] == "Bengaluru"].iloc[0]
        assert bengaluru["orders"] == 2
        assert bengaluru["commission"] == 30.0
        assert bengaluru["line_value"] == 300.0

    def test_breakdown_by_multiple_columns(self):
        df = pd.DataFrame({
            "city_std": ["Bengaluru", "Bengaluru", "Chennai"],
            "payment_std": ["UPI", "COD", "UPI"],
            "commission": [10.0, 20.0, 15.0],
            "line_value": [100.0, 200.0, 150.0],
            "order_id": ["O1", "O2", "O3"]})
        assert len(commission_breakdown(df, ["city_std", "payment_std"])) == 3


class TestBuildCommissionDatamart:
    def setup_method(self):
        self.city_map = {"Bengaluru": "Bengaluru", "Chennai": "Chennai"}
        self.customers = pd.DataFrame({"customer_id": ["C001", "C002"],
                                       "city": ["Bengaluru", "Chennai"]})
        self.products = pd.DataFrame({"product_id": ["P001"],
                                      "category": ["Gadgets"]})

    def _marts(self, raw_orders, clean_orders):
        return build_commission_datamart(
            raw_orders, clean_orders, self.customers, self.products,
            self.city_map, {"Gadgets": "Gadgets"}, {"UPI": "UPI", "COD": "COD"},
            {"Delivered": "Delivered", "Cancelled": "Cancelled"})

    def test_summary_matches_expected(self):
        raw_orders = pd.DataFrame({
            "order_id": ["O001", "O002", "O003"],
            "customer_id": ["C001", "C001", "C002"],
            "product_id": ["P001", "P001", "P001"],
            "order_date": ["2024-01-15", "2024-01-20", "2024-02-10"],
            "quantity": ["2", "2", "1"],
            "unit_price_paid": ["100", "100", "200"],
            "discount": ["0", "0", "0"],
            "payment_mode": ["UPI", "COD", "UPI"],
            "order_status": ["Delivered", "Delivered", "Cancelled"],
            "delivery_days": ["2", "3", ""],
            "notes": ["", "", ""],
            "_source_row": [1, 2, 3]})
        marts = self._marts(raw_orders, raw_orders.iloc[:2].copy())
        for key in ["summary", "by_month", "by_city", "by_payment",
                    "by_status", "compare_month", "compare_city"]:
            assert key in marts
        summary = marts["summary"].iloc[0]
        assert summary["orders_before"] == 3
        assert summary["orders_after"] == 2
        assert summary["rows_removed"] == 1
        assert summary["commission_rate"] == 0.08

    def test_commission_leakage_calculation(self):
        raw_orders = pd.DataFrame({
            "order_id": ["O001", "O002"],
            "customer_id": ["C001", "C001"],
            "product_id": ["P001", "P001"],
            "order_date": ["2024-01-15", "2024-01-15"],
            "quantity": ["2", "2"],
            "unit_price_paid": ["100", "100"],
            "discount": ["0", "0"],
            "payment_mode": ["UPI", "UPI"],
            "order_status": ["Delivered", "Delivered"],
            "delivery_days": ["2", "2"],
            "notes": ["", ""],
            "_source_row": [1, 2]})
        marts = build_commission_datamart(
            raw_orders, raw_orders.iloc[:1].copy(), self.customers,
            self.products, self.city_map, {"Gadgets": "Gadgets"},
            {"UPI": "UPI"}, {"Delivered": "Delivered"})
        summary = marts["summary"].iloc[0]
        assert summary["commission_before"] == 32.0
        assert summary["commission_after"] == 16.0
        assert summary["commission_leakage"] == 16.0


class TestExportCommissionDatamart:
    def test_export_creates_files(self, tmp_path):
        marts = {
            "summary": pd.DataFrame([{"commission_before": 100,
                                      "commission_after": 80}]),
            "by_month": pd.DataFrame([{"order_month": "2024-01",
                                       "commission": 80}]),
            "by_city": pd.DataFrame([{"city_std": "Bengaluru",
                                      "commission": 80}]),
        }
        export_commission_datamart(marts, str(tmp_path))
        assert (tmp_path / "commission_datamart.csv").exists()
        assert (tmp_path / "commission_summary.csv").exists()
        assert (tmp_path / "commission_by_month.csv").exists()
        assert (tmp_path / "commission_by_city.csv").exists()
