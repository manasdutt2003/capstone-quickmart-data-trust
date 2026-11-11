"""Execute every sql/*.sql then sql/questions/*.sql against staging.

Staging tables are loaded from the cleaned pipeline outputs as TEXT
(orders_clean <- data/clean_orders.csv, customers_master <-
data/customer_master.csv, products_clean <- data/products_clean.csv,
rule_failure_log <- outputs/rule_failure_log.csv), plus the load-level
text layers for the segment 1-3 question files (orders_loaded <-
data/orders_clean.csv, customers_loaded <- data/customers_clean.csv,
customers_raw <- the verbatim raw customers extract in file order,
quality_datamart <- data/quality_datamart.csv for the Q29 top-3 check).
Alias views
(orders, customers, products, payment_mapping) and mapping tables mirror
the documented prerequisites of the question files. Files run in
dependency order (views before use), not glob order. Any syntax error
or unresolved reference fails. Required results must be non-empty,
except seg4_q33 (no product is never ordered) and 06_segment6_9_answers
(its 10k running-total threshold exceeds the data: the max customer
running total is 9930), where empty is the correct result. SQL row
counts must equal the Python populations for dedup, trusted, strict,
lenient and rejected.
"""

from pathlib import Path

import pandas as pd
import psycopg
import pytest

from src.data_loader import load_raw
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

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql"
QUESTIONS = SQL / "questions"


def _repo_root():
    """Walk up from the QuickMart dir to the git repo root (contains .git).

    Mirrors src.pipeline._repo_root without importing that module (it pulls
    matplotlib); used only to find the raw customers extract for staging.
    """
    p = ROOT
    for _ in range(8):
        if (p / ".git").exists():
            return p
        p = p.parent
    return ROOT


RAW_DIR = _repo_root() / "Resources/Capstone Questions/Capstone 2/data"

CORE_ORDER = [
    "00_staging.sql",
    "v_line_value.sql",
    "08_rule_views.sql",
    "07_trusted_populations.sql",
    "01_profile_views.sql",
    "02_quality_scorecard.sql",
    "03_dedup.sql",
    "04_trusted_orders.sql",
    "05_marts.sql",
    "06_segment6_9_answers.sql",
]

MAP_FILES = {
    "city_map": "city_map.csv",
    "category_map": "category_map.csv",
    "status_map": "order_status_map.csv",
    "pay_map": "payment_mode_map.csv",
}


def _read_text_csv(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False,
                       encoding="utf-8")


def _mapping_pairs(filename):
    """First two columns of a mapping CSV (rationales may hold commas)."""
    import csv

    pairs = []
    with open(ROOT / "mappings" / "proposed" / filename, encoding="utf-8",
              newline="") as fh:
        reader = csv.reader(fh)
        next(reader)
        for row in reader:
            if row:
                pairs.append((row[0], row[1] if len(row) > 1 else ""))
    return pairs


def _statements(text):
    """Split SQL text into statements (headers may hold stray semicolons)."""
    code = "\n".join(
        line for line in text.splitlines()
        if not line.strip().startswith("--")
    )
    return [s for s in (part.strip() for part in code.split(";")) if s]


def _db():
    """Connect, skip, or fail-fast (twin of the parity-module helper)."""
    if should_fail_fast():
        return connect()
    backend, reason = resolve_backend()
    if backend == "none":
        pytest.skip(f"sql executes tests skipped: {reason}")
    try:
        return connect()
    except (psycopg.Error, OSError) as exc:
        pytest.skip(f"sql executes tests skipped: cannot connect ({exc})")


def stage_db(conn):
    """(Re)build the full staging state (tables, maps, alias views).

    Shared by the module fixture and the SQL output exporter so both
    always stage identically.
    """
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
                  "rule_failure_log", "orders_loaded", "customers_loaded",
                  "customers_raw", "quality_datamart"):
        conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    for table in ("city_map", "category_map", "status_map", "pay_map",
                  "payment_mapping"):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    apply_sql_file(conn, "00_staging.sql")
    orders = _read_text_csv(ROOT / "data" / "clean_orders.csv")
    customers = _read_text_csv(ROOT / "data" / "customer_master.csv")
    products = _read_text_csv(ROOT / "data" / "products_clean.csv")
    orders_loaded = _read_text_csv(ROOT / "data" / "orders_clean.csv")
    customers_loaded = _read_text_csv(ROOT / "data" / "customers_clean.csv")
    failures = _read_text_csv(ROOT / "outputs" / "rule_failure_log.csv")
    load_frame(conn, "orders_clean", orders, ORDERS_COLUMNS)
    load_frame(conn, "customers_master", customers, CUSTOMERS_COLUMNS)
    load_frame(conn, "products_clean", products, PRODUCTS_COLUMNS)
    load_frame(conn, "orders_loaded", orders_loaded, ORDERS_COLUMNS)
    load_frame(conn, "customers_loaded", customers_loaded, CUSTOMERS_COLUMNS)
    header, raw_rows = load_raw(RAW_DIR / "customers.csv", "customers")
    customers_raw = pd.DataFrame(raw_rows, columns=header)
    customers_raw["_source_row"] = [str(i) for i in
                                    range(1, len(customers_raw) + 1)]
    load_frame(conn, "customers_raw", customers_raw,
               header + ["_source_row"])
    quality_datamart = _read_text_csv(ROOT / "data" / "quality_datamart.csv")
    conn.execute(
        "CREATE TABLE quality_datamart ("
        + ", ".join(f"{col} TEXT" for col in quality_datamart.columns) + ")")
    load_frame(conn, "quality_datamart", quality_datamart,
               list(quality_datamart.columns))
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
    return conn


