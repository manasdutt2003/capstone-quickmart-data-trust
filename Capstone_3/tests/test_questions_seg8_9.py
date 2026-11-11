"""SQL <-> Python parity for Q76-Q125 (Segments 8-9).

Each test runs the sql/questions/segN_qNN.sql twin and the
src/questions/seg8_expert_sql.py / seg9a|b|c_expert_data.py twin over
the same population (Sprint-3 lenient trusted orders + masters) and
compares normalized results.

Normalization: per column, try float (tolerance 0.011 for NUMERIC vs
float transport, matching the seg6_7 suite); else NULL/NaN -> "" and
string compare. Rows sorted. Empty is a legitimate answer for Q92
(no shared emails), Q95 (no 4-month rise), Q100 (no same-day pairs),
Q102 (no 10th order) and Q123 (nobody covers all categories); both
sides must agree on empty.

Q120 is a view test: the SQL creates v_completed_line_values and the
test asserts the view exposes no raw price text.
"""

import pandas as pd
import pytest

from src.mapping_gate import load_mapping
from src.pg import (
    CUSTOMERS_COLUMNS,
    ORDERS_COLUMNS,
    PRODUCTS_COLUMNS,
    apply_sql_file,
    fetch_df,
    load_frame,
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


def _real_frames():
    trusted = _read_text_csv(ROOT / "outputs" / "trusted_orders.csv")
    customers = _read_text_csv(ROOT / "data" / "customer_master.csv")
    products = _read_text_csv(ROOT / "data" / "products_clean.csv")
    return trusted, customers, products


def _ctx_for(customers, products):
    return Context(
        customers=customers,
        products=products,
        city_map=load_mapping("city"),
        cat_map=load_mapping("category"),
        pay_map=load_mapping("payment"),
        status_map=load_mapping("status"),
    )


def _args(frames):
    return (frames["trusted"], frames["customers"], frames["products"],
            frames["ctx"])


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

QMAP_A = {
    "q78_mom_by_city": "seg9_q78.sql",
    "q79_median_gap": "seg9_q79.sql",
    "q80_three_recent_nondelivered": "seg9_q80.sql",
    "q81_top10pct_share": "seg9_q81.sql",
    "q82_longest_zero_run": "seg9_q82.sql",
    "q83_except_vs_not_exists": "seg9_q83.sql",
    "q84_second_highest": "seg9_q84.sql",
    "q85_discount_implied_gap": "seg9_q85.sql",
    "q86_latest_three_array": "seg9_q86.sql",
    "q95_four_rising_months": "seg9_q95.sql",
    "q96_paid_over_catalogue": "seg9_q96.sql",
    "q97_ma_yoy": "seg9_q97.sql",
    "q98_latest_payment_switch": "seg9_q98.sql",
    "q99_top2_ranks_city": "seg9_q99.sql",
    "q100_same_day_pairs": "seg9_q100.sql",
    "q101_delivery_pivot": "seg9_q101.sql",
    "q102_tenth_order": "seg9_q102.sql",
    "q103_never_completed": "seg9_q103.sql",
    "q104_notes_vs_late": "seg9_q104.sql",
    "q105_top_product_lateral": "seg9_q105.sql",
    "q106_cte_reconcile": "seg9_q106.sql",
    "q107_first_above_avg": "seg9_q107.sql",
    "q108_orders_prior_30d": "seg9_q108.sql",
    "q109_qty_outliers": "seg9_q109.sql",
}

QMAP_B = {
    "q113_cancel_rate_p90": "seg9_q113.sql",
    "q114_units_per_product_month": "seg9_q114.sql",
    "q115_city_count_drops": "seg9_q115.sql",
    "q116_gini_by_city": "seg9_q116.sql",
    "q117_mode_vs_recent": "seg9_q117.sql",
    "q118_delivery_bands": "seg9_q118.sql",
    "q119_signup_cohort_speed": "seg9_q119.sql",
    "q120_completed_view_check": "seg9_q120.sql",
    "q121_empty_city_category": "seg9_q121.sql",
    "q122_rank1_three_months": "seg9_q122.sql",
    "q123_division_all_categories": "seg9_q123.sql",
    "q124_price_mismatch_spikes": "seg9_q124.sql",
    "q125_mega_top3": "seg9_q125.sql",
}

QMAP_C = {
    "q87_grouping_sets": "seg9_q87.sql",
    "q88_median_monthly_qty": "seg9_q88.sql",
    "q89_range_90d": "seg9_q89.sql",
    "q90_cohort": "seg9_q90.sql",
    "q91_p95_flags": "seg9_q91.sql",
    "q92_dup_email_pairs": "seg9_q92.sql",
    "q93_180d_categories": "seg9_q93.sql",
    "q94_herfindahl": "seg9_q94.sql",
    "q110_id_mismatches": "seg9_q110.sql",
    "q111_share_shift": "seg9_q111.sql",
    "q112_pairs_top5": "seg9_q112.sql",
}


def _sql(path, db):
    return _run_file(db, QUESTIONS / path)


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    s = str(v).strip()
    if s in ("", "None", "nan", "NaN", "NaT", "NULL", "<NA>", "null"):
        return ""
    return s


def _cells_equal(a, b):
    """One cell pair: both empty, both numeric within tol, else strings."""
    ca, cb = _cell(a), _cell(b)
    if ca == "" and cb == "":
        return True
    if ca == "" or cb == "":
        return False
    try:
        return abs(float(ca) - float(cb)) <= 0.011
    except (TypeError, ValueError):
        return ca == cb


def _frames_match(sql, py):
    """Same columns, same multiset of rows, tolerant cells."""
    assert set(sql.columns) == set(py.columns), (
        f"columns differ: sql={list(sql.columns)} py={list(py.columns)}")
    assert len(sql) == len(py), f"row counts differ: {len(sql)} vs {len(py)}"
    if len(sql) == 0:
        return
    cols = list(sql.columns)
    srows = sorted(
        tuple(_cell(v) for v in row)
        for row in sql[cols].itertuples(index=False))
    prows = sorted(
        tuple(_cell(v) for v in row)
        for row in py[cols].itertuples(index=False))
    bad = [(s, p) for s, p in zip(srows, prows)
           if not all(_cells_equal(a, b) for a, b in zip(s, p))]
    assert not bad, f"{len(bad)} mismatched rows, e.g. {bad[:3]}"


def _mod(name):
    import importlib
    return importlib.import_module(f"src.questions.{name}")


A9 = "seg9a_expert_data"
B9 = "seg9b_expert_data"
C9 = "seg9c_expert_data"
S8 = "seg8_expert_sql"


class TestSeg8Parity:
    def test_q76_counterexample(self, frames, db):
        sql = _sql("seg8_q76.sql", db)
        py, _ = _mod(S8).q76_lateral_equivalence()
        _frames_match(sql, py)
        assert bool(sql["agree_with_tiebreak"].iloc[0]) is True

    def test_q77_sums(self, frames, db):
        sql = _sql("seg8_q77.sql", db)
        py, _ = _mod(S8).q77_float_sum_order(*_args(frames))
        _frames_match(sql, py[["city_std", "sum_asc", "sum_desc", "diff",
                               "differs_at_cent"]])


class TestSeg9AParity:
    def test_q78_mom(self, frames, db):
        sql = _sql(QMAP_A["q78_mom_by_city"], db)
        py, _ = _mod(A9).q78_mom_by_city(*_args(frames))
        _frames_match(sql, py)

    def test_q79_gaps(self, frames, db):
        sql = _sql(QMAP_A["q79_median_gap"], db)
        py, _ = _mod(A9).q79_median_gap(*_args(frames))
        _frames_match(sql, py)

    def test_q80_recent(self, frames, db):
        sql = _sql(QMAP_A["q80_three_recent_nondelivered"], db)
        py, _ = _mod(A9).q80_three_recent_nondelivered(*_args(frames))
        _frames_match(sql, py)

    def test_q81_share(self, frames, db):
        sql = _sql(QMAP_A["q81_top10pct_share"], db)
        py, _ = _mod(A9).q81_top10pct_share(*_args(frames))
        _frames_match(sql, py)

    def test_q82_run(self, frames, db):
        sql = _sql(QMAP_A["q82_longest_zero_run"], db)
        py, _ = _mod(A9).q82_longest_zero_run(*_args(frames))
        _frames_match(sql, py)

    def test_q83_halves(self, frames, db):
        sql = _sql(QMAP_A["q83_except_vs_not_exists"], db)
        py, _ = _mod(A9).q83_except_vs_not_exists(*_args(frames))
        _frames_match(sql, py)

    def test_q84_second(self, frames, db):
        sql = _sql(QMAP_A["q84_second_highest"], db)
        py, _ = _mod(A9).q84_second_highest(*_args(frames))
        _frames_match(sql, py)

    def test_q85_gap(self, frames, db):
        sql = _sql(QMAP_A["q85_discount_implied_gap"], db)
        py, _ = _mod(A9).q85_discount_implied_gap(*_args(frames))
        assert set(sql["order_id"].astype(str)) == set(
            py["order_id"].astype(str))
        merged = sql.merge(py, on="order_id", suffixes=("_sql", "_py"))
        assert all(_cells_equal(a, b) for a, b in
                   zip(merged["abs_gap_sql"], merged["abs_gap_py"]))

    def test_q86_arrays(self, frames, db):
        sql = _sql(QMAP_A["q86_latest_three_array"], db)
        py, _ = _mod(A9).q86_latest_three_array(*_args(frames))
        _frames_match(sql, py)

    def test_q95_empty(self, frames, db):
        sql = _sql(QMAP_A["q95_four_rising_months"], db)
        py, _ = _mod(A9).q95_four_rising_months(*_args(frames))
        assert sql is not None and len(sql) == 0
        assert py["n"] == 0

    def test_q96_catalogue(self, frames, db):
        sql = _sql(QMAP_A["q96_paid_over_catalogue"], db)
        py, _ = _mod(A9).q96_paid_over_catalogue(*_args(frames))
        assert set(sql["order_id"].astype(str)) == set(
            py["order_id"].astype(str))

    def test_q97_yoy(self, frames, db):
        sql = _sql(QMAP_A["q97_ma_yoy"], db)
        py, _ = _mod(A9).q97_ma_yoy(*_args(frames))
        _frames_match(sql, py[["category_std", "order_month", "value",
                               "ma_3m", "yoy_value"]])

    def test_q98_pairs(self, frames, db):
        sql = _sql(QMAP_A["q98_latest_payment_switch"], db)
        py, _ = _mod(A9).q98_latest_payment_switch(*_args(frames))
        _frames_match(sql, py["pairs"])

    def test_q99_ranks(self, frames, db):
        sql = _sql(QMAP_A["q99_top2_ranks_city"], db)
        py, _ = _mod(A9).q99_top2_ranks_city(*_args(frames))
        _frames_match(sql, py)

    def test_q100_empty(self, frames, db):
        sql = _sql(QMAP_A["q100_same_day_pairs"], db)
        py, _ = _mod(A9).q100_same_day_pairs(*_args(frames))
        assert sql is not None and len(sql) == 0
        assert len(py) == 0

    def test_q101_pivot(self, frames, db):
        sql = _sql(QMAP_A["q101_delivery_pivot"], db)
        py, _ = _mod(A9).q101_delivery_pivot(*_args(frames))
        _frames_match(sql, py)

    def test_q102_empty(self, frames, db):
        sql = _sql(QMAP_A["q102_tenth_order"], db)
        py, _ = _mod(A9).q102_tenth_order(*_args(frames))
        assert sql is not None and len(sql) == 0
        assert py["n"] == 0

    def test_q103_methods(self, frames, db):
        sql = _sql(QMAP_A["q103_never_completed"], db)
        py, _ = _mod(A9).q103_never_completed(*_args(frames))
        sql = sql[sql["method"] != "NOT_IN_with_null_demo"]
        _frames_match(sql, py)

    def test_q104_notes(self, frames, db):
        sql = _sql(QMAP_A["q104_notes_vs_late"], db)
        py, _ = _mod(A9).q104_notes_vs_late(*_args(frames))
        _frames_match(sql, py)

    def test_q105_lateral(self, frames, db):
        sql = _sql(QMAP_A["q105_top_product_lateral"], db)
        py, _ = _mod(A9).q105_top_product_lateral(*_args(frames))
        _frames_match(sql[["customer_id", "product_id", "price"]], py)
        assert sql["agrees_with_first_value"].astype(str).str.lower().eq(
            "true").all()

    def test_q106_reconcile(self, frames, db):
        sql = _sql(QMAP_A["q106_cte_reconcile"], db)
        py, _ = _mod(A9).q106_cte_reconcile(*_args(frames))
        assert abs(float(sql[sql["cut"] == "grand_total"]["total_value"]
                           .iloc[0]) - py["grand"]) < 0.01
        assert py["ok"] is True

    def test_q107_first(self, frames, db):
        sql = _sql(QMAP_A["q107_first_above_avg"], db)
        py, _ = _mod(A9).q107_first_above_avg(*_args(frames))
        _frames_match(sql, py)

    def test_q108_prior(self, frames, db):
        sql = _sql(QMAP_A["q108_orders_prior_30d"], db)
        py, _ = _mod(A9).q108_orders_prior_30d(*_args(frames))
        _frames_match(sql[["order_id", "prior_30d"]], py)
        assert sql["engines_agree"].astype(str).str.lower().eq(
            "true").all()

    def test_q109_outliers(self, frames, db):
        sql = _sql(QMAP_A["q109_qty_outliers"], db)
        py, _ = _mod(A9).q109_qty_outliers(*_args(frames))
        before_sql = set(sql[sql["outlier_before"].astype(str).str.lower()
                             == "true"]["customer_id"].astype(str))
        after_sql = set(sql[sql["outlier_after"].astype(str).str.lower()
                            == "true"]["customer_id"].astype(str))
        assert before_sql == set(py["before"])
        assert after_sql == set(py["after"])


class TestSeg9BParity:
    def test_q113_p90(self, frames, db):
        sql = _sql(QMAP_B["q113_cancel_rate_p90"], db)
        py, _ = _mod(B9).q113_cancel_rate_p90(*_args(frames))
        _frames_match(sql, py["customers"])
        assert py["n"] == len(sql) == 1

    def test_q114_units(self, frames, db):
        sql = _sql(QMAP_B["q114_units_per_product_month"], db)
        py, _ = _mod(B9).q114_units_per_product_month(*_args(frames))
        _frames_match(sql, py)

    def test_q115_drops(self, frames, db):
        sql = _sql(QMAP_B["q115_city_count_drops"], db)
        py, _ = _mod(B9).q115_city_count_drops(*_args(frames))
        _frames_match(sql, py)

    def test_q116_gini(self, frames, db):
        sql = _sql(QMAP_B["q116_gini_by_city"], db)
        py, _ = _mod(B9).q116_gini_by_city(*_args(frames))
        _frames_match(sql, py)

    def test_q117_modes(self, frames, db):
        sql = _sql(QMAP_B["q117_mode_vs_recent"], db)
        py, _ = _mod(B9).q117_mode_vs_recent(*_args(frames))
        _frames_match(sql, py)

    def test_q118_bands(self, frames, db):
        sql = _sql(QMAP_B["q118_delivery_bands"], db)
        py, _ = _mod(B9).q118_delivery_bands(*_args(frames))
        _frames_match(sql, py)

    def test_q119_cohort(self, frames, db):
        sql = _sql(QMAP_B["q119_signup_cohort_speed"], db)
        py, _ = _mod(B9).q119_signup_cohort_speed(*_args(frames))
        _frames_match(sql[["signup_month", "median_lag_days"]],
                      py[["signup_month", "median_lag_days"]])

    def test_q120_view(self, frames, db):
        sql = _sql(QMAP_B["q120_completed_view_check"], db)
        py, _ = _mod(B9).q120_completed_view_check(*_args(frames))
        assert py["check"].tolist() == ["view_columns_subset_of_allowed",
                                        "no_raw_price_text"]
        assert py["passed"].tolist() == [True, True]
        cols = fetch_df(db, "SELECT column_name FROM information_schema.columns"
                            " WHERE table_name = 'v_completed_line_values'")
        names = set(cols["column_name"].astype(str))
        assert "unit_price_paid" not in names
        assert {"order_id", "line_value"} <= names
        assert len(sql) > 0

    def test_q121_gaps(self, frames, db):
        sql = _sql(QMAP_B["q121_empty_city_category"], db)
        py, _ = _mod(B9).q121_empty_city_category(*_args(frames))
        _frames_match(sql, py)

    def test_q122_rank1(self, frames, db):
        sql = _sql(QMAP_B["q122_rank1_three_months"], db)
        py, _ = _mod(B9).q122_rank1_three_months(*_args(frames))
        _frames_match(sql, py)

    def test_q123_empty(self, frames, db):
        sql = _sql(QMAP_B["q123_division_all_categories"], db)
        py, _ = _mod(B9).q123_division_all_categories(*_args(frames))
        assert sql is not None and len(sql) == 0
        assert len(py) == 0

    def test_q124_spikes(self, frames, db):
        sql = _sql(QMAP_B["q124_price_mismatch_spikes"], db)
        py, _ = _mod(B9).q124_price_mismatch_spikes(*_args(frames))
        _frames_match(sql, py[["ym", "category_std", "share_pct", "n",
                               "doubled"]])

    def test_q125_mega(self, frames, db):
        sql = _sql(QMAP_B["q125_mega_top3"], db)
        py, _ = _mod(B9).q125_mega_top3(*_args(frames))
        _frames_match(sql, py)


class TestSeg9CParity:
    def test_q87_sets(self, frames, db):
        sql = _sql(QMAP_C["q87_grouping_sets"], db)
        py, _ = _mod(C9).q87_grouping_sets(*_args(frames))
        grand_sql = float(sql[sql["kind"] == "grand"]["total_value"]
                          .iloc[0])
        assert abs(grand_sql - py["grand"]) < 0.01
        assert py["ok"] is True
        assert (sql["kind"] == "cell").sum() == py["cells"]

    def test_q88_median(self, frames, db):
        sql = _sql(QMAP_C["q88_median_monthly_qty"], db)
        py, _ = _mod(C9).q88_median_monthly_qty(*_args(frames))
        table = py["table"]
        assert set(sql["product_id"].astype(str)) == set(
            table["product_id"].astype(str))
        assert py["n"] == int(table["all_months_above"].sum()) == 0

    def test_q89_range(self, frames, db):
        sql = _sql(QMAP_C["q89_range_90d"], db)
        py, _ = _mod(C9).q89_range_90d(*_args(frames))
        _frames_match(sql, py)

    def test_q90_cohort(self, frames, db):
        sql = _sql(QMAP_C["q90_cohort"], db)
        py, _ = _mod(C9).q90_cohort(*_args(frames))
        _frames_match(sql, py)

    def test_q91_flags(self, frames, db):
        sql = _sql(QMAP_C["q91_p95_flags"], db)
        py, _ = _mod(C9).q91_p95_flags(*_args(frames))
        assert set(sql["order_id"].astype(str)) == set(
            py["flagged"]["order_id"].astype(str))
        assert py["n_city"] == 4 and py["n_changed"] == 2

    def test_q92_empty(self, frames, db):
        sql = _sql(QMAP_C["q92_dup_email_pairs"], db)
        py, _ = _mod(C9).q92_dup_email_pairs(*_args(frames))
        assert sql is not None and len(sql) == 0
        assert len(py) == 0

    def test_q93_window(self, frames, db):
        sql = _sql(QMAP_C["q93_180d_categories"], db)
        py, _ = _mod(C9).q93_180d_categories(*_args(frames))
        _frames_match(sql, py["table"])

    def test_q94_hhi(self, frames, db):
        sql = _sql(QMAP_C["q94_herfindahl"], db)
        py, _ = _mod(C9).q94_herfindahl(*_args(frames))
        _frames_match(sql, py)

    def test_q110_ids(self, frames, db):
        sql = _sql(QMAP_C["q110_id_mismatches"], db)
        py, _ = _mod(C9).q110_id_mismatches(*_args(frames))
        _frames_match(sql, py)

    def test_q111_movers(self, frames, db):
        sql = _sql(QMAP_C["q111_share_shift"], db)
        py, _ = _mod(C9).q111_share_shift(*_args(frames))
        _frames_match(sql[["category_std", "share_first_pct",
                           "share_second_pct", "shift_pp"]], py["all"])
        assert set(sql[sql["mover"].astype(str).str.lower() == "true"]
                       ["category_std"].astype(str)) == set(
            py["movers"]["category_std"].astype(str))

    def test_q112_pairs(self, frames, db):
        sql = _sql(QMAP_C["q112_pairs_top5"], db)
        py, _ = _mod(C9).q112_pairs_top5(*_args(frames))
        _frames_match(sql, py)
