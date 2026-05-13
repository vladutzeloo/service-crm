"""E2E tests for the reports blueprint routes."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from service_crm.reports._translations import REPORT_CODES
from service_crm.tickets.state import TicketStatus
from tests.factories import (
    ClientFactory,
    EquipmentFactory,
    MaintenanceTaskFactory,
    ServiceInterventionFactory,
    ServicePartUsageFactory,
    ServiceTicketFactory,
    TechnicianFactory,
    UserFactory,
)


def _patch_clock(monkeypatch: pytest.MonkeyPatch, now: datetime) -> None:
    from service_crm.shared import clock

    monkeypatch.setattr(clock, "_now", lambda: now)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)


# ── Auth ────────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_index_redirects_unauthenticated(client: FlaskClient) -> None:
    resp = client.get("/reports/")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


# ── Index ───────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_index_lists_every_report(
    client_logged_in: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    resp = client_logged_in.get("/reports/?lang=en")
    assert resp.status_code == 200
    body = resp.data
    for code in REPORT_CODES:
        # Either as URL or as form-route link, the code shows up.
        assert code.encode("utf-8") in body


@pytest.mark.e2e
def test_index_accepts_date_range(
    client_logged_in: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    resp = client_logged_in.get("/reports/?from=2026-05-01&to=2026-05-13&lang=en")
    assert resp.status_code == 200
    assert b"2026-05-01" in resp.data


# ── tickets_by_status ───────────────────────────────────────────────────────


@pytest.mark.e2e
def test_tickets_by_status_html_renders(
    client_logged_in: FlaskClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    client = ClientFactory()
    db_session.flush()
    t = ServiceTicketFactory(client=client, status=TicketStatus.NEW.value)
    t.created_at = datetime(2026, 5, 5, 10, 0, 0)
    db_session.flush()
    db_session.commit()
    resp = client_logged_in.get("/reports/tickets_by_status?from=2026-05-01&to=2026-05-13&lang=en")
    assert resp.status_code == 200
    assert b"2026-05-05" in resp.data


@pytest.mark.e2e
def test_tickets_by_status_csv_streams_attachment(
    client_logged_in: FlaskClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    client = ClientFactory()
    db_session.flush()
    t = ServiceTicketFactory(client=client, status=TicketStatus.NEW.value)
    t.created_at = datetime(2026, 5, 5, 10, 0, 0)
    db_session.flush()
    db_session.commit()
    resp = client_logged_in.get("/reports/tickets_by_status.csv?from=2026-05-01&to=2026-05-13")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["Content-Type"]
    assert "tickets-by-status-20260501-20260513.csv" in resp.headers["Content-Disposition"]
    body = resp.get_data(as_text=True)
    assert "2026-05-05" in body
    assert "new" in body


# ── interventions_by_machine ────────────────────────────────────────────────


@pytest.mark.e2e
def test_interventions_by_machine_html_and_csv(
    client_logged_in: FlaskClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    client = ClientFactory()
    equipment = EquipmentFactory(client=client)
    db_session.flush()
    ticket = ServiceTicketFactory(client=client, equipment=equipment)
    iv = ServiceInterventionFactory(ticket=ticket)
    iv.started_at = datetime(2026, 5, 5, 9, 0, 0, tzinfo=UTC)
    iv.ended_at = datetime(2026, 5, 5, 10, 0, 0, tzinfo=UTC)
    db_session.flush()
    db_session.commit()
    html = client_logged_in.get("/reports/interventions_by_machine?from=2026-05-01&to=2026-05-13")
    assert html.status_code == 200
    assert equipment.label.encode("utf-8") in html.data
    csv = client_logged_in.get(
        "/reports/interventions_by_machine.csv?from=2026-05-01&to=2026-05-13"
    )
    assert csv.status_code == 200
    assert "text/csv" in csv.headers["Content-Type"]
    assert equipment.label in csv.get_data(as_text=True)


# ── parts_used ──────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_parts_used_html_renders(
    client_logged_in: FlaskClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    ticket = ServiceTicketFactory()
    iv = ServiceInterventionFactory(ticket=ticket)
    iv.started_at = datetime(2026, 5, 5, 9, 0, 0, tzinfo=UTC)
    ServicePartUsageFactory(
        intervention=iv, part_code="PART-9999", description="Spindle", quantity=2
    )
    db_session.flush()
    db_session.commit()
    resp = client_logged_in.get("/reports/parts_used?from=2026-05-01&to=2026-05-13")
    assert resp.status_code == 200
    assert b"PART-9999" in resp.data


@pytest.mark.e2e
def test_parts_used_csv_renders(
    client_logged_in: FlaskClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    ticket = ServiceTicketFactory()
    iv = ServiceInterventionFactory(ticket=ticket)
    iv.started_at = datetime(2026, 5, 5, 9, 0, 0, tzinfo=UTC)
    ServicePartUsageFactory(intervention=iv, part_code="PART-CSV", quantity=4)
    db_session.flush()
    db_session.commit()
    resp = client_logged_in.get("/reports/parts_used.csv?from=2026-05-01&to=2026-05-13")
    assert resp.status_code == 200
    assert "PART-CSV" in resp.get_data(as_text=True)


# ── maintenance_due_vs_completed ────────────────────────────────────────────


@pytest.mark.e2e
def test_maintenance_due_vs_completed_html_renders(
    client_logged_in: FlaskClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    task = MaintenanceTaskFactory()
    task.due_on = date(2026, 5, 5)
    db_session.flush()
    db_session.commit()
    resp = client_logged_in.get(
        "/reports/maintenance_due_vs_completed?from=2026-05-01&to=2026-05-13&lang=en"
    )
    assert resp.status_code == 200
    assert b"2026-05-05" in resp.data


# ── technician_workload ─────────────────────────────────────────────────────


@pytest.mark.e2e
def test_technician_workload_renders(
    client_logged_in: FlaskClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    user = UserFactory()
    TechnicianFactory(user=user, display_name="Workload-Tech")
    db_session.flush()
    ticket = ServiceTicketFactory()
    iv = ServiceInterventionFactory(ticket=ticket, technician=user)
    iv.started_at = datetime(2026, 5, 5, 9, 0, 0, tzinfo=UTC)
    iv.ended_at = datetime(2026, 5, 5, 11, 0, 0, tzinfo=UTC)
    db_session.flush()
    db_session.commit()
    resp = client_logged_in.get("/reports/technician_workload?from=2026-05-01&to=2026-05-13")
    assert resp.status_code == 200
    assert b"Workload-Tech" in resp.data


# ── repeat_issues ───────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_repeat_issues_renders(
    client_logged_in: FlaskClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    client = ClientFactory(name="Repeat-Client")
    equipment = EquipmentFactory(client=client)
    db_session.flush()
    for _ in range(2):
        t = ServiceTicketFactory(client=client, equipment=equipment)
        t.created_at = datetime(2026, 5, 5, 9, 0, 0)
    db_session.flush()
    db_session.commit()
    resp = client_logged_in.get("/reports/repeat_issues?from=2026-05-01&to=2026-05-13")
    assert resp.status_code == 200
    assert b"Repeat-Client" in resp.data


# ── Default window ──────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_routes_accept_missing_dates_and_fall_back(
    client_logged_in: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    for code in REPORT_CODES:
        resp = client_logged_in.get(f"/reports/{code}")
        assert resp.status_code == 200, f"{code} failed"


@pytest.mark.e2e
def test_csv_routes_accept_missing_dates(
    client_logged_in: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    for code in REPORT_CODES:
        resp = client_logged_in.get(f"/reports/{code}.csv")
        assert resp.status_code == 200, f"{code}.csv failed"
        assert "text/csv" in resp.headers["Content-Type"]