@pytest.fixture(scope="module")
def db():
    conn = _db()
    try:
        yield stage_db(conn)
    finally:
        conn.close()


def _run_file(conn, path):
    """Execute every statement; fetch the trailing SELECT, if any."""
    parts = _statements(path.read_text(encoding="utf-8"))
    assert parts, f"{path.name}: no statements"
    for part in parts[:-1]:
        conn.execute(part)
    last = parts[-1]
    if last.lstrip().upper().startswith(("SELECT", "WITH", "EXPLAIN")):
        return fetch_df(conn, last)
    conn.execute(last)
    return None


def test_core_files_execute(db):
    for name in CORE_ORDER:
        apply_sql_file(db, name)


def test_required_results_nonempty(db):
    test_core_files_execute(db)
    assert len(fetch_df(db, "SELECT * FROM v_column_profile")) == 62
    assert len(fetch_df(db, "SELECT * FROM quality_inputs")) == 3
    assert len(fetch_df(db, "SELECT * FROM v_quality_scorecard")) == 3
    assert len(fetch_df(db, "SELECT * FROM v_trusted_lenient")) > 0
    assert len(fetch_df(db, "SELECT * FROM v_trusted_strict")) > 0
    assert len(fetch_df(db, "SELECT * FROM v_rejected_orders")) > 0
    assert len(fetch_df(db, "SELECT * FROM trusted_enriched")) > 0
    stages = fetch_df(db, (SQL / "04_trusted_orders.sql").read_text(
        encoding="utf-8"))
    assert set(stages["stage_name"]) == {"trusted", "strict", "rejected",
                                         "completed"}
    assert len(fetch_df(db, (SQL / "05_marts.sql").read_text(
        encoding="utf-8"))) > 0
    # 06 is execute-only: its 10k running-total threshold exceeds the data
    # (max customer running total is 9930), so empty is the correct answer.
    apply_sql_file(db, "06_segment6_9_answers.sql")


def _dedup_count(db):
    parts = _statements((SQL / "03_dedup.sql").read_text(encoding="utf-8"))
    for part in parts[:-1]:
        db.execute(part)
    return len(fetch_df(db, parts[-1]))


def test_counts_match_python(db):
    test_core_files_execute(db)
    clean = _read_text_csv(ROOT / "data" / "clean_orders.csv")
    assert _dedup_count(db) == len(clean)
    for view, filename in (("v_trusted_lenient", "trusted_orders.csv"),
                           ("v_trusted_strict", "strict_trusted_orders.csv"),
                           ("v_trusted_lenient", "lenient_trusted_orders.csv"),
                           ("v_rejected_orders", "rejected_orders.csv")):
        sql_n = len(fetch_df(db, f"SELECT * FROM {view}"))
        py_n = len(_read_text_csv(ROOT / "outputs" / filename))
        assert sql_n == py_n, f"{view}: sql={sql_n} python={py_n}"


def test_questions_execute(db):
    test_core_files_execute(db)
    files = sorted(QUESTIONS.glob("seg*.sql"))
    # Q1-3+Q5-8+Q10-29 (27; Q4/Q9 are loader-level, no SQL) + Q30-49 (20)
    # + Q50-75 (26) + Q76-125 (50) = 123 question files
    assert len(files) == 123
    for path in files:
        frame = _run_file(db, path)
        if path.name in ("seg4_q33.sql", "seg6_q50.sql", "seg6_q63.sql",
                         "seg6_q67.sql", "seg9_q92.sql", "seg9_q95.sql",
                         "seg9_q100.sql", "seg9_q102.sql",
                         "seg9_q123.sql"):
            assert frame is not None and len(frame) == 0
        else:
            assert frame is not None and len(frame) > 0, path.name
