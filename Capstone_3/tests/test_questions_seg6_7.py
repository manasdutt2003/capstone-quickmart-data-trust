"""SQL <-> Python parity for Q50-Q75 (Segments 6-7).

Each test runs the sql/questions/segN_qNN.sql twin and the
src/questions/seg6_advanced_sql.py / seg7_professional_sql.py twin over
the same population (Sprint-3 lenient trusted orders + masters loaded
from data/ and outputs/) and compares normalized results.

Normalization: numerics rounded to 2 dp (Decimal vs float transport),
NULL/NaN -> None, timestamps -> ISO date strings, rows sorted.
Empty is a legitimate answer for Q50 (no customer crosses 10000),
Q63 (no spikes) and Q67 (every delivered customer has dated delivery);
both sides must agree on empty.

Parity diagnosis log:
- Q52 completed stage first read 56: the inline rule approximations in
  the first draft disagreed with the registry. Fixed on the SQL side:
  the chain now joins the logged rule_failure_log verdicts (single
  source of truth stays in 08_rule_views.sql). SQL was wrong, Python
  (log-based) right.
- Q56 nested a window call inside LAG: Postgres forbids it. Fixed on
  the SQL side with a with_prev CTE. SQL was wrong, Python right.
- Q57/Q65 omitted RECURSIVE: fixed on the SQL side. SQL was wrong.
- Q62 referenced cnt inside an aggregate: fixed with a mid CTE.
- Q68 counted DISTINCT session_id (restarts per customer): fixed to
  COUNT(*). SQL was wrong, Python right.
- Q69 EXPLAIN is fetched by the harness (SELECT/WITH/EXPLAIN).
- Q71 has no APPROX_PERCENTILE builtin in PostgreSQL 16: both sides
  use a deterministic every-10th-row subsample, labelled as analogue.
- Q72 joins rule_failure_log on source_row_number via orders_clean
  (trusted_enriched carries no source_row_number; order_id alone is
  not a safe key because the log is keyed by source row).
- Q75 completeness first draft was row-based on the SQL side vs
  cell-based in Python: fixed on the SQL side to cell-based sums.
"""

import pandas as pd
import pytest

from src.mapping_gate import load_mapping
from src.pg import (
    CUSTOMERS_COLUMNS,
    ORDERS_COLUMNS,
    PRODUCTS_COLUMNS,
    apply_sql_file,
    load_frame,
)
from src.questions.seg6_advanced_sql import (
    q50_running_total_cross_10k,
    q51_avg_paid_20pct_above_catalogue,
    q52_cte_chain_counts,
    q53_quantity_range_check,
    q54_rank_disagreements,
    q55_new_payment_mode,
    q56_moving_avg_direction,
    q57_calendar_zero_cells,
    q58_city_top_bottom_product,
    q59_city_share_over_25pct,
    q60_dedup_determinism,
    q61_no_recent_month_multi_category,
    q62_median_delivery_percentile_vs_rank,
    q63_spike_detection,
    q64_function_tests,
    q65_longest_active_run,
    q66_grouping_sets,
    q67_missing_delivery_customers,
)
from src.questions.seg7_professional_sql import (
    q68_sessions,
    q69_plan_analysis,
    q70_referral_depth,
    q71_p95_exact_vs_approx,
    q72_lateral_rule_strings,
    q73_funnel,
    q74_transition_classes,
    q75_scorecard,
)
from src.validation_rules import Context
from tests.test_sql_executes import (
    MAP_FILES,
    QUESTIONS,
    ROOT,
    _mapping_pairs,
    _read_text_csv,
    _run_file,
)
from tests.test_sql_executes import (
    _db as _exec_db,
)


def _ctx_for(customers, products):
    return Context(
        customers=customers,
        products=products,
        city_map=load_mapping("city"),
        cat_map=load_mapping("category"),
        pay_map=load_mapping("payment"),
        status_map=load_mapping("status"),
    )


