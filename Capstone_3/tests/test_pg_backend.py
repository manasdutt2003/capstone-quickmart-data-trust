"""Tests for the pg.py backend order: DATABASE_URL > local > skip.

No live database is needed: connection attempts are monkeypatched.
"""

import pytest

from src import pg


def test_database_url_first(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://db:5432/qm")
    monkeypatch.delenv("CI", raising=False)
    assert pg.resolve_backend()[0] == "database_url"


def test_database_url_wins_over_local(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://db:5432/qm")
    monkeypatch.setattr(pg, "_local_present", lambda: True)
    assert pg.resolve_backend()[0] == "database_url"


def test_local_second(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(pg, "_local_present", lambda: True)
    backend, detail = pg.resolve_backend()
    assert backend == "local"
    assert detail


def test_skip_last_with_reason(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(pg, "_local_present", lambda: False)
    backend, reason = pg.resolve_backend()
    assert backend == "none"
    assert reason


def test_ci_unreachable_database_url_fails(monkeypatch):
    """CI=true + DATABASE_URL set: no skip; the error propagates (FAIL)."""
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://bad:5432/nope")

    def _boom(*args, **kwargs):
        raise OSError("unreachable")

    monkeypatch.setattr(pg.psycopg, "connect", _boom)
    assert pg.should_fail_fast()
    with pytest.raises(OSError):
        pg.connect()


def test_no_backend_skips_outside_ci(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(pg, "_local_present", lambda: False)
    assert not pg.should_fail_fast()
    assert pg.resolve_backend()[0] == "none"
