"""SQL <-> Python parity: line_value, R01, R03, R06 (Sprint 3).

Runs both versions on real cleaned data and on a crafted fixture, then
compares sorted frames with explicit dtypes (money as Decimal to 2 dp).

Parity diagnosis log:
- COPY ... CSV reads unquoted empty fields as SQL NULL, while Python
  sees ""/None. Fixed on the SQL side: every view treats NULL exactly
  like empty (explicit IS NULL disjuncts first), matching the Python
  None/"" branches. Short-circuit OR evaluation keeps guarded CASTs
  safe. Fixed in sql/08_rule_views.sql (R03 date checks, R06 price
  checks); the SQL was wrong, Python right.
- SQL NULL numerics arrive in pandas as Decimal NaN (transport
  artifact, not a value difference); normalized to None in
  _sql_line_values before comparison.
- Rounding: Python round() (banker's) vs Postgres ROUND(numeric)
  (half away from zero) can differ on exact .5 ties at the 3rd decimal.
  No tie occurred on real data (6000 rows, exact match); the residual
  risk is recorded in docs/line_value.md.
- Python norm_id strips all whitespace, SQL strips spaces only;
  real data is space-only, fixture avoids tabs/newlines.
"""

from decimal import Decimal

import pandas as pd
import psycopg
import pytest

from src.line_value import line_value
from src.normalise import parse_discount_frac, parse_float, parse_int
from src.pg import (
    CUSTOMERS_COLUMNS,
    ORDERS_COLUMNS,
    PRODUCTS_COLUMNS,
    apply_sql_file,
    connect,
    fetch_df,
    load_frame,
    resolve_backend,
    should_fail_fast,
)
from src.validation_rules import (
    Context,
    _r01_customer_exists,
    _r03_signup_before_order,
    _r06_valid_price,
)


def _full_frame(rows, columns, source_file, raw_prefix=True):
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    df = df[list(columns)].astype(str)
    n = len(df)
    df["_source_row"] = [str(i + 1) for i in range(n)]
    df["source_row_number"] = [str(i + 1) for i in range(n)]
    df["source_file"] = source_file
    for col in ("dedup_rule_applied", "rules_passed", "rules_failed"):
        df[col] = ""
    if raw_prefix:
        for col in list(df.columns):
            if col.startswith("raw_"):
                base = col[4:]
                if base in df.columns:
                    df[col] = df[base]
    return df


def _db():
    """Connect, skip, or fail-fast per backend order.

    CI=true with DATABASE_URL set: connect directly so an unreachable
    database FAILS the test. Otherwise skip with a clear reason when no
    backend is available or reachable.
    """
    if should_fail_fast():
        return connect()
    backend, reason = resolve_backend()
    if backend == "none":
        pytest.skip(f"parity tests skipped: {reason}")
    try:
        return connect()
    except (psycopg.Error, OSError) as exc:
        pytest.skip(f"parity tests skipped: cannot connect ({exc})")


