"""Flask CLI commands.

Registered against the app by ``service_crm/__init__.py``. Run via:

    flask --app service_crm reset-db --yes
    flask --app service_crm seed
"""

from __future__ import annotations

import sys

import click
from flask import Flask
from flask.cli import with_appcontext

from .extensions import db


def register(app: Flask) -> None:
    app.cli.add_command(reset_db)
    app.cli.add_command(seed)
    app.cli.add_command(babel_extract)
    app.cli.add_command(babel_update)
    app.cli.add_command(babel_compile)
    app.cli.add_command(sweep_idempotency)


@click.command("reset-db")
@click.option(
    "--yes",
    is_flag=True,
    help="Skip the interactive confirmation. Required in non-TTY environments.",
)
@with_appcontext
def reset_db(yes: bool) -> None:
    """Drop and recreate every table. Destructive; never run in production."""
    if not yes:
        click.echo(
            "Refusing to drop tables without --yes. "
            "Use `flask --app service_crm reset-db --yes` to confirm.",
            err=True,
        )
        sys.exit(1)
    # Drop everything and run migrations from scratch, so ``alembic_version``
    # is rebuilt alongside the schema. ``db.create_all()`` would skip it and
    # leave the next ``flask db upgrade`` thinking nothing has been applied.
    from flask_migrate import upgrade as flask_migrate_upgrade

    db.drop_all()
    flask_migrate_upgrade()
    click.echo("Database reset.")


@click.command("seed")
@with_appcontext
def seed() -> None:
    """Seed demo data. Empty until the auth slice lands."""
    click.echo("Nothing to seed yet — auth slice not implemented.")


def main() -> None:
    """Console-script entry point declared in ``pyproject.toml``."""
    from flask.cli import FlaskGroup

    from . import create_app
    from .config import DevConfig

    cli = FlaskGroup(create_app=lambda: create_app(DevConfig))
    cli()


# ---------------------------------------------------------------------------
# i18n / Flask-Babel commands. Thin wrappers around pybabel so contributors
# don't have to remember the long invocations. Catalogs live inside the
# package at ``service_crm/locale/`` so they ship in the wheel.
# ``babel.cfg`` is at the repo root.
# ---------------------------------------------------------------------------


def _repo_root() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parent.parent)


def _run_pybabel(args: list[str]) -> int:
    import subprocess

    return subprocess.check_call(["pybabel", *args], cwd=_repo_root())


@click.command("babel-extract")
def babel_extract() -> None:
    """Scan templates / Python sources and refresh ``messages.pot``."""
    _run_pybabel(
        [
            "extract",
            "-F",
            "babel.cfg",
            "-k",
            "_l",
            "-o",
            "service_crm/locale/messages.pot",
            ".",
        ]
    )
    click.echo("Extracted to service_crm/locale/messages.pot")


@click.command("babel-update")
def babel_update() -> None:
    """Merge new strings into the ``ro`` and ``en`` catalogs."""
    _run_pybabel(["update", "-i", "service_crm/locale/messages.pot", "-d", "service_crm/locale"])
    click.echo("Updated catalogs in service_crm/locale/")


@click.command("babel-compile")
def babel_compile() -> None:
    """Compile ``.po`` → ``.mo`` so Babel can serve translations."""
    _run_pybabel(["compile", "-d", "service_crm/locale"])
    click.echo("Compiled catalogs.")


@click.command("sweep-idempotency")
@with_appcontext
def sweep_idempotency() -> None:
    """Delete expired ``idempotency_key`` rows.

    The window is 24 h; this command is meant to run from cron or
    APScheduler (the latter lands in v0.7). Idempotent — running it more
    than once a day is fine.
    """
    from .shared.idempotency import sweep

    removed = sweep(db.session)
    db.session.commit()
    click.echo(f"Removed {removed} expired idempotency keys.")
