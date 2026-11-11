"""Row lineage contract (Sprint 3, deliverable 3).

Every order row carries these columns from cleaning onward; no stage may
drop them. Content beyond presence is populated as rule bodies land:
`dedup_rule_applied` names the dedup rule that removed a row ("" = kept),
`rules_passed`/`rules_failed` list rule ids per row (populated with the
rule-body prompt; until then they travel as "" so the contract holds).
Aggregated marts change grain, so per-row lineage stops at trusted orders.
"""

REQUIRED_LINEAGE_COLUMNS = (
    "source_file",
    "source_row_number",
    "dedup_rule_applied",
    "rules_passed",
    "rules_failed",
)

LINEAGE_DEFAULTS = {
    "source_file": "UNKNOWN",
    "source_row_number": -1,
    "dedup_rule_applied": "",
    "rules_passed": "",
    "rules_failed": "",
}


def ensure_lineage(df, source_file=None):
    """Add missing lineage columns with defaults; never drop or overwrite.

    Existing values are preserved. Missing columns are appended in
    contract order (deterministic). Pass `source_file` at cleaning time;
    later stages call with no argument and keep what is there.
    """
    out = df.copy()
    for col in REQUIRED_LINEAGE_COLUMNS:
        if col not in out.columns:
            if col == "source_file" and source_file is not None:
                out[col] = source_file
            else:
                out[col] = LINEAGE_DEFAULTS[col]
    return out
