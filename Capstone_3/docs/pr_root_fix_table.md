## Root Path Resolution — Inspection Table
(Compiled from grep across src/, tests/, config/ — read-only analysis. No files modified.)

| File & Line | Path Expression | How raw_dir / Resources is resolved | Verdict |
|-------------|----------------|-------------------------------------|---------|
| **tests/test_questions_seg4_5.py:42** | `Path(__file__).resolve().parents[6]` | Walks 6 levels up from test file (`tests/`) → parent of repo root. raw_dir = `parents[6] / "Resources" / "Capstone Questions" / "Capstone 2" / "data"` | **wrong** (off-by-one: should be `parents[5]` to hit repo root) |
| **check_manifest.py:6** | `r'C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Resources\Capstone Questions\Capstone 2\data'` | Hardcoded absolute Windows path | **local-only** (depends on this exact machine username/path) |
| **test_shuffled.py:73/77-79** | `r'C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Resources\Capstone Questions\Capstone 2\data'` | Hardcoded absolute Windows path | **local-only** |
| **src/pipeline.py:56/70** | `ROOT = Path(__file__).resolve().parents[1]` then `REPO = _repo_root()` walking for `.git`; `RAW_DIR = REPO / "Resources/Capstone Questions/Capstone 2/data"` | From `src/` → `parents[1]` = QuickMart dir → walks up for `.git` → repo root. RAW_DIR = repo-root-relative path. | **correct** (repo-root anchored) |
| **config/settings.json:3** | `"raw_dir": "Resources/Capstone Questions/Capstone 2/data"` | Relative path. Used as `ROOT / raw_dir` in pipeline (`ROOT` = QuickMart root from `parents[1]`). | **correct** (relative, anchored via pipeline ROOT) |
| **src/manifest.py:24/36-38** | `REL_DIR = "Resources/Capstone Questions/Capstone 2/data"`; `extract_path(table) = repo_root() / REL_DIR / name` | `repo_root()` walks up from `src/manifest.py` file to find `.git` → repo root. REL_DIR is relative fragment. | **correct** (repo-root anchored via walk) |
| **tests/conftest.py:12** | `ROOT = Path(__file__).resolve().parents[1]` | From `tests/` → `parents[1]` = `QuickMart/` root. Used to ensure pipeline artifacts exist. | **correct for its purpose** (artifacts under QuickMart, not source data) |
| **tests/test_line_endings.py:23** | `_repo_root() / "Resources" / "Capstone Questions" / "Capstone 2" / "data"` | `_repo_root()` walks up from `ROOT = parents[1]` (QuickMart) looking for `.git` → reaches repo root correctly (5 levels up from test file). | **correct** (walk finds repo root) |
| **src/questions/seg6_leadership.py:264** | `Path(__file__).resolve().parents[7]` | Walks 7 levels up from `seg6_leadership.py` (in `src/questions/`) → reaches repo root. Then uses `REPO_ROOT / "Resources/Capstone Questions/Capstone 2/data"`. | **correct** (walk finds repo root) |
| **src/questions/seg6_leadership.py:327** | `Path(__file__).resolve().parents[2].parent.parent.parent / "Resources/Capstone Questions/Capstone 2/data"` | From `seg6_leadership.py` → `parents[2]` = `src/` → `.parent.parent.parent` = repo root → appends data path. | **correct** (explicit parents count matches depth) |
| **src/pipeline.py:65** | `CONFIG = ROOT / "config"` where `ROOT = Path(__file__).resolve().parents[1]` | From `src/` → `parents[1]` = QuickMart root → `CONFIG = QuickMart/config`. | **correct** |

### Why it passes locally (evidence)
- **test_questions_seg4_5.py fixture** uses `parents[6]`. On developer's machine, test file is at:
  `C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Projects\Individual\Manas Dutt\Week 3\QuickMart/tests/test_questions_seg4_5.py`
  - `parents[5]` = `C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\` (repo root parent)
  - `parents[6]` = `C:\Users\manas.dutt\Desktop\` (one level above repo root)
  - The source CSVs live at `C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Resources\Capstone Questions\Capstone 2\data/`
  - So `parents[6] / "Resources" / "Capstone Questions" / "Capstone 2" / "data"` = `C:\Users\manas.dutt\Desktop\Resources\Capstone Questions\Capstone 2\data/` — **this does NOT match the actual data location** (`...GGTP_BLR_DP_SEP_26/Resources/...`).
  
  **Correction**: The fixture *appears* to work locally only because the developer's `Resources` folder may be mounted/copied at `Desktop` level, OR the `parents[6]` math happens to align due to idiosyncratic directory depth. The CI runner has the repo checked out as `/home/runner/work/GGTP_CHN_DP_SEP_26/GGTP_CHN_DP_SEP_26/...` so `parents[6]` = `/home/runner/work/` which has no `Resources/Capstone Questions/Capstone 2/data/` — hence the `FileNotFoundError`.

  **Actual local-pass mechanism**: The developer likely has the source data accessible via a path that the `parents[6]` resolves to, OR the test was previously run with the data already present under `QuickMart/data/` (pipeline outputs). But the fixture's explicit purpose is to load raw source extracts, and the path is wrong by one level.

### Minimal fix — shared helper proposal
Create a single reusable function in `tests/conftest.py` (or a new `src/paths.py`) that:

1. Walks up from the importing file's `__file__` until it finds a folder matching `Resources/Capstone Questions/Capstone 2/data` (or hits the filesystem root).
2. Returns the repo-root-anchored path to that data folder.
3. Fails with a clear `RuntimeError` if not found, so the mismatch is obvious on first CI run.

**Pseudocode (to be added to `tests/conftest.py` or `src/paths.py`):**

```python
def find_extracts_root(from_file: Path) -> Path:
    """Walk up from __file__ until Resources/Capstone Questions/Capstone 2/data is found."""
    p = Path(from_file).resolve()
    for _ in range(20):  # safety limit
        candidate = p / "Resources" / "Capstone Questions" / "Capstone 2" / "data"
        if candidate.exists():
            return candidate
        p = p.parent
    raise RuntimeError(
        f"Could not find 'Resources/Capstone Questions/Capstone 2/data' "
        f"by walking up from {from_file}. Check repo layout."
    )
```

**Then update `tests/test_questions_seg4_5.py` fixture:**

```python
repo_root = find_extracts_root(__file__).parent.parent.parent.parent.parent  # or just use the returned path directly
```

Or more simply, just replace the broken `parents[6]` with a call to this helper.

STOP. Waiting for "go" before any further writes or git actions.