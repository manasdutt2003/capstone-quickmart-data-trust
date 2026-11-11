"""CSV hygiene: every src writer uses utf-8 + LF; no CRLF in outputs/."""

import ast
import json
from pathlib import Path

from src.pipeline import verify_output_hashes

ROOT = Path(__file__).resolve().parents[1]


def test_no_crlf_in_outputs():
    out = ROOT / "outputs"
    bad = []
    for path in sorted(out.glob("*.csv")):
        if b"\r\n" in path.read_bytes():
            bad.append(path.name)
    assert bad == [], f"CRLF found in outputs: {bad}"


def test_src_writers_use_utf8_lf():
    """Every to_csv call site in src/ passes encoding + lineterminator."""
    offenders = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "to_csv":
                keywords = {kw.arg for kw in node.keywords}
                if not {"encoding", "lineterminator"} <= keywords:
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert offenders == [], f"writers missing utf-8/LF: {offenders}"


def test_output_hashes_verify():
    ref = ROOT / "reference" / "output_hashes.json"
    assert ref.exists(), "reference/output_hashes.json missing"
    expected = json.loads(ref.read_text(encoding="utf-8"))
    assert set(expected) == {p.name for p in (ROOT / "outputs").glob("*.csv")}
    verify_output_hashes()
