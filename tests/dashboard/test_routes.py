"""E2E tests for the dashboard blueprint routes."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from service_crm.tickets.state import TicketStatus
from tests.factories import (
    ClientFactory,
    MaintenancePlanFactory,
    ServiceTicketFactory,
    TechnicianFactory,
)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def today(now: datetime) -> date:
    return now.date()


def _patch_clock(monkeypatch: pytest.MonkeyPatch, now: datetime) -> None:
    from service_crm.shared import clock

    monkeypatch.setattr(clock, "_now", lambda: now)


# ── Auth ────────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_admin_redirects_unauthenticated(client: FlaskClient) -> None:
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


@pytest.mark.e2e
def test_me_redirects_unauthenticated(client: FlaskClient) -> None:
    resp = client.get("/dashboard/me", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


# ── Manager view ────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_admin_renders_for_logged_in_user(
    client_logged_in: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    resp = client_logged_in.get("/?lang=en")
    assert resp.status_code == 200
    assert b"Operational dashboard" in resp.data


@pytest.mark.e2e
def test_admin_shows_kpi_values(
    client_logged_in: FlaskClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    client = ClientFactory(name="Visible-on-dashboard")
    ServiceTicketFactory(client=client, status=TicketStatus.IN_PROGRESS.value)
    ServiceTicketFactory(client=client, status=TicketStatus.WAITING_PARTS.value)
    db_session.flush()
    db_session.commit()
    resp = client_logged_in.get("/?lang=en")
    assert resp.status_code == 200
    # Drillable: the open-tickets tile points at the tickets list.
    assert b"/tickets/" in resp.data
    # "Waiting parts" KPI is rendered.
    assert b"Waiting parts" in resp.data


@pytest.mark.e2e
def test_admin_renders_upcoming_maintenance(
    client_logged_in: FlaskClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
    today: date,
) -> None:
    _patch_clock(monkeypatch, now)
    plan = MaintenancePlanFactory(is_active=True)
    plan.next_due_on = today + timedelta(days=2)
    db_session.flush()
    db_session.commit()
    resp = client_logged_in.get("/")
    assert resp.status_code == 200
    assert plan.equipment.label.encode("utf-8") in resp.data


@pytest.mark.e2e
def test_admin_renders_high_risk_machines(
    client_logged_in: FlaskClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    from tests.factories import EquipmentFactory

    client = ClientFactory()
    equipment = EquipmentFactory(client=client)
    db_session.flush()
    for _ in range(3):
        ServiceTicketFactory(client=client, equipment=equipment)
    db_session.flush()
    db_session.commit()
    resp = client_logged_in.get("/")
    assert resp.status_code == 200
    assert equipment.label.encode("utf-8") in resp.data


# ── Technician view ────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_me_renders_with_no_assignments(
    client_logged_in: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    resp = client_logged_in.get("/dashboard/me?lang=en")
    assert resp.status_code == 200
    assert b"My queue" in resp.data


@pytest.mark.e2e
def test_me_renders_open_tickets_for_user(
    client_logged_in: FlaskClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    # The client_logged_in fixture builds an admin user. We can pull it
    # back via the session cookie and attach a ticket as assignee.
    from service_crm.auth.models import User

    user = db_session.query(User).order_by(User.created_at.desc()).first()
    assert user is not None
    ticket = ServiceTicketFactory(
        assignee=user,
        status=TicketStatus.IN_PROGRESS.value,
        title="My ticket on the dashboard",
    )
    db_session.flush()
    db_session.commit()
    resp = client_logged_in.get("/dashboard/me")
    assert resp.status_code == 200
    assert ticket.title.encode("utf-8") in resp.data


@pytest.mark.e2e
def test_me_hints_when_user_has_no_technician_row(
    client_logged_in: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    resp = client_logged_in.get("/dashboard/me?lang=en")
    assert resp.status_code == 200
    # User has no technician row → the technician toolbar hint copy renders.
    assert b"technician roster" in resp.data


@pytest.mark.e2e
def test_me_surfaces_maintenance_tasks_when_user_has_technician(
    client_logged_in: FlaskClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
    today: date,
) -> None:
    _patch_clock(monkeypatch, now)
    from service_crm.auth.models import User
    from tests.factories import MaintenanceTaskFactory

    user = db_session.query(User).order_by(User.created_at.desc()).first()
    assert user is not None
    tech = TechnicianFactory(user=user, display_name="Test tech")
    task = MaintenanceTaskFactory(assigned_technician=tech)
    task.due_on = today + timedelta(days=3)
    db_session.flush()
    db_session.commit()
    resp = client_logged_in.get("/dashboard/me")
    assert resp.status_code == 200
    assert task.plan.equipment.label.encode("utf-8") in resp.data


# ── Sidebar links ──────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_admin_link_to_my_queue_is_present(
    client_logged_in: FlaskClient,
) -> None:
    resp = client_logged_in.get("/")
    assert resp.status_code == 200
    assert b'href="/dashboard/me"' in resp.data


@pytest.mark.e2e
def test_me_link_to_admin_is_present(
    client_logged_in: FlaskClient,
) -> None:
    resp = client_logged_in.get("/dashboard/me")
    assert resp.status_code == 200
    # The "Manager overview" link points back to /
    assert b'href="/"' in resp.data
