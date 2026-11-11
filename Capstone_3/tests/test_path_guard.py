"""Tests for the write-root path guard (Prompt 0)."""

from pathlib import Path

import pytest

from src.path_guard import WRITE_ROOT, assert_inside_write_root


def test_inside_relative_path_passes():
    p = assert_inside_write_root("data/clean_orders.csv")
    assert p == (WRITE_ROOT / "data/clean_orders.csv").resolve()


def test_inside_absolute_path_passes():
    target = WRITE_ROOT / "reports" / "quality_summary.md"
    assert assert_inside_write_root(target) == target.resolve()


def test_dotdot_escape_fails():
    with pytest.raises(PermissionError):
        assert_inside_write_root("../outside.txt")


def test_nested_dotdot_escape_fails():
    with pytest.raises(PermissionError):
        assert_inside_write_root("data/../../outside.txt")


def test_absolute_outside_path_fails():
    outside = WRITE_ROOT.parents[3] / "other.txt"
    assert WRITE_ROOT not in outside.resolve().parents
    with pytest.raises(PermissionError):
        assert_inside_write_root(outside)


def test_sibling_prefix_path_fails():
    sibling = Path(str(WRITE_ROOT) + "_other") / "x.csv"
    with pytest.raises(PermissionError):
        assert_inside_write_root(sibling)
