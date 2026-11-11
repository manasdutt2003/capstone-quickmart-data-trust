"""Scratch probe: run seg6/seg7 SQL files, print row counts (deleted after)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))

import test_sql_executes as t

conn = t._db()
try:
    # Reuse fixture setup by calling the fixture function directly
    gen = t.db.__wrapped__()
    conn2 = next(gen)
    try:
        t.test_core_files_execute(conn2)
        for path in sorted(t.QUESTIONS.glob("seg6*.sql")) + sorted(
                t.QUESTIONS.glob("seg7*.sql")):
            try:
                frame = t._run_file(conn2, path)
                n = "None" if frame is None else len(frame)
                print(f"{path.name}: rows={n}")
                if frame is not None and len(frame) and len(frame) <= 8:
                    print(frame.to_string())
            except Exception as exc:
                print(f"{path.name}: ERROR {str(exc)[:220]}")
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
finally:
    conn.close()
