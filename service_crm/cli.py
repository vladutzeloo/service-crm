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
