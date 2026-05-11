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


@pytest.mark.unit
@pytest.mark.parametrize(
    "command, expected_args_head",
    [
        ("babel_extract", ["extract", "-F", "babel.cfg"]),
        ("babel_update", ["update"]),
        ("babel_compile", ["compile"]),
    ],
)
def test_babel_commands_shell_out_to_pybabel(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    expected_args_head: list[str],
) -> None:
    """The Babel CLI commands wrap ``pybabel``. Patch ``subprocess`` so the
    test doesn't shell out, then assert on the call shape."""
    from click.testing import CliRunner

    from service_crm import cli as cli_mod

    captured: dict[str, object] = {}

    def _fake_check_call(args: list[str], cwd: str | None = None) -> int:
        captured["args"] = args
        captured["cwd"] = cwd
        return 0

    monkeypatch.setattr("subprocess.check_call", _fake_check_call)
    runner = CliRunner()
    with app.app_context():
        result = runner.invoke(getattr(cli_mod, command), [])

    assert result.exit_code == 0, result.output
    assert isinstance(captured["args"], list)
    args_list: list[str] = captured["args"]  # type: ignore[assignment]
    assert args_list[0] == "pybabel"
    assert args_list[1 : 1 + len(expected_args_head)] == expected_args_head


@pytest.mark.unit
def test_main_entrypoint_invokes_flask_group(monkeypatch: pytest.MonkeyPatch) -> None:
    """``service_crm.cli:main`` is the ``service-crm-cli`` console-script
    entry. We don't want to invoke the real Flask CLI from the suite, so
    we patch ``FlaskGroup`` and assert it's constructed with our factory
    and then called."""
    from service_crm import cli as cli_mod

    constructed: dict[str, object] = {}
    called = []

    class _FakeFlaskGroup:
        def __init__(self, *, create_app: object) -> None:
            constructed["create_app"] = create_app

        def __call__(self) -> None:
            called.append(True)

    monkeypatch.setattr("flask.cli.FlaskGroup", _FakeFlaskGroup)
    cli_mod.main()

    assert called == [True]
    assert callable(constructed["create_app"])
