"""E2E tests for the maintenance blueprint routes."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from service_crm.maintenance.models import (
    MaintenanceTask,
    MaintenanceTemplate,
    TaskStatus,
)
from tests.factories import (
    EquipmentFactory,
    MaintenancePlanFactory,
    MaintenanceTaskFactory,
    MaintenanceTemplateFactory,
    ServiceInterventionFactory,
    ServiceTicketFactory,
    TechnicianFactory,
)


def _tok() -> str:
    return uuid.uuid4().hex


# ── Auth ────────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_index_redirects_unauthenticated(client: FlaskClient) -> None:
    resp = client.get("/maintenance/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


@pytest.mark.e2e
def test_index_redirects_to_plans(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/maintenance/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/maintenance/plans" in resp.headers["Location"]


# ── Templates ───────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_templates_list_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    MaintenanceTemplateFactory(name="Visible-template-XYZ")
    db_session.flush()
    resp = client_logged_in.get("/maintenance/templates")
    assert resp.status_code == 200
    assert b"Visible-template-XYZ" in resp.data


@pytest.mark.e2e
def test_templates_list_show_all(client_logged_in: FlaskClient, db_session: Session) -> None:
    MaintenanceTemplateFactory(name="A-active", is_active=True)
    MaintenanceTemplateFactory(name="B-inactive", is_active=False)
    db_session.flush()
    resp = client_logged_in.get("/maintenance/templates?show=all")
    assert resp.status_code == 200
    assert b"A-active" in resp.data
    assert b"B-inactive" in resp.data


@pytest.mark.e2e
def test_template_new_creates(client_logged_in: FlaskClient, db_session: Session) -> None:
    resp = client_logged_in.post(
        "/maintenance/templates/new",
        data={
            "name": "From route",
            "description": "blah",
            "cadence_days": "30",
            "estimated_minutes": "60",
            "checklist_template_id": "",
            "idempotency_token": _tok(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire_all()
    created = db_session.query(MaintenanceTemplate).filter_by(name="From route").one_or_none()
    assert created is not None
    assert created.cadence_days == 30


@pytest.mark.e2e
def test_template_new_rejects_blank(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        "/maintenance/templates/new",
        data={"name": "", "cadence_days": "30", "idempotency_token": _tok()},
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_template_new_duplicate_name_flashes(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    """Service-level ``ValueError`` (duplicate name) is caught and flashed."""
    MaintenanceTemplateFactory(name="Dup-name-Q42")
    db_session.flush()
    resp = client_logged_in.post(
        "/maintenance/templates/new",
        data={
            "name": "Dup-name-Q42",
            "cadence_days": "30",
            "idempotency_token": _tok(),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_template_new_idempotent_retry(client_logged_in: FlaskClient, db_session: Session) -> None:
    token = _tok()
    payload = {
        "name": "Once",
        "cadence_days": "30",
        "idempotency_token": token,
    }
    resp1 = client_logged_in.post(
        "/maintenance/templates/new", data=payload, follow_redirects=False
    )
    assert resp1.status_code == 302
    # Same token, same name → second submit is rejected as a duplicate
    # (no second row, redirect to list).
    resp2 = client_logged_in.post(
        "/maintenance/templates/new", data=payload, follow_redirects=False
    )
    assert resp2.status_code == 302
    db_session.expire_all()
    assert db_session.query(MaintenanceTemplate).filter_by(name="Once").count() == 1


@pytest.mark.e2e
def test_template_edit(client_logged_in: FlaskClient, db_session: Session) -> None:
    template = MaintenanceTemplateFactory(name="Editable")
    db_session.flush()
    resp = client_logged_in.get(f"/maintenance/templates/{template.id.hex()}/edit")
    assert resp.status_code == 200
    resp = client_logged_in.post(
        f"/maintenance/templates/{template.id.hex()}/edit",
        data={
            "name": "Edited",
            "description": "",
            "cadence_days": "45",
            "estimated_minutes": "",
            "checklist_template_id": "",
            "is_active": "y",
            "idempotency_token": _tok(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire_all()
    fresh = db_session.get(MaintenanceTemplate, template.id)
    assert fresh.name == "Edited"
    assert fresh.cadence_days == 45


@pytest.mark.e2e
def test_template_edit_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get(f"/maintenance/templates/{'00' * 16}/edit", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_template_edit_rename_clash_flashes(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    a = MaintenanceTemplateFactory(name="A-clash-test")
    MaintenanceTemplateFactory(name="B-clash-test")
    db_session.flush()
    resp = client_logged_in.post(
        f"/maintenance/templates/{a.id.hex()}/edit",
        data={
            "name": "B-clash-test",
            "description": "",
            "cadence_days": "30",
            "estimated_minutes": "",
            "checklist_template_id": "",
            "is_active": "y",
            "idempotency_token": _tok(),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_template_new_idempotency_short_circuit(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    """Second submit with the same token redirects without re-running create.

    The handler's idempotency-token branch (``flash + redirect``) is
    exercised here so it doesn't show up as missing coverage.
    """
    token = _tok()
    payload = {"name": "Once-X-77", "cadence_days": "30", "idempotency_token": token}
    client_logged_in.post("/maintenance/templates/new", data=payload, follow_redirects=False)
    resp = client_logged_in.post("/maintenance/templates/new", data=payload, follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_template_edit_idempotency_short_circuit(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    tpl = MaintenanceTemplateFactory(name="Edit-idem")
    db_session.flush()
    token = _tok()
    payload = {
        "name": "Edit-idem-new",
        "description": "",
        "cadence_days": "30",
        "estimated_minutes": "",
        "checklist_template_id": "",
        "is_active": "y",
        "idempotency_token": token,
    }
    client_logged_in.post(
        f"/maintenance/templates/{tpl.id.hex()}/edit", data=payload, follow_redirects=False
    )
    resp = client_logged_in.post(
        f"/maintenance/templates/{tpl.id.hex()}/edit", data=payload, follow_redirects=False
    )
    assert resp.status_code == 302


# ── Plans ───────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_plans_list_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    tpl = MaintenanceTemplateFactory(name="Visible-plan-template-Q9")
    MaintenancePlanFactory(template=tpl)
    db_session.flush()
    resp = client_logged_in.get("/maintenance/plans")
    assert resp.status_code == 200
    assert b"Visible-plan-template-Q9" in resp.data


@pytest.mark.e2e
def test_plans_list_filters_by_equipment(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    eq = EquipmentFactory()
    MaintenancePlanFactory(equipment=eq)
    db_session.flush()
    resp = client_logged_in.get(f"/maintenance/plans?equipment={eq.id.hex()}")
    assert resp.status_code == 200


@pytest.mark.e2e
def test_plan_new_prefills_equipment(client_logged_in: FlaskClient, db_session: Session) -> None:
    eq = EquipmentFactory()
    db_session.flush()
    resp = client_logged_in.get(f"/maintenance/plans/new?equipment={eq.id.hex()}")
    assert resp.status_code == 200


@pytest.mark.e2e
def test_plans_list_overdue_filter(
    client_logged_in: FlaskClient, db_session: Session, frozen_clock
) -> None:
    today = frozen_clock.date()
    tpl = MaintenanceTemplateFactory(name="A1")
    MaintenancePlanFactory(template=tpl, next_due_on=today - timedelta(days=1))
    db_session.flush()
    resp = client_logged_in.get("/maintenance/plans?overdue=1")
    assert resp.status_code == 200
    assert b"A1" in resp.data


@pytest.mark.e2e
def test_plan_new_creates(client_logged_in: FlaskClient, db_session: Session) -> None:
    eq = EquipmentFactory()
    tpl = MaintenanceTemplateFactory(cadence_days=30)
    db_session.flush()
    resp = client_logged_in.post(
        "/maintenance/plans/new",
        data={
            "equipment_id": eq.id.hex(),
            "template_id": tpl.id.hex(),
            "cadence_days": "",
            "last_done_on": "",
            "notes": "weekly",
            "idempotency_token": _tok(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_plan_new_validation_flashes(client_logged_in: FlaskClient, db_session: Session) -> None:
    tpl = MaintenanceTemplateFactory(cadence_days=30)
    db_session.flush()
    # Equipment is required; submitting blank should re-render the form.
    resp = client_logged_in.post(
        "/maintenance/plans/new",
        data={
            "equipment_id": "",
            "template_id": tpl.id.hex(),
            "cadence_days": "",
            "last_done_on": "",
            "notes": "",
            "idempotency_token": _tok(),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_plan_detail_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    plan = MaintenancePlanFactory()
    MaintenanceTaskFactory(plan=plan, due_on=date(2026, 6, 1))
    db_session.flush()
    resp = client_logged_in.get(f"/maintenance/plans/{plan.id.hex()}")
    assert resp.status_code == 200
    assert b"2026-06-01" in resp.data


@pytest.mark.e2e
def test_plan_detail_unknown_id(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get(f"/maintenance/plans/{'00' * 16}", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_plan_edit(client_logged_in: FlaskClient, db_session: Session) -> None:
    plan = MaintenancePlanFactory()
    db_session.flush()
    resp = client_logged_in.get(f"/maintenance/plans/{plan.id.hex()}/edit")
    assert resp.status_code == 200
    resp = client_logged_in.post(
        f"/maintenance/plans/{plan.id.hex()}/edit",
        data={
            "cadence_days": "45",
            "last_done_on": "2026-01-01",
            "notes": "edited",
            "is_active": "y",
            "idempotency_token": _tok(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_plan_edit_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get(f"/maintenance/plans/{'00' * 16}/edit", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_plan_generate_tasks(
    client_logged_in: FlaskClient, db_session: Session, frozen_clock
) -> None:
    today = frozen_clock.date()
    plan = MaintenancePlanFactory(cadence_days=30, last_done_on=today - timedelta(days=30))
    db_session.flush()
    resp = client_logged_in.post(
        f"/maintenance/plans/{plan.id.hex()}/generate-tasks",
        data={"idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire_all()
    tasks = db_session.query(MaintenanceTask).filter_by(plan_id=plan.id).all()
    assert len(tasks) == 1


@pytest.mark.e2e
def test_plan_generate_tasks_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        f"/maintenance/plans/{'00' * 16}/generate-tasks",
        data={"idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302


# ── Tasks ───────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_tasks_list_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    plan = MaintenancePlanFactory(template=MaintenanceTemplateFactory(name="Tpl-list"))
    MaintenanceTaskFactory(plan=plan, due_on=date(2026, 7, 1))
    db_session.flush()
    resp = client_logged_in.get("/maintenance/tasks")
    assert resp.status_code == 200
    assert b"Tpl-list" in resp.data


@pytest.mark.e2e
def test_tasks_list_status_filter(client_logged_in: FlaskClient, db_session: Session) -> None:
    MaintenanceTaskFactory(status=TaskStatus.DONE)
    db_session.flush()
    resp = client_logged_in.get("/maintenance/tasks?status=done")
    assert resp.status_code == 200
    # Bogus status falls through to "all".
    resp = client_logged_in.get("/maintenance/tasks?status=bogus")
    assert resp.status_code == 200


@pytest.mark.e2e
def test_task_detail_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    task = MaintenanceTaskFactory()
    db_session.flush()
    resp = client_logged_in.get(f"/maintenance/tasks/{task.id.hex()}")
    assert resp.status_code == 200


@pytest.mark.e2e
def test_task_detail_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get(f"/maintenance/tasks/{'00' * 16}", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_task_assign(client_logged_in: FlaskClient, db_session: Session) -> None:
    task = MaintenanceTaskFactory()
    tech = TechnicianFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/maintenance/tasks/{task.id.hex()}/assign",
        data={"technician_id": tech.id.hex(), "idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire_all()
    fresh = db_session.get(MaintenanceTask, task.id)
    assert fresh.assigned_technician_id == tech.id


@pytest.mark.e2e
def test_task_assign_unknown_task(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        f"/maintenance/tasks/{'00' * 16}/assign",
        data={"idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_task_complete(client_logged_in: FlaskClient, db_session: Session) -> None:
    task = MaintenanceTaskFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/maintenance/tasks/{task.id.hex()}/complete",
        data={
            "intervention_id": "",
            "notes": "done",
            "idempotency_token": _tok(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire_all()
    fresh = db_session.get(MaintenanceTask, task.id)
    assert fresh.status == TaskStatus.DONE


@pytest.mark.e2e
def test_task_complete_with_intervention(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    task = MaintenanceTaskFactory()
    # Use a deliberately high ticket number to avoid colliding with
    # explicit-number tickets created by other test modules — the conftest
    # SAVEPOINT pattern doesn't roll back route-committed data.
    ticket = ServiceTicketFactory(number=950_010)
    intervention = ServiceInterventionFactory(ticket=ticket)
    db_session.flush()
    resp = client_logged_in.post(
        f"/maintenance/tasks/{task.id.hex()}/complete",
        data={
            "intervention_id": intervention.id.hex(),
            "notes": "linked",
            "idempotency_token": _tok(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_task_complete_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        f"/maintenance/tasks/{'00' * 16}/complete",
        data={"idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_task_escalate(client_logged_in: FlaskClient, db_session: Session) -> None:
    task = MaintenanceTaskFactory()
    # Seed a high-numbered ticket so the escalation route's MAX+1 lands
    # well above the number range used by other test modules (e.g.
    # tests/tickets/test_models.py pins ticket numbers like 42).
    ServiceTicketFactory(number=950_500)
    db_session.flush()
    resp = client_logged_in.post(
        f"/maintenance/tasks/{task.id.hex()}/escalate",
        data={
            "title": "Custom-escalation",
            "description": "needs help",
            "idempotency_token": _tok(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert b"/tickets/" in resp.data
    db_session.expire_all()
    fresh = db_session.get(MaintenanceTask, task.id)
    assert fresh.status == TaskStatus.ESCALATED
    assert fresh.ticket_id is not None


@pytest.mark.e2e
def test_task_escalate_already_done(client_logged_in: FlaskClient, db_session: Session) -> None:
    task = MaintenanceTaskFactory(status=TaskStatus.DONE)
    db_session.flush()
    resp = client_logged_in.post(
        f"/maintenance/tasks/{task.id.hex()}/escalate",
        data={"idempotency_token": _tok()},
        follow_redirects=False,
    )
    # Service raises; route flashes and stays on the task page.
    assert resp.status_code == 302


@pytest.mark.e2e
def test_task_escalate_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        f"/maintenance/tasks/{'00' * 16}/escalate",
        data={"idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302
