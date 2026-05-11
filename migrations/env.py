"""Alembic environment.

This file is invoked by ``alembic`` and by ``flask db ...``. It pulls
the SQLAlchemy URL from the Flask config (so dev, test, and prod all
agree) and turns on ``render_as_batch`` for SQLite so ALTER TABLE
operations work despite SQLite's limitations.
"""

from __future__ import annotations

import logging
from logging.config import fileConfig

from alembic import context
from flask import current_app

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")


def get_engine():  # type: ignore[no-untyped-def]
    # Flask-SQLAlchemy 3.x exposes ``.engine``; the ``.get_engine()``
    # callable is deprecated and slated for removal in 3.2.
    return current_app.extensions["migrate"].db.engine


def get_engine_url() -> str:
    try:
        return get_engine().url.render_as_string(hide_password=False).replace("%", "%%")
    except AttributeError:
        return str(get_engine().url).replace("%", "%%")


config.set_main_option("sqlalchemy.url", get_engine_url())
target_db = current_app.extensions["migrate"].db


def get_metadata():  # type: ignore[no-untyped-def]
    if hasattr(target_db, "metadatas"):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=get_metadata(),
        literal_binds=True,
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    def process_revision_directives(context_, revision, directives):  # type: ignore[no-untyped-def]
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info("No changes detected — skipping empty migration.")

    conf_args = current_app.extensions["migrate"].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    with connectable.connect() as connection:
        # ``render_as_batch`` is configured globally via Flask-Migrate's
        # ``init_app(render_as_batch=True)``, so it's already in
        # ``conf_args``. Don't pass it again.
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
