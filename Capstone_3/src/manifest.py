"""Extract manifest for criterion 2 (read-only source integrity).

Hashes are computed AFTER CRLF -> LF normalisation so the manifest is
stable on Windows checkouts and Linux CI. Paths are repo-relative
(forward slashes); no absolute path ever enters the manifest.

Usage:
    python -m src.manifest verify   # fail on any mismatch
    python -m src.manifest write    # (re)write reference/extract_manifest.json
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

EXTRACTS = (
    ("customers", "customers.csv"),
    ("products", "products.csv"),
    ("orders", "orders.csv"),
)

REL_DIR = "Resources/Capstone Questions/Capstone 2/data"


def repo_root() -> Path:
    """Walk up from the write root to the git repo root (contains .git)."""
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / ".git").exists():
            return parent
    raise RuntimeError("repo root (.git) not found")


def extract_path(table: str) -> Path:
    name = dict(EXTRACTS)[table]
    return repo_root() / REL_DIR / name


def lf_bytes(path: Path) -> bytes:
    """File bytes with CRLF normalised to LF (idempotent)."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def sha256_lf(path: Path) -> str:
    return hashlib.sha256(lf_bytes(path)).hexdigest()


def row_count(path: Path) -> int:
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        next(reader)
        return sum(1 for row in reader
                   if not (len(row) == 1 and row[0].strip() == ""))


def build_manifest() -> dict:
    manifest = {}
    for table, _ in EXTRACTS:
        path = extract_path(table)
        blob = lf_bytes(path)
        manifest[table] = {
            "file": f"{REL_DIR}/{dict(EXTRACTS)[table]}".replace("\\", "/"),
            "sha256_lf": hashlib.sha256(blob).hexdigest(),
            "size_lf": len(blob),
            "rows": row_count(path),
        }
    return manifest


def reference_path() -> Path:
    from .path_guard import assert_inside_write_root
    root = Path(__file__).resolve().parents[1]
    return assert_inside_write_root(root / "reference" / "extract_manifest.json")


def write_reference_manifest() -> Path:
    target = reference_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_manifest(), indent=2) + "\n",
                      encoding="utf-8")
    return target


def verify() -> dict:
    """Compare live extracts against reference/extract_manifest.json."""
    ref_file = reference_path()
    if not ref_file.exists():
        raise SystemExit(f"reference manifest missing: {ref_file.name} "
                         f"(run: python -m src.manifest write)")
    expected = json.loads(ref_file.read_text(encoding="utf-8"))
    actual = build_manifest()
    lines = []
    failed = False
    for table, _ in EXTRACTS:
        exp, got = expected[table], actual[table]
        ok = (exp["sha256_lf"] == got["sha256_lf"]
              and exp["size_lf"] == got["size_lf"]
              and exp["rows"] == got["rows"])
        failed = failed or not ok
        lines.append(f"{table}: expected={exp['sha256_lf'][:16]}… "
                     f"actual={got['sha256_lf'][:16]}… "
                     f"rows={got['rows']} {'OK' if ok else 'MISMATCH'}")
    print("\n".join(lines))
    if failed:
        raise SystemExit("extract manifest MISMATCH (source CSVs changed?)")
    print("extract manifest verify: OK")
    return actual


def main(argv=None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["verify"]:
        verify()
    elif args == ["write"]:
        print(f"wrote {write_reference_manifest()}")
    else:
        raise SystemExit("usage: python -m src.manifest [verify|write]")


if __name__ == "__main__":
    main()
