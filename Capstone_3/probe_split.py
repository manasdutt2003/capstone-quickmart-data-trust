"""One-off probe: statement splitter output (read-only)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _statements(text):
    return [s for s in (part.strip() for part in text.split(";")) if s]


for name in ("sql/03_dedup.sql", "sql/questions/seg4_q30.sql"):
    parts = _statements((ROOT / name).read_text(encoding="utf-8"))
    print("=" * 40, name, len(parts))
    for i, part in enumerate(parts):
        print(f"--- part {i} ({len(part)} chars) first 120:")
        print(part[:120].replace("\n", "\\n"))
