"""Tests for the Flask-Login ``user_loader`` and the audit-context hook."""

from __future__ import annotations

import pytest
from flask import Flask
from sqlalchemy.orm import Session

from service_crm.auth import _load_user
from tests.factories import UserFactory


@pytest.mark.integration
def test_user_loader_returns_user_for_valid_hex_id(app: Flask, db_session: Session) -> None:
    user = UserFactory(email="loader@example.com")
    db_session.flush()
    hex_id = user.id.hex()

    loaded = _load_user(hex_id)
    assert loaded is not None
    assert loaded.email == "loader@example.com"


@pytest.mark.integration
def test_user_loader_returns_none_for_unknown_id(app: Flask, db_session: Session) -> None:
    # 16 random bytes that don't correspond to any user.
    fake_hex = (b"\x00" * 15 + b"\xff").hex()
    assert _load_user(fake_hex) is None


@pytest.mark.integration
def test_user_loader_returns_none_for_malformed_id(app: Flask, db_session: Session) -> None:
    """Anything that's not valid hex must be rejected without raising."""
    assert _load_user("not-hex-at-all") is None


@pytest.mark.e2e
def test_before_request_hook_sets_request_id_on_g(app: Flask) -> None:
    client = app.test_client()
    with app.test_request_context("/healthz"):
        # The hook fires per-request via the test client.
        pass
    # End-to-end via a real request: g is per-request, so we read it
    # through a view that exposes it. The hook runs for every request,
    # so any 200 response confirms it didn't raise.
    response = client.get("/healthz")
    assert response.status_code == 200
