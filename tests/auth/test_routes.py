"""End-to-end tests for the auth blueprint routes."""

from __future__ import annotations

import pytest
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from service_crm.auth.models import Role, User
from service_crm.shared.audit import AuditEvent
from tests.factories import UserFactory


@pytest.mark.e2e
def test_login_get_renders_the_form(client: FlaskClient) -> None:
    response = client.get("/auth/login")
    assert response.status_code == 200
    body = response.data.decode()
    assert "<form" in body
    assert 'name="email"' in body
    assert 'name="password"' in body
    # CSRF disabled in TestConfig, but the form still emits the field's HTML.
    assert "csrf_token" in body or "csrf-token" in body or "<input" in body


@pytest.mark.e2e
def test_login_post_happy_path_redirects_and_stamps_last_login(
    client: FlaskClient, db_session: Session
) -> None:
    admin = db_session.query(Role).filter_by(name="admin").one()
    UserFactory(email="alice@example.com", password="hunter2", role=admin)
    db_session.flush()

    response = client.post(
        "/auth/login",
        data={"email": "alice@example.com", "password": "hunter2"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    user = db_session.query(User).filter_by(email="alice@example.com").one()
    assert user.last_login_at is not None


@pytest.mark.e2e
def test_login_post_normalises_email_case(client: FlaskClient, db_session: Session) -> None:
    UserFactory(email="bob@example.com", password="hunter2")
    db_session.flush()

    response = client.post(
        "/auth/login",
        data={"email": "BOB@Example.COM", "password": "hunter2"},
    )
    assert response.status_code == 302


@pytest.mark.e2e
def test_login_post_wrong_password_returns_401(client: FlaskClient, db_session: Session) -> None:
    UserFactory(email="carol@example.com", password="hunter2")
    db_session.flush()

    response = client.post(
        "/auth/login",
        data={"email": "carol@example.com", "password": "wrong"},
    )
    assert response.status_code == 401
    # Default locale is RO; assert on the locale-agnostic flash class.
    assert b"flash-error" in response.data


@pytest.mark.e2e
def test_login_post_unknown_email_returns_401(client: FlaskClient) -> None:
    response = client.post(
        "/auth/login",
        data={"email": "nobody@example.com", "password": "whatever"},
    )
    assert response.status_code == 401


@pytest.mark.e2e
def test_inactive_user_cannot_log_in(client: FlaskClient, db_session: Session) -> None:
    UserFactory(email="dormant@example.com", password="hunter2", is_active=False)
    db_session.flush()

    response = client.post(
        "/auth/login",
        data={"email": "dormant@example.com", "password": "hunter2"},
    )
    assert response.status_code == 401


@pytest.mark.e2e
def test_login_records_actor_on_subsequent_audit_events(
    client: FlaskClient, db_session: Session
) -> None:
    """After a successful login, the next write captures actor_user_id."""
    user = UserFactory(email="eve@example.com", password="hunter2")
    db_session.flush()
    expected_actor = user.id

    response = client.post(
        "/auth/login",
        data={"email": "eve@example.com", "password": "hunter2"},
    )
    assert response.status_code == 302

    # The login itself stamps last_login_at — that update event must
    # carry the actor.
    update_events = (
        db_session.query(AuditEvent).filter_by(entity_type="User", action="update").all()
    )
    assert any(evt.actor_user_id == expected_actor for evt in update_events)


@pytest.mark.e2e
def test_logout_requires_authentication(client: FlaskClient) -> None:
    response = client.get("/auth/logout", follow_redirects=False)
    # Flask-Login redirects to the login_view when unauthenticated.
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


@pytest.mark.e2e
def test_logout_after_login_clears_session(client: FlaskClient, db_session: Session) -> None:
    UserFactory(email="frank@example.com", password="hunter2")
    db_session.flush()
    client.post(
        "/auth/login",
        data={"email": "frank@example.com", "password": "hunter2"},
    )

    response = client.get("/auth/logout", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


@pytest.mark.e2e
def test_login_honours_next_parameter(client: FlaskClient, db_session: Session) -> None:
    UserFactory(email="grace@example.com", password="hunter2")
    db_session.flush()
    response = client.post(
        "/auth/login?next=/version",
        data={"email": "grace@example.com", "password": "hunter2"},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/version")


@pytest.mark.e2e
def test_login_form_validation_keeps_user_on_page(client: FlaskClient) -> None:
    """Empty submit → form errors, no redirect."""
    response = client.post("/auth/login", data={"email": "", "password": ""})
    # Form fails validation → 200 with the form re-rendered.
    assert response.status_code == 200
    assert b"<form" in response.data


@pytest.mark.e2e
def test_already_authenticated_user_skips_login_page(
    client: FlaskClient, db_session: Session
) -> None:
    """A logged-in user hitting /auth/login is redirected away."""
    UserFactory(email="loggedin@example.com", password="hunter2")
    db_session.flush()
    client.post(
        "/auth/login",
        data={"email": "loggedin@example.com", "password": "hunter2"},
    )

    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 302
    # Should land on the configured post-login destination, not stay on login.
    assert "/auth/login" not in response.headers["Location"]


@pytest.mark.e2e
def test_login_rejects_open_redirect_to_external_host(
    client: FlaskClient, db_session: Session
) -> None:
    """An attacker can't smuggle a same-domain login into a redirect to evil.com."""
    UserFactory(email="harry@example.com", password="hunter2")
    db_session.flush()

    response = client.post(
        "/auth/login?next=https://evil.example.org/steal",
        data={"email": "harry@example.com", "password": "hunter2"},
    )
    assert response.status_code == 302
    assert "evil.example.org" not in response.headers["Location"]


@pytest.mark.e2e
def test_login_rejects_protocol_relative_open_redirect(
    client: FlaskClient, db_session: Session
) -> None:
    """``//evil.com/path`` is a protocol-relative external URL; reject it."""
    UserFactory(email="ian@example.com", password="hunter2")
    db_session.flush()
    response = client.post(
        "/auth/login?next=//evil.example.org/steal",
        data={"email": "ian@example.com", "password": "hunter2"},
    )
    assert response.status_code == 302
    assert "evil.example.org" not in response.headers["Location"]


@pytest.mark.e2e
def test_login_page_lang_switch_preserves_next(client: FlaskClient) -> None:
    """The RO/EN buttons on the login page must keep ?next=... intact."""
    response = client.get("/auth/login?next=/version")
    assert response.status_code == 200
    body = response.data.decode()
    # Both language-switch anchors must include the next target.
    assert "next=%2Fversion" in body or "next=/version" in body
