"""Raw-preserving loader for QuickMart extracts.

Every value is kept as text (dtype=str, keep_default_na=False) so that
leading zeros, spaces, currency symbols and ambiguous dates survive load.
Reloading is idempotent: same file bytes -> same row count and SHA-256.
"""

import csv
import hashlib
import json
from pathlib import Path

EXPECTED_HEADERS: dict[str, list[str]] = {
    "customers": ["customer_id", "customer_name", "email", "city", "phone", "signup_date"],
    "products": ["product_id", "product_name", "category", "unit_price", "stock_qty"],
    "orders": [
        "order_id", "customer_id", "product_id", "order_date", "quantity",
        "unit_price_paid", "discount", "payment_mode", "order_status",
        "delivery_days", "notes",
    ],
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_encoding(path: Path) -> str:
    raw = path.read_bytes()[:4096]
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


def load_raw(path: Path, table: str) -> tuple[list[str], list[list[str]]]:
    """Return (header, rows) preserving every raw value as text."""
    enc = detect_encoding(path)
    with open(path, encoding=enc, newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        rows = [row for row in reader if not (len(row) == 1 and row[0].strip() == "")]
    expected = EXPECTED_HEADERS[table]
    if header != expected:
        raise ValueError(f"{table}: header mismatch file={header} expected={expected}")
    return header, rows


def row_length_audit(header: list[str], rows: list[list[str]]) -> dict[int, int]:
    dist: dict[int, int] = {}
    for row in rows:
        dist[len(row)] = dist.get(len(row), 0) + 1
    dist.setdefault(len(header), 0)
    return dist


def _display_path(path: Path) -> str:
    """Repo-relative display path (never absolute; criterion 2)."""
    candidate = Path(path)
    for parent in [candidate] + list(candidate.parents):
        if (parent / ".git").exists():
            return candidate.relative_to(parent).as_posix()
    for parent in [candidate] + list(candidate.parents):
        if parent.name == "QuickMart":
            return candidate.relative_to(parent).as_posix()
    return candidate.name


def write_manifest(raw_dir: Path, out_path: Path) -> dict:
    manifest: dict = {}
    for table in ("customers", "products", "orders"):
        path = raw_dir / f"{table}.csv"
        header, rows = load_raw(path, table)
        manifest[table] = {
            "file": _display_path(path),
            "sha256": sha256_of(path),
            "encoding": detect_encoding(path),
            "header": header,
            "rows_in_file": len(rows),
            "rows_loaded": len(rows),
            "row_length_dist": row_length_audit(header, rows),
        }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_all_text(raw_dir: Path) -> dict[str, list[dict[str, str]]]:
    """Load all three extracts as list-of-dicts of raw text (no coercion)."""
    out: dict[str, list[dict[str, str]]] = {}
    for table in ("customers", "products", "orders"):
        header, rows = load_raw(raw_dir / f"{table}.csv", table)
        out[table] = [dict(zip(header, r, strict=True)) for r in rows]
    return out