def _real_frames():
    trusted = _read_text_csv(ROOT / "outputs" / "trusted_orders.csv")
    customers = _read_text_csv(ROOT / "data" / "customer_master.csv")
    products = _read_text_csv(ROOT / "data" / "products_clean.csv")
    return trusted, customers, products


@pytest.fixture(scope="module")
def frames():
    trusted, customers, products = _real_frames()
    ctx = _ctx_for(customers, products)
    return {"trusted": trusted, "customers": customers,
            "products": products, "ctx": ctx}


@pytest.fixture(scope="module")
def db():
    conn = _exec_db()
    try:
        conn.execute("DROP VIEW IF EXISTS trusted_enriched CASCADE")
        for view in ("v_trusted_lenient", "v_trusted_strict",
                     "v_rejected_orders",
                     "v_column_profile", "quality_inputs",
                     "v_quality_scorecard", "v_d06_review_flags",
                     "v_line_value", "v_r01_customer_exists",
                     "v_r03_signup_before_order", "v_r06_valid_price",
                     "v_r06_valid_price_tol05", "v_run_params",
                     "orders", "customers", "products"):
            conn.execute(f"DROP VIEW IF EXISTS {view} CASCADE")
        for table in ("orders_clean", "customers_master", "products_clean",
                      "rule_failure_log"):
            conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        for table in ("city_map", "category_map", "status_map", "pay_map",
                      "payment_mapping"):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        apply_sql_file(conn, "00_staging.sql")
        orders = _read_text_csv(ROOT / "data" / "clean_orders.csv")
        customers = _read_text_csv(ROOT / "data" / "customer_master.csv")
        products = _read_text_csv(ROOT / "data" / "products_clean.csv")
        failures = _read_text_csv(ROOT / "outputs" / "rule_failure_log.csv")
        load_frame(conn, "orders_clean", orders, ORDERS_COLUMNS)
        load_frame(conn, "customers_master", customers, CUSTOMERS_COLUMNS)
        load_frame(conn, "products_clean", products, PRODUCTS_COLUMNS)
        conn.execute("TRUNCATE rule_failure_log")
        text = failures[["source_row_number", "order_id", "rule_id",
                         "result", "failing_detail"]].to_csv(
            index=False, encoding="utf-8", lineterminator="\n")
        with conn.cursor().copy(
                "COPY rule_failure_log (source_row_number, order_id, "
                "rule_id, result, failing_detail) "
                "FROM STDIN WITH (FORMAT csv, HEADER true)") as cp:
            cp.write(text)
        for table, filename in MAP_FILES.items():
            pairs = _mapping_pairs(filename)
            conn.execute(f"CREATE TABLE {table} "
                         f"(raw_value TEXT, standard_value TEXT)")
            text = pd.DataFrame(
                pairs, columns=["raw_value", "standard_value"]).to_csv(
                index=False, encoding="utf-8", lineterminator="\n")
            with conn.cursor().copy(
                    f"COPY {table} (raw_value, standard_value) "
                    f"FROM STDIN WITH (FORMAT csv, HEADER true)") as cp:
                cp.write(text)
        conn.execute("CREATE TABLE payment_mapping (raw TEXT, standard TEXT)")
        pairs = _mapping_pairs("payment_mode_map.csv")
        text = pd.DataFrame(pairs, columns=["raw", "standard"]).to_csv(
            index=False, encoding="utf-8", lineterminator="\n")
        with conn.cursor().copy("COPY payment_mapping (raw, standard) "
                                "FROM STDIN WITH (FORMAT csv, HEADER true)") as cp:
            cp.write(text)
        conn.execute("CREATE OR REPLACE VIEW orders AS "
                     "SELECT * FROM orders_clean")
        conn.execute("CREATE OR REPLACE VIEW customers AS "
                     "SELECT * FROM customers_master")
        conn.execute("CREATE OR REPLACE VIEW products AS "
                     "SELECT * FROM products_clean")
        apply_sql_file(conn, "v_line_value.sql")
        apply_sql_file(conn, "08_rule_views.sql")
        apply_sql_file(conn, "07_trusted_populations.sql")
        yield conn
    finally:
        conn.close()


