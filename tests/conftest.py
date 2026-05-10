"""Shared pytest fixtures.

Per ``python.tests.md`` §3, this file owns the public fixtures. The
foundation PR ships only what the foundation tests need:

- ``app``: the Flask app under :class:`TestConfig`.
- ``client``: the Flask test client.
- ``frozen_clock``: patches :func:`service_crm.shared.clock._now`.

The DB-aware fixtures (``db_engine``, ``db_session``, ``client_logged_in``)
land alongside the first migration in the auth data-model PR.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from flask import Flask
from flask.testing import FlaskClient

from service_crm import create_app
from service_crm.config import TestConfig


@pytest.fixture(scope="session")
def app() -> Iterator[Flask]:
    flask_app = create_app(TestConfig)
    with flask_app.app_context():
        yield flask_app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


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
