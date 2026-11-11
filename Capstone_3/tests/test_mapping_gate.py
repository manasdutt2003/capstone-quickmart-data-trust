"""Tests for the mapping gate (used by R08/R09)."""

import pandas as pd
import pytest

from src.mapping_gate import (
    MappingGateError,
    apply_mapping,
    apply_mapping_with,
    load_mapping,
)


def _frame(rows):
    return pd.DataFrame(rows)


def test_complete_mapping_passes():
    mapping = load_mapping("payment")
    assert mapping["upi"] == "UPI"
    assert mapping[""] == "MISSING"


def test_unknown_mapping_name_fails():
    with pytest.raises(MappingGateError):
        load_mapping("nope")


def test_duplicate_raw_value_fails():
    frame = _frame([{"raw_value": "a", "standard_value": "A", "approved_by": "N"},
                    {"raw_value": "a", "standard_value": "A", "approved_by": "N"}])
    from src.mapping_gate import _validate_frame
    with pytest.raises(MappingGateError):
        _validate_frame(frame, "test.csv")


def test_missing_approved_by_fails():
    frame = _frame([{"raw_value": "a", "standard_value": "A", "approved_by": ""}])
    from src.mapping_gate import _validate_frame
    with pytest.raises(MappingGateError):
        _validate_frame(frame, "test.csv")


def test_empty_standard_value_fails():
    frame = _frame([{"raw_value": "a", "standard_value": "", "approved_by": "N"}])
    from src.mapping_gate import _validate_frame
    with pytest.raises(MappingGateError):
        _validate_frame(frame, "test.csv")


def test_unseen_value_fails():
    mapping = load_mapping("status")
    with pytest.raises(MappingGateError):
        apply_mapping_with(pd.Series(["Shipped"]), mapping, "status")


def test_apply_is_idempotent():
    assert load_mapping("payment")["upi"] == "UPI"
    once = apply_mapping(pd.Series(["upi", "UPI", ""]), "payment")
    twice = apply_mapping(once, "payment")
    pd.testing.assert_series_equal(once, twice)


def test_already_standard_passthrough():
    mapping = load_mapping("status")
    out = apply_mapping_with(pd.Series(["Delivered", "Cancelled"]), mapping, "status")
    assert out.tolist() == ["Delivered", "Cancelled"]
