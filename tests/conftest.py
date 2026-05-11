"""Shared pytest fixtures.

Per ``python.tests.md`` §3, this file owns the public fixtures:

- ``app``: the Flask app under :class:`TestConfig`, with the schema
  built via ``alembic upgrade head`` so we test the migrations we ship,
  not a ``db.create_all`` shortcut.
- ``client``: the Flask test client.
- ``frozen_clock``: patches :func:`service_crm.shared.clock._now`.
- ``db_engine``: session-scoped SQLAlchemy engine bound to the test DB.
- ``db_session``: per-test transactional session, rolled back on exit
  via a SAVEPOINT — roughly two orders of magnitude faster than
  recreating the schema per test, and surfaces ordering bugs.
- ``client_logged_in``: ``client`` + a default admin session cookie
  (lights up once the auth slice ships the ``/auth/login`` route; for
  now it just seeds an admin user against ``db_session``).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import event as sa_event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from service_crm import create_app
from service_crm.config import TestConfig
from service_crm.extensions import db as _db


@sa_event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
    """SQLite ships with foreign-key enforcement disabled. Turn it on for
    every connection so ``ON DELETE RESTRICT``/``CASCADE`` actually fire
    in tests. The check is dialect-name agnostic — non-SQLite drivers
    don't expose ``isolation_level`` the same way, so we sniff first."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()


@pytest.fixture(scope="session")
def app() -> Iterator[Flask]:
    flask_app = create_app(TestConfig)
    with flask_app.app_context():
        # Run Alembic upgrade head against TestConfig.SQLALCHEMY_DATABASE_URI
        # so the suite exercises the migrations we ship.
        from pathlib import Path

        from alembic import command
        from alembic.config import Config as AlembicConfig

        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
        cfg = AlembicConfig(str(migrations_dir / "alembic.ini"))
        cfg.set_main_option("script_location", str(migrations_dir))
        cfg.set_main_option("sqlalchemy.url", flask_app.config["SQLALCHEMY_DATABASE_URI"])
        command.upgrade(cfg, "head")
        yield flask_app


@pytest.fixture(scope="session")
def db_engine(app: Flask) -> Engine:
    return _db.engine


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Transactional session, rolled back at teardown.

    Standard "join an external transaction" recipe adapted for
    Flask-SQLAlchemy 3.x. Hijacks the global ``db.session`` for the
    duration of the test so the factories and any service code under
    test write into our nested transaction. The outer rollback discards
    everything regardless of whether test code called ``commit``.
    """
    connection = db_engine.connect()
    transaction = connection.begin()

    # Reconfigure the scoped-session proxy to bind every fresh session
    # to this connection. ``_db.session`` is a ``scoped_session``; the
    # ``session_factory`` attribute is the underlying ``sessionmaker``.
    _db.session.remove()
    original_bind = _db.session.session_factory.kw.get("bind")
    _db.session.session_factory.configure(bind=connection)

    session = _db.session()
    nested = connection.begin_nested()

    @sa_event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, trans: object) -> None:
        nonlocal nested
        if not nested.is_active and connection.in_transaction():
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        _db.session.remove()
        _db.session.session_factory.configure(bind=original_bind)
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def client_logged_in(client: FlaskClient, db_session: Session) -> FlaskClient:
    """``client`` with a default admin user persisted in the test DB.

    The auth slice (next PR) wires the ``/auth/login`` route; until
    then this fixture only guarantees the user row exists. Once login
    lands, this fixture will POST to ``/auth/login`` so the returned
    client carries the session cookie.
    """
    from tests.factories import RoleFactory, UserFactory

    admin_role = db_session.query(_admin_role_model()).filter_by(name="admin").one_or_none()
    if admin_role is None:
        admin_role = RoleFactory(name="admin")
    UserFactory(email="admin@example.com", role=admin_role)
    db_session.flush()
    return client


def _admin_role_model() -> type:
    from service_crm.auth.models import Role

    return Role


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """Patch :func:`service_crm.shared.clock._now` to return a fixed timestamp."""
    fixed = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr("service_crm.shared.clock._now", lambda: fixed)
    return fixed


@pytest.fixture(autouse=True)
def _reset_audit_context() -> Iterator[None]:
    """Make sure the audit context vars don't leak between tests."""
    from service_crm.shared.audit import ACTOR_CTX, REQUEST_ID_CTX

    actor_token = ACTOR_CTX.set(None)
    request_token = REQUEST_ID_CTX.set(None)
    try:
        yield
    finally:
        ACTOR_CTX.reset(actor_token)
        REQUEST_ID_CTX.reset(request_token)
