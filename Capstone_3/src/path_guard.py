"""Path guard: confine every write to the QuickMart write root.

All writers must resolve target paths through `assert_inside_write_root`,
which resolves symlinks and `..` and raises `PermissionError` when the
target falls outside the write root (including sibling-prefix tricks
such as ".../QuickMart_other").
"""

import argparse
import sys
import time
from pathlib import Path

WRITE_ROOT = Path(__file__).resolve().parents[1]

WRITE_LOG = WRITE_ROOT / ".write_log"


def assert_inside_write_root(path: str | Path) -> Path:
    """Resolve `path` and ensure it stays inside the write root.

    Accepts paths relative to the write root or absolute paths.
    Returns the resolved absolute `Path`. Raises `PermissionError`
    otherwise.
    """
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = WRITE_ROOT / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(WRITE_ROOT.resolve())
    except ValueError:
        raise PermissionError(
            f"Refused write outside write root: {path!s} "
            f"(resolves to {resolved}, root is {WRITE_ROOT})"
        )
    return resolved


def scan_recent(limit_hours: float = 24.0) -> tuple[list[Path], list[str]]:
    """List files modified in the last `limit_hours` under the write root.

    Returns (recent_files, violations). Also inspects `.write_log` when
    present: any logged path resolving outside the root is a violation.
    """
    cutoff = time.time() - limit_hours * 3600
    root = WRITE_ROOT.resolve()
    recent: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file() or p.is_symlink() and not p.exists():
            continue
        try:
            if p.stat().st_mtime >= cutoff:
                recent.append(p)
        except OSError:
            continue
    violations: list[str] = []
    if WRITE_LOG.exists():
        for line in WRITE_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                assert_inside_write_root(line)
            except PermissionError as exc:
                violations.append(str(exc))
    return sorted(recent), violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan write-root writes.")
    parser.add_argument("--scan", action="store_true",
                        help="List files modified in the last 24h.")
    parser.add_argument("--hours", type=float, default=24.0)
    args = parser.parse_args(argv)
    if not args.scan:
        parser.print_help()
        return 2
    recent, violations = scan_recent(args.hours)
    for p in recent:
        print(str(p))
    if violations:
        for v in violations:
            print(f"VIOLATION: {v}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
