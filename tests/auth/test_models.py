"""Tests for ``service_crm.auth.models``.

Covers relationships, unique constraints, cascade behaviour, and the
end-to-end audit listener path now that real models exist.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from service_crm.auth.models import Role
from service_crm.shared.audit import AuditEvent
from tests.factories import RoleFactory, UserFactory


@pytest.mark.integration
def test_role_seed_is_present(db_session: Session) -> None:
    names = {r.name for r in db_session.query(Role).all()}
    assert names == {"admin", "manager", "technician"}


@pytest.mark.integration
def test_user_factory_creates_user_with_seeded_technician_role(
    db_session: Session,
) -> None:
    user = UserFactory()
    db_session.flush()
    assert isinstance(user.id, bytes)
    assert len(user.id) == 16
    assert user.role.name == "technician"
    assert user.is_active is True


@pytest.mark.integration
def test_user_relationships_load_both_sides(db_session: Session) -> None:
    role = db_session.query(Role).filter_by(name="admin").one()
    user = UserFactory(email="boss@example.com", role=role)
    db_session.flush()

    assert user.role is role
    assert user in role.users


@pytest.mark.integration
def test_email_is_unique_case_insensitively(db_session: Session) -> None:
    UserFactory(email="duplicate@example.com")
    db_session.flush()
    # factory-boy's ``sqlalchemy_session_persistence = "flush"`` makes
    # the IntegrityError fire on construction, not on the explicit flush.
    with pytest.raises(IntegrityError):
        UserFactory(email="DUPLICATE@example.com")


@pytest.mark.integration
def test_role_name_is_unique(db_session: Session) -> None:
    RoleFactory(name="custom")
    db_session.flush()
    with pytest.raises(IntegrityError):
        RoleFactory(name="custom")


@pytest.mark.integration
def test_deleting_a_role_with_users_is_restricted(db_session: Session) -> None:
    """``ON DELETE RESTRICT`` should block deleting a role still in use."""
    role = RoleFactory(name="custom-with-users")
    UserFactory(email="bound@example.com", role=role)
    db_session.flush()

    db_session.delete(role)
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_creating_a_user_writes_an_audit_event(db_session: Session) -> None:
    """The listener should pick up Auditable creates end-to-end."""
    UserFactory(email="audited@example.com")
    db_session.flush()

    events = db_session.query(AuditEvent).filter_by(entity_type="User", action="create").all()
    assert len(events) == 1
    event = events[0]
    assert event.entity_id is not None
    assert event.after is not None
    assert event.after["email"] == "audited@example.com"
    # password_hash is recorded (it's a column); we just confirm it's present.
    assert "password_hash" in event.after
    # before is empty for creates.
    assert event.before is None


@pytest.mark.integration
def test_updating_a_user_writes_an_update_audit_event(db_session: Session) -> None:
    user = UserFactory(email="before@example.com")
    db_session.flush()
    db_session.query(AuditEvent).delete()  # clear the create event
    db_session.flush()

    user.is_active = False
    db_session.flush()

    events = db_session.query(AuditEvent).filter_by(entity_type="User", action="update").all()
    assert len(events) == 1
    event = events[0]
    assert event.before is not None
    assert event.after is not None
    assert event.before["is_active"] is True
    assert event.after["is_active"] is False


@pytest.mark.integration
def test_deleting_a_user_writes_a_delete_audit_event(db_session: Session) -> None:
    user = UserFactory(email="goner@example.com")
    db_session.flush()
    db_session.query(AuditEvent).delete()
    db_session.flush()

    db_session.delete(user)
    db_session.flush()

    events = db_session.query(AuditEvent).filter_by(entity_type="User", action="delete").all()
    assert len(events) == 1
    event = events[0]
    assert event.before is not None
    assert event.before["email"] == "goner@example.com"
    assert event.after is None


@pytest.mark.integration
def test_user_and_role_repr(db_session: Session) -> None:
    """``__repr__`` is a developer-facing convenience; pin its shape."""
    role = db_session.query(Role).filter_by(name="admin").one()
    user = UserFactory(email="reprable@example.com", role=role)
    db_session.flush()
    assert repr(role) == "<Role 'admin'>"
    assert repr(user) == "<User 'reprable@example.com'>"


@pytest.mark.integration
def test_audit_actor_is_recorded_when_context_var_is_set(
    db_session: Session,
) -> None:
    from service_crm.shared.audit import ACTOR_CTX, REQUEST_ID_CTX

    actor_bytes = b"\x42" * 16
    ACTOR_CTX.set(actor_bytes)
    REQUEST_ID_CTX.set("req-1234")

    UserFactory(email="acted-on@example.com")
    db_session.flush()

    event = db_session.query(AuditEvent).filter_by(entity_type="User", action="create").one()
    assert event.actor_user_id == actor_bytes
    assert event.request_id == "req-1234"
