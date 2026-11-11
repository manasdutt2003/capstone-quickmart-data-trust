"""Line-ending independence: CRLF vs LF extracts give identical results."""

import shutil
from pathlib import Path

from src.cleaning import clean_all
from src.data_loader import load_all_text
from src.manifest import sha256_lf
from src.normalise import load_mapping

ROOT = Path(__file__).resolve().parents[1]


def _repo_root() -> Path:
    p = ROOT
    for _ in range(8):
        if (p / ".git").exists():
            return p
        p = p.parent
    raise RuntimeError("repo root not found")


RAW = _repo_root() / "Resources" / "Capstone Questions" / "Capstone 2" / "data"


def _copies(tmp: Path, ending: bytes) -> Path:
    """Copy the three extracts into tmp with the given line ending."""
    tmp.mkdir(parents=True, exist_ok=True)
    for table in ("customers", "products", "orders"):
        raw = (RAW / f"{table}.csv").read_bytes().replace(b"\r\n", b"\n")
        if ending == b"\r\n":
            raw = raw.replace(b"\n", b"\r\n")
        (tmp / f"{table}.csv").write_bytes(raw)
    return tmp


def test_crlf_and_lf_load_identically():
    work = ROOT / "test_tmp_line_endings"
    crlf_dir, lf_dir = work / "crlf", work / "lf"
    try:
        _copies(crlf_dir, b"\r\n")
        _copies(lf_dir, b"\n")
        crlf = {t: load_all_text(crlf_dir)[t] for t in ("customers", "products", "orders")}
        lf = {t: load_all_text(lf_dir)[t] for t in ("customers", "products", "orders")}
        assert crlf == lf
        for table in ("customers", "products", "orders"):
            assert sha256_lf(crlf_dir / f"{table}.csv") == sha256_lf(lf_dir / f"{table}.csv")

        import pandas as pd

        city_map = load_mapping(ROOT / "config" / "city_mapping.csv")
        cat_map = load_mapping(ROOT / "config" / "category_mapping.csv")
        status_map = load_mapping(ROOT / "config" / "status_mapping.csv")
        pay_map = load_mapping(ROOT / "config" / "payment_mapping.csv")
        clean_crlf = clean_all(
            pd.DataFrame(crlf["customers"]), pd.DataFrame(crlf["products"]),
            pd.DataFrame(crlf["orders"]),
            city_map, cat_map, status_map, pay_map)
        clean_lf = clean_all(
            pd.DataFrame(lf["customers"]), pd.DataFrame(lf["products"]),
            pd.DataFrame(lf["orders"]),
            city_map, cat_map, status_map, pay_map)
        for left, right in zip(clean_crlf, clean_lf):
            assert (left.to_csv(index=False, encoding="utf-8", lineterminator="\n")
                    == right.to_csv(index=False, encoding="utf-8", lineterminator="\n"))
    finally:
        shutil.rmtree(work, ignore_errors=True)
