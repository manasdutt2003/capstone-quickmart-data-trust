"""Static test: Q4 queries use only trusted columns, no line value redefinition."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Patterns that indicate line value recomputation
LINE_VALUE_RE = re.compile(
    r"(?:quantity|qty)\s*\*\s*(?:unit_price_paid|price)\s*\*\s*\(1\s*-\s*(?:discount|disc)",
    re.IGNORECASE
)

# Raw columns that should NOT appear in Q4 queries
RAW_COLUMNS = {
    "raw_order_id", "raw_customer_id", "raw_product_id", "raw_order_date",
    "raw_quantity", "raw_unit_price_paid", "raw_discount", "raw_payment_mode",
    "raw_order_status", "raw_delivery_days", "dedup_rule_applied",
    "rules_passed", "rules_failed", "commission"
}

# Trusted columns that ARE allowed
TRUSTED_COLUMNS = {
    "source_file", "source_row_number", "order_id", "customer_id", "product_id",
    "order_date", "quantity", "unit_price_paid", "discount", "payment_mode",
    "order_status", "delivery_days", "notes", "notes_sha256",
    "line_value", "city_std", "category_std", "status_std", "payment_std",
    "order_month", "signup_date"
}

# SQL files to check
SQL_FILES = [
    "sql/06_segment6_9_answers.sql",
]

# Python files to check
PY_FILES = [
    "src/questions/seg4_cross_file.py",
    "src/questions/seg5_values.py",
    "src/datamarts.py",
    "src/pipeline.py",
]


def test_no_raw_columns_in_q4_sql():
    """Q4 SQL must not reference raw_* or dedup columns."""
    for sql_file in SQL_FILES:
        path = ROOT / sql_file
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for raw_col in RAW_COLUMNS:
            # Skip comments
            for line_num, line in enumerate(text.splitlines(), 1):
                if line.strip().startswith("--"):
                    continue
                if re.search(rf"\b{re.escape(raw_col)}\b", line):
                    raise AssertionError(
                        f"{sql_file}:{line_num} references forbidden raw column '{raw_col}': {line.strip()}"
                    )


def test_no_line_value_redefinition_in_q4_sql():
    """Q4 SQL must not redefine line value formula."""
    for sql_file in SQL_FILES:
        path = ROOT / sql_file
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for line_num, line in enumerate(text.splitlines(), 1):
            if line.strip().startswith("--"):
                continue
            if LINE_VALUE_RE.search(line):
                raise AssertionError(
                    f"{sql_file}:{line_num} redefines line value formula: {line.strip()}"
                )


def test_no_line_value_redefinition_in_q4_python():
    """Q4 Python must not redefine line value formula (must delegate to line_value.py)."""
    for py_file in PY_FILES:
        path = ROOT / py_file
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        # Allow the single definition in line_value.py
        if "line_value.py" in str(py_file):
            continue
        # Allow _line_value helper in datamarts.py that delegates to line_value.line_value
        if "datamarts.py" in str(py_file):
            # Check it delegates properly
            if "_line_value" in text and "from .line_value import line_value" not in text:
                raise AssertionError(f"{py_file}: _line_value doesn't import from line_value.py")
            continue
        for line_num, line in enumerate(text.splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            if LINE_VALUE_RE.search(line):
                raise AssertionError(
                    f"{py_file}:{line_num} redefines line value formula: {line.strip()}"
                )


def test_q4_queries_use_trusted_enriched():
    """Q4 SQL should read from trusted_enriched or v_trusted_lenient, not raw tables."""
    path = ROOT / "sql/06_segment6_9_answers.sql"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        # Should reference trusted_enriched or v_trusted_lenient
        has_trusted = "trusted_enriched" in text or "v_trusted_lenient" in text
        assert has_trusted, "Q4 SQL must read from trusted_enriched or v_trusted_lenient"


if __name__ == "__main__":
    test_no_raw_columns_in_q4_sql()
    test_no_line_value_redefinition_in_q4_sql()
    test_no_line_value_redefinition_in_q4_python()
    test_q4_queries_use_trusted_enriched()
    print("All Q4 static tests passed!")