def _fixture():
    customers = _full_frame([
        {"customer_id": "C1", "customer_name": "A", "email": "a@b.com",
         "city": "Pune", "phone": "9999999999", "signup_date": "2024-01-01"},
        {"customer_id": "C-2", "customer_name": "B", "email": "b@b.com",
         "city": "Pune", "phone": "8888888888", "signup_date": "2024-01-01"},
    ], CUSTOMERS_COLUMNS, "customers.csv")
    products = _full_frame([
        {"product_id": "P1", "product_name": "X", "category": "Grocery",
         "unit_price": "100", "stock_qty": "5"},
        {"product_id": "p-01", "product_name": "Y", "category": "Grocery",
         "unit_price": "200", "stock_qty": "5"},
    ], PRODUCTS_COLUMNS, "products.csv")
    orders = _full_frame([
        {"order_id": "O1", "customer_id": "C1", "product_id": "P1",
         "order_date": "2024-02-01", "quantity": "2",
         "unit_price_paid": "100", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3", "notes": ""},
        {"order_id": "O2", "customer_id": "c 1", "product_id": "P1",
         "order_date": "2024-02-01", "quantity": "2",
         "unit_price_paid": "100", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3", "notes": ""},
        {"order_id": "O3", "customer_id": "GHOST", "product_id": "P1",
         "order_date": "2024-02-01", "quantity": "2",
         "unit_price_paid": "100", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3", "notes": ""},
        {"order_id": "O4", "customer_id": "C1", "product_id": "P1",
         "order_date": "2024-01-01", "quantity": "2",
         "unit_price_paid": "100", "discount": "0.1", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3", "notes": ""},
        {"order_id": "O5", "customer_id": "C1", "product_id": "P1",
         "order_date": "2024-02-01", "quantity": "2",
         "unit_price_paid": "90", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3", "notes": ""},
        {"order_id": "O6", "customer_id": "C1", "product_id": "P1",
         "order_date": "2024-02-01", "quantity": "2",
         "unit_price_paid": "", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3", "notes": ""},
        {"order_id": "O7", "customer_id": "C1", "product_id": "P 01",
         "order_date": "2024-02-01", "quantity": "2",
         "unit_price_paid": "200", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3", "notes": ""},
        # R03 same-day boundary: order_date == signup_date passes.
        {"order_id": "O8", "customer_id": "C1", "product_id": "P1",
         "order_date": "2024-01-01", "quantity": "2",
         "unit_price_paid": "100", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3", "notes": ""},
        # TODAY-invariance pair: R01/R03/R06/line_value never read TODAY,
        # so 2026-10-11 and 2026-10-12 must agree SQL<->Python row for row.
        {"order_id": "O9", "customer_id": "C1", "product_id": "P1",
         "order_date": "2026-10-11", "quantity": "2",
         "unit_price_paid": "100", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3", "notes": ""},
        {"order_id": "O10", "customer_id": "C1", "product_id": "P1",
         "order_date": "2026-10-12", "quantity": "2",
         "unit_price_paid": "100", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3", "notes": ""},
        # R06 just-outside-tolerance twin of O5 (exactly -10%, PASS):
        # -10.01% must FAIL on both sides.
        {"order_id": "O11", "customer_id": "C1", "product_id": "P1",
         "order_date": "2024-02-01", "quantity": "2",
         "unit_price_paid": "89.99", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3", "notes": ""},
    ], ORDERS_COLUMNS, "orders.csv")
    return orders, customers, products
    # NOTE: quantity-at-fence (R05) has no SQL twin by design — the IQR
    # fence is derived from the input distribution, so parity is asserted
    # in the Python unit tests (TestR05Bodies), not here.


def _ctx_for(customers, products):
    return Context(customers=customers, products=products, city_map={},
                   cat_map={}, pay_map={}, status_map={})


def _load_all(conn, orders, customers, products):
    conn.execute("DROP VIEW IF EXISTS trusted_enriched CASCADE")
    for view in ("v_trusted_lenient", "v_trusted_strict", "v_rejected_orders",
                 "v_r01_customer_exists", "v_r03_signup_before_order",
                 "v_r06_valid_price", "v_r06_valid_price_tol05",
                 "v_line_value", "v_column_profile", "quality_inputs",
                 "v_quality_scorecard", "v_d06_review_flags",
                 "v_run_params", "orders", "customers", "products"):
        conn.execute(f"DROP VIEW IF EXISTS {view} CASCADE")
    for table in ("orders_clean", "customers_master", "products_clean",
                  "rule_failure_log"):
        conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    for table in ("orders_clean", "customers_master", "products_clean",
                  "rule_failure_log"):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    apply_sql_file(conn, "00_staging.sql")
    load_frame(conn, "orders_clean", orders, ORDERS_COLUMNS)
    load_frame(conn, "customers_master", customers, CUSTOMERS_COLUMNS)
    load_frame(conn, "products_clean", products, PRODUCTS_COLUMNS)
    apply_sql_file(conn, "v_line_value.sql")
    apply_sql_file(conn, "08_rule_views.sql")


def _money(value):
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _py_line_values(orders):
    out = {}
    for _, row in orders.iterrows():
        qty = parse_int(row["quantity"]) if row["quantity"].strip() != "" else None
        price = parse_float(row["unit_price_paid"]) \
            if row["unit_price_paid"].strip() != "" else None
        disc = parse_discount_frac(row["discount"]) \
            if row["discount"].strip() != "" else None
        out[str(row["order_id"])] = _money(line_value(qty, price, disc))
    return out


def _sql_line_values(conn):
    out = {}
    rows = fetch_df(conn, "SELECT order_id, line_value FROM v_line_value")
    for _, row in rows.iterrows():
        value = row["line_value"]
        if value is None or (not isinstance(value, str) and pd.isna(value)):
            value = None
        out[str(row["order_id"])] = _money(value)
    return out


def _norm_result_frame(df):
    out = df.copy()
    out["source_row_number"] = out["source_row_number"].astype(int)
    out["result"] = out["result"].astype(str)
    out["failing_detail"] = out["failing_detail"].astype(str)
    return out.sort_values(["source_row_number", "result",
                            "failing_detail"]).reset_index(drop=True)


def _py_rule_frame(impl, orders, ctx):
    frame = impl(orders, ctx)[["result", "failing_detail"]].copy()
    frame.insert(0, "source_row_number",
                 orders["source_row_number"].astype(int).values)
    return _norm_result_frame(frame)


def _sql_rule_frame(conn, view):
    return _norm_result_frame(fetch_df(
        conn, f"SELECT source_row_number, result, failing_detail FROM {view}"))


class TestParityFixture:
    def test_line_value_matches(self):
        orders, customers, products = _fixture()
        conn = _db()
        try:
            _load_all(conn, orders, customers, products)
            sql_vals = _sql_line_values(conn)
        finally:
            conn.close()
        py_vals = _py_line_values(orders)
        assert sql_vals == py_vals
        assert py_vals["O1"] == Decimal("200.00")
        assert py_vals["O4"] == Decimal("180.00")
        assert py_vals["O6"] is None
        assert py_vals["O9"] == Decimal("200.00")
        assert py_vals["O10"] == Decimal("200.00")
        assert py_vals["O11"] == Decimal("179.98")

    def test_r01_matches(self):
        orders, customers, products = _fixture()
        ctx = _ctx_for(customers, products)
        py = _py_rule_frame(_r01_customer_exists, orders, ctx)
        conn = _db()
        try:
            _load_all(conn, orders, customers, products)
            sql = _sql_rule_frame(conn, "v_r01_customer_exists")
        finally:
            conn.close()
        pd.testing.assert_frame_equal(py, sql)
        assert py[py["source_row_number"] == 2]["result"].iloc[0] == "PASS"
        assert py[py["source_row_number"] == 3]["result"].iloc[0] == "FAIL"

    def test_r03_matches(self):
        orders, customers, products = _fixture()
        ctx = _ctx_for(customers, products)
        py = _py_rule_frame(_r03_signup_before_order, orders, ctx)
        conn = _db()
        try:
            _load_all(conn, orders, customers, products)
            sql = _sql_rule_frame(conn, "v_r03_signup_before_order")
        finally:
            conn.close()
        pd.testing.assert_frame_equal(py, sql)
        assert py[py["source_row_number"] == 8]["result"].iloc[0] == "PASS"
        assert py[py["source_row_number"] == 9]["result"].iloc[0] == "PASS"
        assert py[py["source_row_number"] == 10]["result"].iloc[0] == "PASS"

    def test_r06_matches(self):
        orders, customers, products = _fixture()
        ctx = _ctx_for(customers, products)
        py = _py_rule_frame(_r06_valid_price, orders, ctx)
        conn = _db()
        try:
            _load_all(conn, orders, customers, products)
            sql = _sql_rule_frame(conn, "v_r06_valid_price")
        finally:
            conn.close()
        pd.testing.assert_frame_equal(py, sql)
        row5 = py[py["source_row_number"] == 5].iloc[0]
        assert row5["result"] == "PASS"
        assert row5["failing_detail"] == "within_tolerance"
        row11 = py[py["source_row_number"] == 11].iloc[0]
        assert row11["result"] == "FAIL"
        assert row11["failing_detail"] == "outside_tolerance"


class TestParityRealData:
    def _real(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        data = root / "data"
        orders = pd.read_csv(data / "clean_orders.csv", dtype=str,
                             keep_default_na=False, encoding="utf-8")
        customers = pd.read_csv(data / "customer_master.csv", dtype=str,
                                keep_default_na=False, encoding="utf-8")
        products = pd.read_csv(data / "products_clean.csv", dtype=str,
                               keep_default_na=False, encoding="utf-8")
        return orders, customers, products

    def test_line_value_matches(self):
        orders, customers, products = self._real()
        assert orders["order_id"].is_unique
        conn = _db()
        try:
            _load_all(conn, orders, customers, products)
            sql_vals = _sql_line_values(conn)
        finally:
            conn.close()
        py_vals = _py_line_values(orders)
        assert sql_vals == py_vals

    def test_r01_matches(self):
        orders, customers, products = self._real()
        ctx = _ctx_for(customers, products)
        py = _py_rule_frame(_r01_customer_exists, orders, ctx)
        conn = _db()
        try:
            _load_all(conn, orders, customers, products)
            sql = _sql_rule_frame(conn, "v_r01_customer_exists")
        finally:
            conn.close()
        pd.testing.assert_frame_equal(py, sql)

    def test_r03_matches(self):
        orders, customers, products = self._real()
        ctx = _ctx_for(customers, products)
        py = _py_rule_frame(_r03_signup_before_order, orders, ctx)
        conn = _db()
        try:
            _load_all(conn, orders, customers, products)
            sql = _sql_rule_frame(conn, "v_r03_signup_before_order")
        finally:
            conn.close()
        pd.testing.assert_frame_equal(py, sql)

    def test_r06_matches(self):
        orders, customers, products = self._real()
        ctx = _ctx_for(customers, products)
        py = _py_rule_frame(_r06_valid_price, orders, ctx)
        conn = _db()
        try:
            _load_all(conn, orders, customers, products)
            sql = _sql_rule_frame(conn, "v_r06_valid_price")
        finally:
            conn.close()
        pd.testing.assert_frame_equal(py, sql)
