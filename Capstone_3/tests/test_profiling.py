import pandas as pd

from src.profiling import profile_all, profile_table


class TestProfiling:
    def setup_method(self):
        self.customers = pd.DataFrame({
            "customer_id": ["C001", "C002", "C003"],
            "customer_name": ["John", "Jane", ""],
            "email": ["john@test.com", "NA", "jane@test.com"],
            "city": ["Bengaluru", "Chennai", ""],
            "phone": ["1234567890", "0987654321", "NA"],
            "signup_date": ["2023-01-01", "2023-06-15", "unknown"],
        })
        self.products = pd.DataFrame({
            "product_id": ["P001", "P002"],
            "product_name": ["Widget", "Gadget"],
            "category": ["Gadgets", "Tools"],
            "unit_price": ["100", "200"],
            "stock_qty": ["10", "5"],
        })
        self.orders = pd.DataFrame({
            "order_id": ["O001", "O002"],
            "customer_id": ["C001", "C002"],
            "product_id": ["P001", "P002"],
            "order_date": ["2024-01-15", "2024-02-20"],
            "quantity": ["2", "3"],
            "unit_price_paid": ["100", "200"],
            "discount": ["0", "10%"],
            "payment_mode": ["UPI", "COD"],
            "order_status": ["Delivered", "Cancelled"],
            "delivery_days": ["2", ""],
            "notes": ["", "note"],
        })

    def test_profile_table_columns(self):
        profile = profile_table(self.customers, "customers")
        assert list(profile.columns) == ["table", "column", "rows", "missing",
                                         "usable", "distinct", "missing_pct"]
        assert len(profile) == 6

    def test_missing_counts(self):
        profile = profile_table(self.customers, "customers")
        missing = dict(zip(profile["column"], profile["missing"]))
        assert missing["customer_name"] == 1
        assert missing["email"] == 1
        assert missing["city"] == 1
        assert missing["phone"] == 1
        assert missing["signup_date"] == 1

    def test_usable_counts(self):
        profile = profile_table(self.customers, "customers")
        usable = dict(zip(profile["column"], profile["usable"]))
        assert usable["customer_id"] == 3
        assert usable["customer_name"] == 2
        assert usable["email"] == 2

    def test_distinct_counts(self):
        profile = profile_table(self.customers, "customers")
        distinct = dict(zip(profile["column"], profile["distinct"]))
        assert distinct["customer_id"] == 3
        assert distinct["city"] == 3

    def test_profile_all(self):
        profile = profile_all(self.customers, self.products, self.orders)
        assert "table" in profile.columns
        assert profile["table"].nunique() == 3
        assert len(profile) == 6 + 5 + 11
