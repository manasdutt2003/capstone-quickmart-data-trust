"""Session fixture: ensure pipeline artifacts exist before artifact-gated tests.

If generated outputs are missing (fresh clone), run the pipeline once into
the write root so tests fail only on real logic errors, not on absent files.
Pipeline is deterministic and idempotent; no source CSVs are modified.

Also provides :func:`find_extracts_root` so that tests can locate the
raw source extracts (``Resources/Capstone Questions/Capstone 2/data``)
in a repo-root-anchored way, independent of how many ``parents`` levels
the importing file happens to be deep.
"""

from pathlib import Path

import pytest


def find_extracts_root(from_file) -> Path:
    """Walk up from *from_file* until ``Resources/Capstone Questions/Capstone 2/data`` is found.

    Accepts a file path string or a ``pathlib.Path``.  Converts to ``Path``
    internally and resolves before walking up.
    """
    p = Path(from_file).resolve()
    for _ in range(30):  # safety limit – should not need more than ~12 for this repo
        candidate = p / "Resources" / "Capstone Questions" / "Capstone 2" / "data"
        if candidate.exists():
            return candidate
        p = p.parent
    raise RuntimeError(
        f"Could not find 'Resources/Capstone Questions/Capstone 2/data' "
        f"by walking up from {from_file}.  Check repo layout."
    )


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_ARTIFACTS = (
    "data/raw_manifest.json",
    "data/sales_datamart.csv",
    "data/trusted_orders.csv",
    "data/rejected_orders.csv",
    "data/clean_orders.csv",
    "data/customer_value_datamart.csv",
    "data/delivery_datamart.csv",
    "reports/generated_report.md",
    "reports/executive_report.md",
    "charts/monthly_sales.png",
    "outputs/trusted_orders.csv",
    "outputs/rejected_orders.csv",
    "outputs/rule_failure_log.csv",
    "outputs/strict_trusted_orders.csv",
    "outputs/lenient_trusted_orders.csv",
    "outputs/validation_datamart.csv",
)


@pytest.fixture(scope="session", autouse=True)
def _ensure_pipeline_outputs():
    missing = [p for p in REQUIRED_ARTIFACTS if not (ROOT / p).exists()]
    if not missing:
        return
    from src.pipeline import main
    main()
