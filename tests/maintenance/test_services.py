"""Service-layer tests for the maintenance blueprint."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from service_crm.maintenance import services
from service_crm.maintenance.models import (
    MaintenanceExecution,
    MaintenanceTask,
    TaskStatus,
)
from tests.factories import (
    ChecklistTemplateFactory,
    EquipmentFactory,
    MaintenancePlanFactory,
    MaintenanceTaskFactory,
    MaintenanceTemplateFactory,
    ServiceInterventionFactory,
    ServiceTicketFactory,
    TechnicianFactory,
    UserFactory,
)

# ── Templates ───────────────────────────────────────────────────────────────


def test_list_templates_active_only_filter(db_session):
    a = MaintenanceTemplateFactory(name="filter-A-test-list-templates")
    b = MaintenanceTemplateFactory(name="filter-B-test-list-templates", is_active=False)
    db_session.flush()
    active_names = {t.name for t in services.list_templates(db_session)}
    all_names = {t.name for t in services.list_templates(db_session, active_only=False)}
    assert a.name in active_names
    assert b.name not in active_names
    assert {a.name, b.name} <= all_names


def test_require_template_invalid_hex(db_session):
    with pytest.raises(ValueError, match="invalid"):
        services.require_template(db_session, "garbage")


def test_require_template_unknown(db_session):
    with pytest.raises(ValueError, match="not found"):
        services.require_template(db_session, "00" * 16)


def test_create_template_happy(db_session):
    checklist = ChecklistTemplateFactory()
    db_session.flush()
    tpl = services.create_template(
        db_session,
        name="Quarterly",
        description="Quarterly check",
        cadence_days=90,
        estimated_minutes=60,
        checklist_template_id=checklist.id,
    )
    assert tpl.name == "Quarterly"
    assert tpl.cadence_days == 90
    assert tpl.checklist_template_id == checklist.id


def test_create_template_validates(db_session):
    with pytest.raises(ValueError, match="name is required"):
        services.create_template(db_session, name=" ")
    with pytest.raises(ValueError, match="cadence must be"):
        services.create_template(db_session, name="X", cadence_days=0)
    with pytest.raises(ValueError, match="estimated minutes"):
        services.create_template(db_session, name="X", cadence_days=30, estimated_minutes=-1)
    with pytest.raises(ValueError, match="checklist template not found"):
        services.create_template(
            db_session, name="X", cadence_days=30, checklist_template_id=b"\0" * 16
        )


def test_create_template_duplicate_name(db_session):
    MaintenanceTemplateFactory(name="X")
    db_session.flush()
    with pytest.raises(ValueError, match="already exists"):
        services.create_template(db_session, name="x")


def test_update_template(db_session):
    tpl = MaintenanceTemplateFactory(name="A")
    MaintenanceTemplateFactory(name="B")
    db_session.flush()
    services.update_template(
        db_session,
        tpl,
        name="Renamed",
        description="d",
        cadence_days=42,
        estimated_minutes=15,
        checklist_template_id=None,
        is_active=False,
    )
    assert tpl.name == "Renamed"
    assert tpl.cadence_days == 42
    assert tpl.is_active is False
    # Clashing rename rejected.
    with pytest.raises(ValueError, match="already exists"):
        services.update_template(
            db_session,
            tpl,
            name="B",
            description="",
            cadence_days=42,
            estimated_minutes=None,
            checklist_template_id=None,
            is_active=True,
        )


def test_update_template_keeps_name_case(db_session):
    tpl = MaintenanceTemplateFactory(name="A")
    db_session.flush()
    services.update_template(
        db_session,
        tpl,
        name="A",
        description="",
        cadence_days=99,
        estimated_minutes=None,
        checklist_template_id=None,
        is_active=True,
    )
    assert tpl.cadence_days == 99


def test_update_template_validation(db_session):
    tpl = MaintenanceTemplateFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="name is required"):
        services.update_template(
            db_session,
            tpl,
            name="",
            description="",
            cadence_days=30,
            estimated_minutes=None,
            checklist_template_id=None,
            is_active=True,
        )
    with pytest.raises(ValueError, match="cadence must be"):
        services.update_template(
            db_session,
            tpl,
            name="X",
            description="",
            cadence_days=0,
            estimated_minutes=None,
            checklist_template_id=None,
            is_active=True,
        )
    with pytest.raises(ValueError, match="estimated minutes"):
        services.update_template(
            db_session,
            tpl,
            name="X",
            description="",
            cadence_days=30,
            estimated_minutes=-1,
            checklist_template_id=None,
            is_active=True,
        )
    with pytest.raises(ValueError, match="checklist template not found"):
        services.update_template(
            db_session,
            tpl,
            name="X",
            description="",
            cadence_days=30,
            estimated_minutes=None,
            checklist_template_id=b"\0" * 16,
            is_active=True,
        )


# ── Plans ───────────────────────────────────────────────────────────────────


def test_create_plan_validation(db_session):
    eq = EquipmentFactory()
    tpl = MaintenanceTemplateFactory(cadence_days=30)
    db_session.flush()
    with pytest.raises(ValueError, match="equipment not found"):
        services.create_plan(db_session, equipment_id=b"\0" * 16, template_id=tpl.id)
    eq_inactive = EquipmentFactory(is_active=False)
    db_session.flush()
    with pytest.raises(ValueError, match="equipment is inactive"):
        services.create_plan(db_session, equipment_id=eq_inactive.id, template_id=tpl.id)
    with pytest.raises(ValueError, match="template not found"):
        services.create_plan(db_session, equipment_id=eq.id, template_id=b"\0" * 16)
    tpl_inactive = MaintenanceTemplateFactory(is_active=False)
    db_session.flush()
    with pytest.raises(ValueError, match="template is inactive"):
        services.create_plan(db_session, equipment_id=eq.id, template_id=tpl_inactive.id)
    with pytest.raises(ValueError, match="cadence"):
        services.create_plan(db_session, equipment_id=eq.id, template_id=tpl.id, cadence_days=0)


def test_create_plan_recomputes_next_due_on(db_session, frozen_clock):
    eq = EquipmentFactory()
    tpl = MaintenanceTemplateFactory(cadence_days=30)
    db_session.flush()
    plan = services.create_plan(
        db_session,
        equipment_id=eq.id,
        template_id=tpl.id,
        last_done_on=date(2026, 1, 1),
    )
    assert plan.next_due_on == date(2026, 1, 31)


def test_create_plan_seed_from_created_at(db_session, frozen_clock):
    """When no ``last_done_on`` is set, seed from ``created_at``."""
    eq = EquipmentFactory()
    tpl = MaintenanceTemplateFactory(cadence_days=10)
    db_session.flush()
    plan = services.create_plan(db_session, equipment_id=eq.id, template_id=tpl.id)
    expected = plan.created_at.date() + timedelta(days=10)
    assert plan.next_due_on == expected


def test_update_plan_validation(db_session):
    plan = MaintenancePlanFactory(cadence_days=30)
    db_session.flush()
    with pytest.raises(ValueError, match="cadence must be"):
        services.update_plan(
            db_session, plan, cadence_days=0, last_done_on=None, notes="", is_active=True
        )


def test_update_plan_recomputes(db_session, frozen_clock):
    plan = MaintenancePlanFactory()
    db_session.flush()
    services.update_plan(
        db_session,
        plan,
        cadence_days=7,
        last_done_on=date(2026, 1, 1),
        notes="weekly",
        is_active=True,
    )
    assert plan.next_due_on == date(2026, 1, 8)


def test_update_plan_inactive_clears_next_due(db_session):
    plan = MaintenancePlanFactory(next_due_on=date(2026, 1, 1))
    db_session.flush()
    services.update_plan(
        db_session,
        plan,
        cadence_days=plan.cadence_days,
        last_done_on=plan.last_done_on,
        notes="",
        is_active=False,
    )
    assert plan.next_due_on is None


def test_list_plans_overdue_only(db_session, frozen_clock):
    today = frozen_clock.date()
    overdue = MaintenancePlanFactory(next_due_on=today - timedelta(days=1))
    future = MaintenancePlanFactory(next_due_on=today + timedelta(days=5))
    db_session.flush()
    rows = services.list_plans(db_session, overdue_only=True)
    assert overdue in rows
    assert future not in rows


def test_list_plans_filters_equipment(db_session):
    eq_a = EquipmentFactory()
    eq_b = EquipmentFactory()
    plan_a = MaintenancePlanFactory(equipment=eq_a)
    MaintenancePlanFactory(equipment=eq_b)
    db_session.flush()
    rows = services.list_plans(db_session, equipment_id=eq_a.id, active_only=False)
    assert rows == [plan_a]


# ── Tasks ───────────────────────────────────────────────────────────────────


def test_generate_pending_tasks_creates_one(db_session, frozen_clock):
    today = frozen_clock.date()
    plan = MaintenancePlanFactory(next_due_on=today)
    db_session.flush()
    created = services.generate_pending_tasks(db_session)
    assert len(created) == 1
    assert created[0].plan_id == plan.id
    # Idempotent: second call returns no new rows.
    again = services.generate_pending_tasks(db_session)
    assert again == []


def test_generate_pending_skips_far_future(db_session, frozen_clock):
    today = frozen_clock.date()
    MaintenancePlanFactory(next_due_on=today + timedelta(days=60))
    db_session.flush()
    assert services.generate_pending_tasks(db_session, horizon_days=14) == []


def test_generate_pending_skips_inactive(db_session, frozen_clock):
    today = frozen_clock.date()
    MaintenancePlanFactory(next_due_on=today, is_active=False)
    db_session.flush()
    assert services.generate_pending_tasks(db_session) == []


def test_assign_task_validation(db_session):
    task = MaintenanceTaskFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="technician not found"):
        services.assign_task(db_session, task, technician_id=b"\0" * 16)
    tech = TechnicianFactory(is_active=False)
    db_session.flush()
    with pytest.raises(ValueError, match="inactive"):
        services.assign_task(db_session, task, technician_id=tech.id)


def test_assign_task_only_when_pending(db_session):
    task = MaintenanceTaskFactory(status=TaskStatus.DONE)
    db_session.flush()
    with pytest.raises(ValueError, match="pending"):
        services.assign_task(db_session, task, technician_id=None)


def test_assign_task_happy_path(db_session):
    task = MaintenanceTaskFactory()
    tech = TechnicianFactory()
    db_session.flush()
    services.assign_task(db_session, task, technician_id=tech.id)
    assert task.assigned_technician_id == tech.id


def test_assign_task_clearing_assignment(db_session):
    """Passing ``technician_id=None`` unassigns the task."""
    tech = TechnicianFactory()
    task = MaintenanceTaskFactory(assigned_technician=tech)
    db_session.flush()
    services.assign_task(db_session, task, technician_id=None)
    assert task.assigned_technician_id is None


def test_complete_task_marks_done_and_recomputes(db_session, frozen_clock):
    today = frozen_clock.date()
    plan = MaintenancePlanFactory(cadence_days=7, next_due_on=today)
    task = MaintenanceTaskFactory(plan=plan, due_on=today)
    db_session.flush()
    execution = services.complete_task(db_session, task)
    assert task.status == TaskStatus.DONE
    assert task.plan.last_done_on == today
    assert task.plan.next_due_on == today + timedelta(days=7)
    assert isinstance(execution, MaintenanceExecution)
    # A follow-up pending task was generated for the new due date.
    follow_up = (
        db_session.query(MaintenanceTask)
        .filter(MaintenanceTask.plan_id == plan.id, MaintenanceTask.status == TaskStatus.PENDING)
        .first()
    )
    assert follow_up is not None
    assert follow_up.due_on == today + timedelta(days=7)


def test_complete_task_links_intervention(db_session):
    # Bump ticket numbers high so we never collide with rows committed by
    # earlier route tests (the conftest savepoint pattern doesn't catch
    # those — known limitation).
    ticket = ServiceTicketFactory(number=950_001)
    intervention = ServiceInterventionFactory(ticket=ticket)
    task = MaintenanceTaskFactory()
    db_session.flush()
    ex = services.complete_task(db_session, task, intervention_id=intervention.id, notes="ok")
    assert ex.intervention_id == intervention.id
    assert ex.notes == "ok"


def test_complete_task_validation(db_session):
    task = MaintenanceTaskFactory(status=TaskStatus.DONE)
    db_session.flush()
    with pytest.raises(ValueError, match="not pending"):
        services.complete_task(db_session, task)
    pending = MaintenanceTaskFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="intervention not found"):
        services.complete_task(db_session, pending, intervention_id=b"\0" * 16)


def test_escalate_task_creates_ticket(db_session):
    eq = EquipmentFactory()
    plan = MaintenancePlanFactory(equipment=eq)
    task = MaintenanceTaskFactory(plan=plan)
    db_session.flush()
    ticket = services.escalate_task(db_session, task, title="Custom title")
    assert task.status == TaskStatus.ESCALATED
    assert task.ticket_id == ticket.id
    assert ticket.title == "Custom title"
    assert ticket.equipment_id == eq.id


def test_escalate_task_defaults_title(db_session):
    plan = MaintenancePlanFactory()
    task = MaintenanceTaskFactory(plan=plan)
    db_session.flush()
    ticket = services.escalate_task(db_session, task)
    assert plan.template.name in ticket.title


def test_escalate_task_only_when_pending(db_session):
    task = MaintenanceTaskFactory(status=TaskStatus.DONE)
    db_session.flush()
    with pytest.raises(ValueError, match="pending"):
        services.escalate_task(db_session, task)


def test_scheduler_tick_idempotent(db_session, frozen_clock):
    today = frozen_clock.date()
    # 30-day cadence + last_done_on 30 days ago → next_due_on lands on today.
    plan = MaintenancePlanFactory(cadence_days=30, last_done_on=today - timedelta(days=30))
    db_session.flush()
    first = services.scheduler_tick(db_session)
    second = services.scheduler_tick(db_session)
    assert first["plans_recomputed"] >= 1
    assert first["tasks_generated"] == 1
    assert second["tasks_generated"] == 0
    assert plan.next_due_on == today


def test_list_tasks_filters(db_session, frozen_clock):
    today = frozen_clock.date()
    pending = MaintenanceTaskFactory(due_on=today)
    overdue = MaintenanceTaskFactory(due_on=today - timedelta(days=1))
    done = MaintenanceTaskFactory(due_on=today, status=TaskStatus.DONE)
    db_session.flush()
    pending_rows = services.list_tasks(db_session, status=TaskStatus.PENDING)
    done_rows = services.list_tasks(db_session, status=TaskStatus.DONE)
    overdue_rows = services.list_tasks(db_session, overdue_only=True)
    assert pending in pending_rows
    assert overdue in pending_rows
    assert done in done_rows
    assert overdue in overdue_rows
    assert pending not in overdue_rows
    with pytest.raises(ValueError, match="unknown"):
        services.list_tasks(db_session, status="bogus")


def test_list_tasks_filters_plan_and_tech(db_session):
    plan = MaintenancePlanFactory()
    other = MaintenancePlanFactory()
    tech = TechnicianFactory()
    in_plan = MaintenanceTaskFactory(plan=plan, assigned_technician=tech)
    MaintenanceTaskFactory(plan=other)
    db_session.flush()
    assert services.list_tasks(db_session, plan_id=plan.id) == [in_plan]
    assert services.list_tasks(db_session, technician_id=tech.id) == [in_plan]


def test_require_task_unknown(db_session):
    with pytest.raises(ValueError, match="not found"):
        services.require_task(db_session, "00" * 16)
    with pytest.raises(ValueError, match="invalid"):
        services.require_task(db_session, "zzzz")


def test_require_plan_invalid(db_session):
    with pytest.raises(ValueError, match="invalid"):
        services.require_plan(db_session, "zz")


def test_recompute_plan_public_helper(db_session, frozen_clock):
    plan = MaintenancePlanFactory(cadence_days=10, last_done_on=date(2026, 1, 1), next_due_on=None)
    db_session.flush()
    services.recompute_plan(db_session, plan)
    assert plan.next_due_on == date(2026, 1, 11)


# Silence ruff: factories' UserFactory is the technician-row source
_ = (UserFactory, ServiceTicketFactory)