def _sql(path, db):
    return _run_file(db, QUESTIONS / path)


def _norm(df):
    """Sort columns/rows, round numerics to 2 dp, None-normalize."""
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_numeric_dtype(out[col]):
            out[col] = pd.to_numeric(out[col], errors="coerce").round(2)
    out = out.astype(str).replace({"nan": "", "None": "", "NaT": ""})
    return out.sort_values(list(out.columns)).reset_index(drop=True)


def _close(a, b, tol=0.011):
    """Numeric closeness for SQL NUMERIC vs Python float tie-rounding.

    Postgres ROUND(numeric) is half-away-from-zero, Python round() is
    banker's; exact .xx5 ties can differ by 0.01. tol=0.011 admits
    only that documented residual.
    """
    return ((a.astype(float) - b.astype(float)).abs() <= tol).all()


def _args(frames):
    return (frames["trusted"], frames["customers"], frames["products"],
            frames["ctx"])


class TestSeg6Parity:
    def test_q50_empty_both(self, frames, db):
        sql = _sql("seg6_q50.sql", db)
        py, _ = q50_running_total_cross_10k(*_args(frames))
        assert sql is not None and len(sql) == 0
        assert py["n_crossed"] == 0
        assert py["n_never"] == py["n_valid_customers"] > 0

    def test_q51_products(self, frames, db):
        sql = _sql("seg6_q51.sql", db)
        py, _ = q51_avg_paid_20pct_above_catalogue(*_args(frames))
        assert set(sql["product_id"].astype(str)) == set(
            py["product_id"].astype(str))
        merged = sql.merge(py, on="product_id", suffixes=("_sql", "_py"))
        assert (merged["pct_above_sql"].astype(float).round(2)
                == merged["pct_above_py"].astype(float).round(2)).all()

    def test_q52_stages(self, frames, db):
        sql = _sql("seg6_q52.sql", db)
        py, _ = q52_cte_chain_counts(*_args(frames))
        sql_map = dict(zip(sql["stage"], sql["count"].astype(int)))
        py_map = dict(zip(py["stage"], py["count"]))
        assert sql_map == py_map
        assert sql_map["raw_orders"] == 6103
        assert sql_map["deduped"] == 6000
        assert sql_map["completed"] == 168

    def test_q53_cases(self, frames, db):
        sql = _sql("seg6_q53.sql", db)
        py, _ = q53_quantity_range_check(*_args(frames))
        pd.testing.assert_frame_equal(
            _norm(sql[["qty", "expected", "actual"]]),
            _norm(py[["qty", "expected", "actual"]]))
        assert sql["matches_expected"].astype(str).str.lower().eq(
            "true").all()

    def test_q54_disagreements(self, frames, db):
        sql = _sql("seg6_q54.sql", db)
        py, _ = q54_rank_disagreements(*_args(frames))
        assert set(sql["customer_id"].astype(str)) == set(
            py["customer_id"].astype(str))
        merged = sql.merge(py, on="customer_id", suffixes=("_sql", "_py"))
        assert (merged["rnk_sql"].astype(int)
                == merged["rnk_py"].astype(int)).all()
        assert (merged["dense_rnk_sql"].astype(int)
                == merged["dense_rnk_py"].astype(int)).all()
        assert (merged["row_n_sql"].astype(int)
                == merged["row_n_py"].astype(int)).all()

    def test_q55_new_mode(self, frames, db):
        sql = _sql("seg6_q55.sql", db)
        py, _ = q55_new_payment_mode(*_args(frames))
        assert len(sql) == py["n"]
        assert set(sql["customer_id"].astype(str)) == set(
            py["new_mode"]["customer_id"].astype(str))

    def test_q56_direction(self, frames, db):
        sql = _sql("seg6_q56.sql", db)
        py, _ = q56_moving_avg_direction(*_args(frames))
        sql_k = set(zip(sql["order_month"].astype(str),
                        sql["category_std"].astype(str)))
        py_k = set(zip(py["order_month"].astype(str),
                       py["category_std"].astype(str)))
        assert sql_k == py_k
        merged = sql.merge(py, on=["order_month", "category_std"],
                           suffixes=("_sql", "_py"))
        assert (merged["ma_3m_sql"].astype(float).round(2)
                == merged["ma_3m_py"].astype(float).round(2)).all()

    def test_q57_calendar(self, frames, db):
        sql = _sql("seg6_q57.sql", db)
        py, _ = q57_calendar_zero_cells(*_args(frames))
        assert len(sql) == py["cells"]
        assert int((sql["orders"].astype(int) == 0).sum()) == py["zero_filled"]

    def test_q58_top_bottom(self, frames, db):
        sql = _sql("seg6_q58.sql", db)
        py, _ = q58_city_top_bottom_product(*_args(frames))
        pd.testing.assert_frame_equal(
            _norm(sql), _norm(py[["city_std", "highest_product",
                                   "lowest_product"]]))

    def test_q59_share(self, frames, db):
        sql = _sql("seg6_q59.sql", db)
        py, _ = q59_city_share_over_25pct(*_args(frames))
        assert set(sql["customer_id"].astype(str)) == set(
            py["customer_id"].astype(str))
        merged = sql.merge(py, on="customer_id", suffixes=("_sql", "_py"))
        assert (merged["pct_of_city_sql"].astype(float).round(2)
                == merged["pct_of_city_py"].astype(float).round(2)).all()

    def test_q60_dedup(self, frames, db):
        sql = _sql("seg6_q60.sql", db)
        py, _ = q60_dedup_determinism(*_args(frames))
        assert len(sql) == py["survivors"] == 6000
        assert py["match"] is True

    def test_q61_no_recent(self, frames, db):
        sql = _sql("seg6_q61.sql", db)
        py, _ = q61_no_recent_month_multi_category(*_args(frames))
        assert set(sql["customer_id"].astype(str)) == set(py["customers"])

    def test_q62_median(self, frames, db):
        sql = _sql("seg6_q62.sql", db)
        py, _ = q62_median_delivery_percentile_vs_rank(*_args(frames))
        merged = sql.merge(py, on="city_std", suffixes=("_sql", "_py"))
        assert (merged["median_days"].astype(float).round(2)
                == merged["manual"].astype(float).round(2)).all()

    def test_q63_empty_both(self, frames, db):
        sql = _sql("seg6_q63.sql", db)
        py, _ = q63_spike_detection(*_args(frames))
        assert sql is not None and len(sql) == 0
        assert py["n_customers"] == 0

    def test_q64_function(self, frames, db):
        sql = _sql("seg6_q64.sql", db)
        py, _ = q64_function_tests(*_args(frames))
        normal_sql = sql[sql["test"] == "normal_range_2024"]
        assert set(normal_sql["category"].astype(str)) == set(
            py["normal_2024"]["category_std"].astype(str))
        merged = normal_sql.merge(py["normal_2024"], left_on="category",
                                  right_on="category_std",
                                  suffixes=("_sql", "_py"))
        assert (merged["total_value_sql"].astype(float).round(2)
                == merged["total_value_py"].astype(float).round(2)).all()
        assert (merged["total_orders_sql"].astype(int)
                == merged["total_orders_py"].astype(int)).all()
        assert py["early_2018_rows"] == 0
        assert py["inverted_detected"] is True

    def test_q65_runs(self, frames, db):
        sql = _sql("seg6_q65.sql", db)
        py, _ = q65_longest_active_run(*_args(frames))
        assert len(sql) == len(py) == 135
        merged = sql.merge(py, on="customer_id", suffixes=("_sql", "_py"))
        assert (merged["run_length_sql"].astype(int)
                == merged["run_length_py"].astype(int)).all()
        assert (merged["start_month_sql"].astype(str)
                == merged["start_month_py"].astype(str)).all()
        assert (merged["end_month_sql"].astype(str)
                == merged["end_month_py"].astype(str)).all()

    def test_q66_grouping_sets(self, frames, db):
        sql = _sql("seg6_q66.sql", db)
        py, _ = q66_grouping_sets(*_args(frames))
        grand_sql = float(sql[sql["category_std"].isna()
                              & sql["city_std"].isna()]["total_value"].iloc[0])
        assert abs(grand_sql - py["grand"]) < 0.01
        assert py["ok"] == True
        detail = sql[sql["category_std"].notna() & sql["city_std"].notna()]
        assert len(detail) == py["cells"]

    def test_q67_empty_both(self, frames, db):
        sql = _sql("seg6_q67.sql", db)
        py, _ = q67_missing_delivery_customers(*_args(frames))
        assert sql is not None and len(sql) == 0
        assert py["n"] == 0


