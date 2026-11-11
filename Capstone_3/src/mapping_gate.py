"""Mapping gate: standardise values only through approved mappings.

`load_mapping(name)` reads config/{name}_mapping.csv (approved_by=Neha on
every row) and rejects: (a) unseen values at apply time, (b) rows with an
empty approved_by (approved_on is required only when the column exists),
(c) duplicate raw_value rows, (d) empty standard_value rows.
`apply_mapping(series, name)` standardises like cleaning does (strip,
pass-through of already-standard values, "" via its mapping row) and is
idempotent; anything else raises MappingGateError instead of being
silently forced into a group.
"""

import pandas as pd

from .path_guard import assert_inside_write_root

MAPPINGS_DIR_NAME = "config"

MAPPING_FILES = {
    "payment": "payment_mapping.csv",
    "status": "status_mapping.csv",
    "city": "city_mapping.csv",
    "category": "category_mapping.csv",
}


class MappingGateError(Exception):
    """Raised when a value cannot pass the mapping gate."""


def _mappings_dir():
    from pathlib import Path
    return Path(__file__).resolve().parents[1] / MAPPINGS_DIR_NAME


def load_mapping(name, mappings_dir=None):
    """Load and validate one mapping; return {raw_value: standard_value}."""
    if name not in MAPPING_FILES:
        raise MappingGateError(f"unknown mapping: {name}")
    base = mappings_dir
    if base is None:
        base = _mappings_dir()
    path = assert_inside_write_root(base) / MAPPING_FILES[name]
    frame = pd.read_csv(path, dtype=str, keep_default_na=False,
                        encoding="utf-8")
    return _validate_frame(frame, path.name)


def _validate_frame(frame, source_name):
    """Check gate invariants on a mapping frame; return the mapping dict."""
    for col in ("raw_value", "standard_value", "approved_by"):
        if col not in frame.columns:
            raise MappingGateError(f"{source_name} lacks column {col}")
    seen = set()
    mapping = {}
    for _, row in frame.iterrows():
        raw, std, approver = row["raw_value"], row["standard_value"], \
            row["approved_by"]
        if raw in seen:
            raise MappingGateError(
                f"duplicate raw_value {raw!r} in {source_name}")
        seen.add(raw)
        if std.strip() == "":
            raise MappingGateError(f"empty standard_value for {raw!r}")
        if approver.strip() == "":
            raise MappingGateError(f"empty approved_by for {raw!r}")
        if "approved_on" in frame.columns and \
                str(row["approved_on"]).strip() == "":
            raise MappingGateError(f"empty approved_on for {raw!r}")
        mapping[raw] = std
    return mapping


def apply_mapping_with(series, mapping, name):
    """Standardise a series against a mapping dict (idempotent).

    Already-standard values pass through; anything else not present as a
    raw_value raises MappingGateError instead of being silently forced
    into a group.
    """
    standards = set(mapping.values())
    out = []
    for value in series.astype(str):
        v = value.strip()
        if v in standards:
            out.append(v)
        elif v in mapping:
            out.append(mapping[v])
        else:
            raise MappingGateError(
                f"value {value!r} not in {name} mapping")
    return pd.Series(out, index=series.index)


def apply_mapping(series, name, mappings_dir=None):
    """Standardise a series through the gate (idempotent)."""
    return apply_mapping_with(series, load_mapping(name, mappings_dir), name)
