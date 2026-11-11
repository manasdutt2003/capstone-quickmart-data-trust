"""Scratch probe: q69 plan text (deleted after)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))

from test_sql_executes import _db, _run_file, QUESTIONS, apply_sql_file
from src.pg import fetch_df

conn = _db()
try:
    for name in ("00_staging.sql", "v_line_value.sql", "08_rule_views.sql",
                 "07_trusted_populations.sql"):
        apply_sql_file(conn, name)
    frame = _run_file(conn, QUESTIONS / "seg7_q69.sql")
    print("\n".join(frame.iloc[:, 0].astype(str)))
finally:
    conn.close()