class TestSeg7Parity:
    def test_q68_sessions(self, frames, db):
        sql = _sql("seg7_q68.sql", db)
        py, _ = q68_sessions(*_args(frames))
        assert int(sql["total_sessions"].iloc[0]) == py["total_sessions"]
        assert float(sql["median_session_length_min"].iloc[0]) == \
            py["median_session_length_min"]
        assert int(sql["sessions_over_10_events"].iloc[0]) == \
            py["sessions_over_10_events"]

    def test_q69_plan(self, frames, db):
        sql = _sql("seg7_q69.sql", db)
        py, _ = q69_plan_analysis(*_args(frames))
        plan = " ".join(sql.iloc[:, 0].astype(str))
        # Join strategy is planner/state-dependent; both sides agree a
        # join is used and record which one this run chose.
        assert "Join" in plan
        assert py["join_type"].startswith("Nested Loop")
        assert "partition" in py["proposal"].lower()
        assert len(py["tradeoff"]) > 20

    def test_q70_no_hierarchy(self, frames, db):
        sql = _sql("seg7_q70.sql", db)
        py, _ = q70_referral_depth(*_args(frames))
        assert int(sql["customers"].iloc[0]) == py["customers"] == 499
        assert int(sql["referral_chains"].iloc[0]) == py["referral_chains"] == 0
        assert int(sql["max_depth"].iloc[0]) == py["max_depth"] == 0

    def test_q71_p95(self, frames, db):
        sql = _sql("seg7_q71.sql", db)
        py, _ = q71_p95_exact_vs_approx(*_args(frames))
        sql_k = set(zip(sql["order_month"].astype(str),
                        sql["city_std"].astype(str)))
        py_k = set(zip(py["order_month"].astype(str),
                       py["city_std"].astype(str)))
        assert sql_k == py_k
        merged = sql.merge(py, on=["order_month", "city_std"],
                           suffixes=("_sql", "_py"))
        assert _close(merged["p95_exact_sql"], merged["p95_exact_py"])
        assert _close(merged["p95_approx_sql"], merged["p95_approx_py"])

    def test_q72_lateral(self, frames, db):
        sql = _sql("seg7_q72.sql", db)
        py, _ = q72_lateral_rule_strings(*_args(frames))
        assert len(sql) == len(py) == 168
        pd.testing.assert_frame_equal(
            _norm(sql[["order_id", "violated_rules"]]),
            _norm(py[["order_id", "violated_rules"]]))

    def test_q73_funnel(self, frames, db):
        sql = _sql("seg7_q73.sql", db)
        py, _ = q73_funnel(*_args(frames))
        pd.testing.assert_frame_equal(
            _norm(sql), _norm(py[["stage", "count"]]))

    def test_q74_classes(self, frames, db):
        sql = _sql("seg7_q74.sql", db)
        py, _ = q74_transition_classes(*_args(frames))
        pd.testing.assert_frame_equal(
            _norm(sql), _norm(py[["state_class", "status", "orders"]]))

    def test_q75_scorecard(self, frames, db):
        sql = _sql("seg7_q75.sql", db)
        py, _ = q75_scorecard(*_args(frames))
        merged = sql.merge(py, on="scope", suffixes=("_sql", "_py"))
        assert (merged["score_0_100_sql"].astype(float).round(2)
                == merged["score_0_100_py"].astype(float).round(2)).all()
