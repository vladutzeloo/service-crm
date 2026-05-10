"""Tests for ``flask reset-db`` and ``flask seed``."""

from __future__ import annotations

import pytest
from click.testing import CliRunner
from flask import Flask

from service_crm.cli import reset_db, seed


@pytest.mark.integration
def test_reset_db_requires_yes_flag(app: Flask) -> None:
    runner = CliRunner()
    with app.app_context():
        result = runner.invoke(reset_db, [])
    assert result.exit_code == 1
    assert "Refusing to drop tables" in result.output


@pytest.mark.integration
def test_reset_db_with_yes_runs_migrations(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    """``reset_db`` should ``db.drop_all`` and then ``flask_migrate.upgrade``.

    Asserting on the upgrade *call* rather than the schema state because
    the foundation PR ships zero Alembic revisions; the real upgrade
    round-trip is exercised once /data-model lands the first revision.
    """
    calls: list[str] = []

    def _fake_upgrade(*_args: object, **_kwargs: object) -> None:
        calls.append("upgrade")

    monkeypatch.setattr("flask_migrate.upgrade", _fake_upgrade)

    runner = CliRunner()
    with app.app_context():
        result = runner.invoke(reset_db, ["--yes"])

    assert result.exit_code == 0, result.output
    assert "Database reset." in result.output
    assert calls == ["upgrade"]


@pytest.mark.unit
def test_seed_is_a_no_op(app: Flask) -> None:
    runner = CliRunner()
    with app.app_context():
        result = runner.invoke(seed, [])
    assert result.exit_code == 0
    assert "Nothing to seed yet" in result.output
