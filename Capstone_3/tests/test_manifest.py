"""Extract-manifest gate (criterion 2): LF-normalised source integrity."""

import json
from pathlib import Path

from src.manifest import verify

ROOT = Path(__file__).resolve().parents[1]

EXPECTED = {
    "customers": "7664b59dd98d11f903cb8203eca1e87a4c2554ca4550c54eefdc36e4a6aca548",
    "orders": "2f142cedfd7811ed7c295ccd9ef6e43f26f4e70d9ce10ffc86c621c540cbeb88",
    "products": "4c8ec5eea500bce61e7554453d765fddd78d56ab2327f5c1cf2253f74c97138a",
}


def test_reference_manifest_matches_expected():
    ref = ROOT / "reference" / "extract_manifest.json"
    assert ref.exists(), "reference/extract_manifest.json missing"
    manifest = json.loads(ref.read_text(encoding="utf-8"))
    for table, sha in EXPECTED.items():
        assert manifest[table]["sha256_lf"] == sha
        assert "\\" not in manifest[table]["file"]
        assert not manifest[table]["file"].startswith("C:")
        assert not manifest[table]["file"].startswith("/")


def test_verify_passes():
    verify()


def test_raw_manifest_has_no_absolute_paths():
    manifest = json.loads((ROOT / "data" / "raw_manifest.json").read_text(encoding="utf-8"))
    for key, entry in manifest.items():
        if isinstance(entry, dict) and "file" in entry:
            assert not Path(entry["file"]).is_absolute(), key
