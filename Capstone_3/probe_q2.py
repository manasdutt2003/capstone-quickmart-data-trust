"""Scratch probe: q71/q75 SQL vs Python detail (deleted after)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))

import pandas as pd
from test_sql_executes import _db, _run_file, QUESTIONS, apply_sql_file

conn = _db()
try:
    for name in ("00_staging.sql", "v_line_value.sql", "08_rule_views.sql",
                 "07_trusted_populations.sql"):
        apply_sql_file(conn, name)
    q71 = _run_file(conn, QUESTIONS / "seg7_q71.sql")
    print("q71 rows:", len(q71))
    print(q71.head(10).to_string())
    q75 = _run_file(conn, QUESTIONS / "seg7_q75.sql")
    print("q75 SQL:")
    print(q75.to_string())
finally:
    conn.close()

from src.questions.seg7_professional_sql import q71_p95_exact_vs_approx, q75_scorecard
from src.validation_rules import Context
from src.mapping_gate import load_mapping

ROOT = Path("C:/Users/manas.dutt/Desktop/GGTP_BLR_DP_SEP_26/Projects/Individual/Manas Dutt/Week 3/QuickMart")
trusted = pd.read_csv(ROOT / "outputs" / "trusted_orders.csv", dtype=str, keep_default_na=False, encoding="utf-8")
customers = pd.read_csv(ROOT / "data" / "customer_master.csv", dtype=str, keep_default_na=False, encoding="utf-8")
products = pd.read_csv(ROOT / "data" / "products_clean.csv", dtype=str, keep_default_na=False, encoding="utf-8")
ctx = Context(customers=customers, products=products, city_map=load_mapping("city"),
              cat_map=load_mapping("category"), pay_map=load_mapping("payment"),
              status_map=load_mapping("status"))
args = (trusted, customers, products, ctx)
py71, _ = q71_p95_exact_vs_approx(*args)
print("py71 rows:", len(py71))
print(py71.head(10).to_string())
py75, _ = q75_scorecard(*args)
print("py75:")
print(py75.to_string())
