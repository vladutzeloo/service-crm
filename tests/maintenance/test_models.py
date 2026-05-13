"""Model-level tests for the maintenance blueprint."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from service_crm.maintenance.models import (
    MaintenanceExecution,
    MaintenanceTask,
    TaskStatus,
)
from tests.factories import (
    EquipmentFactory,
    MaintenanceExecutionFactory,
    MaintenancePlanFactory,
    MaintenanceTaskFactory,
    MaintenanceTemplateFactory,
)


def test_template_name_unique(db_session):
    MaintenanceTemplateFactory(name="quarterly")
    db_session.flush()
    with pytest.raises((IntegrityError, Exception)):
        MaintenanceTemplateFactory(name="quarterly")
    db_session.rollback()


def test_template_cadence_must_be_positive(db_session):
    with pytest.raises(IntegrityError):
        MaintenanceTemplateFactory(cadence_days=0)
    db_session.rollback()


def test_plan_belongs_to_template(db_session):
    template = MaintenanceTemplateFactory()
    eq = EquipmentFactory()
    plan = MaintenancePlanFactory(equipment=eq, template=template)
    db_session.flush()
    assert plan.template_id == template.id
    assert plan in template.plans


def test_plan_is_overdue_property(db_session, frozen_clock):
    today = frozen_clock.date()
    plan = MaintenancePlanFactory(next_due_on=today - timedelta(days=1))
    db_session.flush()
    assert plan.is_overdue is True
    plan.next_due_on = today + timedelta(days=1)
    assert plan.is_overdue is False
    plan.next_due_on = None
    assert plan.is_overdue is False


def test_task_cascades_when_plan_deleted(db_session):
    plan = MaintenancePlanFactory()
    task = MaintenanceTaskFactory(plan=plan, due_on=date(2026, 6, 1))
    db_session.flush()
    db_session.delete(plan)
    db_session.flush()
    assert db_session.get(MaintenanceTask, task.id) is None


def test_execution_cascades_when_task_deleted(db_session):
    task = MaintenanceTaskFactory()
    execution = MaintenanceExecutionFactory(task=task)
    db_session.flush()
    db_session.delete(task)
    db_session.flush()
    assert db_session.get(MaintenanceExecution, execution.id) is None


def test_task_status_default_is_pending(db_session):
    task = MaintenanceTaskFactory()
    db_session.flush()
    assert task.status == TaskStatus.PENDING
    assert task.is_done is False


def test_task_is_overdue(db_session, frozen_clock):
    today = frozen_clock.date()
    task = MaintenanceTaskFactory(due_on=today - timedelta(days=1))
    db_session.flush()
    assert task.is_overdue is True
    # Non-pending tasks never report overdue regardless of due date.
    task.status = TaskStatus.DONE
    assert task.is_overdue is False


def test_template_repr_round_trip(db_session):
    tpl = MaintenanceTemplateFactory()
    db_session.flush()
    assert "MaintenanceTemplate" in repr(tpl)


def test_plan_repr_round_trip(db_session):
    plan = MaintenancePlanFactory()
    db_session.flush()
    assert "MaintenancePlan" in repr(plan)


def test_task_repr_round_trip(db_session):
    task = MaintenanceTaskFactory()
    db_session.flush()
    assert "MaintenanceTask" in repr(task)


def test_execution_repr_round_trip(db_session):
    ex = MaintenanceExecutionFactory()
    db_session.flush()
    assert "MaintenanceExecution" in repr(ex)


def test_task_status_all_set():
    assert frozenset({"pending", "done", "escalated"}) == TaskStatus.ALL
