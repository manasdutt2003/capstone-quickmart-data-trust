"""Static guard: line value is defined exactly once in Python.

The formula may appear only in src/line_value.py. Every other module must
delegate to it. sql/v_line_value.sql is the single allowed SQL mirror.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Arithmetic that recomputes line value (quantity * price * (1 - discount)).
FORMULA_PATTERNS = [
    re.compile(r"round\s*\(\s*\w+\s*\*\s*\w+\s*\*\s*\(1\s*-"),
    re.compile(r"\*\s*\(1\s*-\s*d(isc)?\b"),
]

DELEGATING_MODULES = (
    "commission.py",
    "datamarts.py",
    "pipeline.py",
    "validation_rules.py",
)


def test_no_recomputation_in_src():
    offenders = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        if path.name == "line_value.py":
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel == "src/questions/seg4_cross_file.py":
            # Single documented exception: q34's median-net-paid probe
            # (paid * (1 - disc)) is not a line value (no quantity term);
            # it is covered by the probe assertion below, not the guard.
            text = path.read_text(encoding="utf-8")
            probe = [line for line in text.splitlines()
                     if "paid * (1 - disc)" in line]
            assert len(probe) == 1, f"probe changed shape: {probe}"
            text = "\n".join(line for line in text.splitlines()
                              if "paid * (1 - disc)" not in line)
        else:
            text = path.read_text(encoding="utf-8")
        for pat in FORMULA_PATTERNS:
            if pat.search(text):
                offenders.append(f"{path.name}: {pat.pattern}")
    assert offenders == [], f"line value recomputed outside src/line_value.py: {offenders}"


def test_no_recomputation_in_sql():
    offenders = []
    for path in sorted((ROOT / "sql").rglob("*.sql")):
        if path.name == "v_line_value.sql":
            continue
        text = path.read_text(encoding="utf-8")
        for pat in FORMULA_PATTERNS:
            if pat.search(text):
                offenders.append(f"{path.relative_to(ROOT).as_posix()}: {pat.pattern}")
    assert offenders == [], f"line value recomputed outside sql/v_line_value.sql: {offenders}"


def test_reference_date_literal_single_home():
    hits = []
    for path in sorted((ROOT / "sql").rglob("*.sql")):
        rel = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "2026-10-11" in line:
                hits.append((rel, number, line))
    assert len(hits) == 1, (
        "TODAY literal not unique: "
        + ", ".join(f"{rel}:{number}" for rel, number, _ in hits))
    rel, _, line = hits[0]
    assert rel == "sql/00_staging.sql" and "AS today" in line, (
        f"TODAY literal outside v_run_params: {rel}: {line.strip()}")


def test_sql_mirror_exists_and_matches():
    view = (ROOT / "sql" / "v_line_value.sql").read_text(encoding="utf-8")
    assert "line_value" in view
    assert "ROUND" in view
    assert "(1 - CAST(discount AS NUMERIC))" in view


def test_call_sites_delegate():
    for name in DELEGATING_MODULES:
        text = (ROOT / "src" / name).read_text(encoding="utf-8")
        assert "line_value import" in text, f"{name} does not import the canonical definition"


def test_canonical_null_semantics():
    from src.line_value import line_value
    assert line_value(None, 100.0, 0.1) is None
    assert line_value(2, None, 0.1) is None
    assert line_value(2, 100.0, None) is None
    assert line_value(2, 100.0, 0.1) == 180.0
    assert line_value(2, 100.0, 0.0) == 200.0
