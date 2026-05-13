"""Unit tests for ``service_crm.dashboard.services``."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from service_crm.dashboard import services as ds
from service_crm.maintenance.models import TaskStatus
from service_crm.shared.date_window import DateWindow
from service_crm.tickets.state import TicketStatus
from tests.factories import (
    ClientFactory,
    EquipmentFactory,
    MaintenanceExecutionFactory,
    MaintenancePlanFactory,
    MaintenanceTaskFactory,
    ServiceInterventionFactory,
    ServiceTicketFactory,
    TechnicianAssignmentFactory,
    TechnicianFactory,
    UserFactory,
)


@pytest.fixture
def today() -> date:
    """Wednesday, 2026-05-13 — anchored so week math is predictable."""
    return date(2026, 5, 13)


@pytest.fixture
def now(today: date) -> datetime:
    return datetime(today.year, today.month, today.day, 12, 0, 0, tzinfo=UTC)


def _patch_clock(monkeypatch: pytest.MonkeyPatch, now: datetime) -> None:
    from service_crm.shared import clock

    monkeypatch.setattr(clock, "_now", lambda: now)


def test_manager_kpis_returns_six_tiles(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    kpis = ds.manager_kpis(db_session, today=now.date())
    codes = [k.code for k in kpis]
    assert codes == [
        "active_clients",
        "open_tickets",
        "overdue_tickets",
        "due_maintenance_week",
        "tickets_waiting_parts",
        "technician_utilization",
    ]
    assert all(k.drill_endpoint for k in kpis)


def test_manager_kpis_counts_active_clients(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    baseline = {k.code: k.value for k in ds.manager_kpis(db_session, today=now.date())}
    ClientFactory(is_active=True)
    ClientFactory(is_active=True)
    ClientFactory(is_active=False)  # excluded
    db_session.flush()
    kpis = {k.code: k.value for k in ds.manager_kpis(db_session, today=now.date())}
    assert kpis["active_clients"] == baseline["active_clients"] + 2


def test_manager_kpis_counts_open_and_overdue_tickets(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    baseline = {k.code: k.value for k in ds.manager_kpis(db_session, today=now.date())}
    client = ClientFactory()
    db_session.flush()
    ServiceTicketFactory(client=client, status=TicketStatus.NEW.value)
    ServiceTicketFactory(
        client=client,
        status=TicketStatus.IN_PROGRESS.value,
        due_at=now - timedelta(days=2),
    )
    ServiceTicketFactory(
        client=client,
        status=TicketStatus.SCHEDULED.value,
        due_at=now + timedelta(days=2),
    )
    ServiceTicketFactory(client=client, status=TicketStatus.CLOSED.value)
    db_session.flush()
    kpis = {k.code: k.value for k in ds.manager_kpis(db_session, today=now.date())}
    assert kpis["open_tickets"] == baseline["open_tickets"] + 3
    assert kpis["overdue_tickets"] == baseline["overdue_tickets"] + 1


def test_manager_kpis_counts_waiting_parts(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    baseline = {k.code: k.value for k in ds.manager_kpis(db_session, today=now.date())}
    client = ClientFactory()
    db_session.flush()
    ServiceTicketFactory(client=client, status=TicketStatus.WAITING_PARTS.value)
    ServiceTicketFactory(client=client, status=TicketStatus.WAITING_PARTS.value)
    ServiceTicketFactory(client=client, status=TicketStatus.NEW.value)
    db_session.flush()
    kpis = {k.code: k.value for k in ds.manager_kpis(db_session, today=now.date())}
    assert kpis["tickets_waiting_parts"] == baseline["tickets_waiting_parts"] + 2


def test_manager_kpis_counts_due_maintenance_this_week(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
    today: date,
) -> None:
    _patch_clock(monkeypatch, now)
    baseline = {k.code: k.value for k in ds.manager_kpis(db_session, today=today)}
    plan_this_week = MaintenancePlanFactory(is_active=True)
    plan_this_week.next_due_on = today + timedelta(days=1)
    plan_next_week = MaintenancePlanFactory(is_active=True)
    plan_next_week.next_due_on = today + timedelta(days=14)
    plan_inactive = MaintenancePlanFactory(is_active=False)
    plan_inactive.next_due_on = today + timedelta(days=1)
    db_session.flush()
    kpis = {k.code: k.value for k in ds.manager_kpis(db_session, today=today)}
    assert kpis["due_maintenance_week"] == baseline["due_maintenance_week"] + 1


def test_technician_utilization_handles_empty_roster(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    pct = ds.technician_utilization_pct(db_session, today=now.date())
    assert pct == 0


def test_technician_utilization_clamps_excess(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
    today: date,
) -> None:
    """High enough load that the 999% clamp kicks in regardless of any
    leaked technicians from sibling tests."""
    _patch_clock(monkeypatch, now)
    tech = TechnicianFactory(weekly_capacity_minutes=60)
    week_start = today - timedelta(days=today.weekday())
    week_dt = datetime(week_start.year, week_start.month, week_start.day, 9, 0, 0, tzinfo=UTC)
    for _ in range(500):
        asg = TechnicianAssignmentFactory(technician=tech)
        asg.assigned_at = week_dt
    db_session.flush()
    pct = ds.technician_utilization_pct(db_session, today=today)
    assert pct == 999


def test_technician_utilization_with_zero_capacity(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    TechnicianFactory(weekly_capacity_minutes=0)
    db_session.flush()
    pct = ds.technician_utilization_pct(db_session, today=now.date())
    assert pct == 0


def test_tickets_by_status_returns_only_nonzero_buckets(
    db_session: Session,
) -> None:
    baseline = dict(ds.tickets_by_status(db_session))
    client = ClientFactory()
    db_session.flush()
    ServiceTicketFactory(client=client, status=TicketStatus.NEW.value)
    ServiceTicketFactory(client=client, status=TicketStatus.NEW.value)
    ServiceTicketFactory(client=client, status=TicketStatus.CLOSED.value)
    db_session.flush()
    rows = dict(ds.tickets_by_status(db_session))
    assert rows.get("new", 0) - baseline.get("new", 0) == 2
    assert rows.get("closed", 0) - baseline.get("closed", 0) == 1


def test_upcoming_maintenance_orders_by_due_date(
    db_session: Session,
    today: date,
) -> None:
    plan_a = MaintenancePlanFactory(is_active=True)
    plan_a.next_due_on = today + timedelta(days=5)
    plan_b = MaintenancePlanFactory(is_active=True)
    plan_b.next_due_on = today + timedelta(days=1)
    plan_inactive = MaintenancePlanFactory(is_active=False)
    plan_inactive.next_due_on = today + timedelta(days=2)
    db_session.flush()
    rows = ds.upcoming_maintenance(db_session)
    # plan_b precedes plan_a (earlier due date); ignore any leaked plans.
    ids = [r.id for r in rows]
    assert plan_b.id in ids and plan_a.id in ids
    assert ids.index(plan_b.id) < ids.index(plan_a.id)
    assert plan_inactive.id not in ids


def test_upcoming_maintenance_skips_plans_without_due_date(
    db_session: Session,
) -> None:
    plan = MaintenancePlanFactory(is_active=True)
    plan.next_due_on = None
    db_session.flush()
    rows = ds.upcoming_maintenance(db_session)
    assert plan not in rows


def test_recent_interventions_orders_newest_first(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    older = ServiceInterventionFactory()
    older.started_at = now - timedelta(days=2)
    newer = ServiceInterventionFactory()
    newer.started_at = now - timedelta(hours=1)
    db_session.flush()
    rows = ds.recent_interventions(db_session)
    assert rows[0].id == newer.id
    assert rows[-1].id == older.id


def test_high_risk_machines_returns_equipment_above_threshold(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    client = ClientFactory()
    equipment = EquipmentFactory(client=client)
    db_session.flush()
    for _ in range(3):
        ServiceTicketFactory(client=client, equipment=equipment)
    other_equipment = EquipmentFactory(client=client)
    ServiceTicketFactory(client=client, equipment=other_equipment)
    db_session.flush()
    window = DateWindow(
        start=now.date() - timedelta(days=30),
        end_exclusive=now.date() + timedelta(days=1),
    )
    rows = ds.high_risk_machines(db_session, window=window, min_tickets=3)
    ids = {r["equipment"].id: r for r in rows}
    assert equipment.id in ids
    assert ids[equipment.id]["ticket_count"] == 3
    assert other_equipment.id not in ids


def test_technician_load_week_returns_per_tech_summary(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
    today: date,
) -> None:
    _patch_clock(monkeypatch, now)
    tech = TechnicianFactory()
    week_start = today - timedelta(days=today.weekday())
    week_dt = datetime(week_start.year, week_start.month, week_start.day, 9, 0, 0, tzinfo=UTC)
    asg = TechnicianAssignmentFactory(technician=tech)
    asg.assigned_at = week_dt
    db_session.flush()
    rows = ds.technician_load_week(db_session, today=today)
    rows_by_tech = {r["technician"].id: r for r in rows}
    row = rows_by_tech[tech.id]
    assert row["assignment_count"] == 1
    assert row["scheduled_minutes"] == 60
    assert row["tone"] == "success"


@pytest.mark.parametrize(
    ("capacity", "assignments", "expected_tone"),
    [
        # ratio 60/100 = 0.60 → success (< 0.75)
        (100, 1, "success"),
        # ratio (3 * 60)/240 = 0.75 → warning ([0.75, 1.0))
        (240, 3, "warning"),
        # ratio (5 * 60)/120 = 2.5 → danger (>= 1.0)
        (120, 5, "danger"),
    ],
)
def test_technician_load_week_tone_thresholds(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
    today: date,
    capacity: int,
    assignments: int,
    expected_tone: str,
) -> None:
    """Each saturation band yields its tone class."""
    _patch_clock(monkeypatch, now)
    tech = TechnicianFactory(weekly_capacity_minutes=capacity)
    week_start = today - timedelta(days=today.weekday())
    week_dt = datetime(week_start.year, week_start.month, week_start.day, 9, 0, 0, tzinfo=UTC)
    for _ in range(assignments):
        asg = TechnicianAssignmentFactory(technician=tech)
        asg.assigned_at = week_dt
    db_session.flush()
    rows = ds.technician_load_week(db_session, today=today)
    rows_by_tech = {r["technician"].id: r for r in rows}
    assert rows_by_tech[tech.id]["tone"] == expected_tone


def test_my_open_tickets_filters_to_assignee(
    db_session: Session,
) -> None:
    user = UserFactory()
    other = UserFactory()
    db_session.flush()
    mine = ServiceTicketFactory(assignee=user, status=TicketStatus.NEW.value)
    ServiceTicketFactory(assignee=user, status=TicketStatus.CLOSED.value)  # excluded
    ServiceTicketFactory(assignee=other, status=TicketStatus.NEW.value)  # excluded
    db_session.flush()
    rows = ds.my_open_tickets(db_session, user_id=user.id)
    assert [t.id for t in rows] == [mine.id]


def test_my_overdue_tickets_filters_to_overdue(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    user = UserFactory()
    db_session.flush()
    overdue = ServiceTicketFactory(
        assignee=user,
        status=TicketStatus.IN_PROGRESS.value,
        due_at=now - timedelta(days=1),
    )
    ServiceTicketFactory(  # future due — not overdue
        assignee=user,
        status=TicketStatus.IN_PROGRESS.value,
        due_at=now + timedelta(days=1),
    )
    ServiceTicketFactory(  # no due_at
        assignee=user,
        status=TicketStatus.IN_PROGRESS.value,
    )
    db_session.flush()
    rows = ds.my_overdue_tickets(db_session, user_id=user.id)
    assert [t.id for t in rows] == [overdue.id]


def test_my_maintenance_tasks_returns_pending_only(
    db_session: Session,
) -> None:
    tech = TechnicianFactory()
    db_session.flush()
    pending = MaintenanceTaskFactory(
        assigned_technician=tech,
        status=TaskStatus.PENDING,
    )
    MaintenanceTaskFactory(
        assigned_technician=tech,
        status=TaskStatus.DONE,
    )
    db_session.flush()
    rows = ds.my_maintenance_tasks(db_session, technician_id=tech.id)
    assert [t.id for t in rows] == [pending.id]


def test_my_maintenance_tasks_empty_when_no_technician(db_session: Session) -> None:
    assert ds.my_maintenance_tasks(db_session, technician_id=None) == []


def test_technician_summary_counts_open_overdue_and_tasks(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
    today: date,
) -> None:
    _patch_clock(monkeypatch, now)
    user = UserFactory()
    tech = TechnicianFactory(user=user)
    db_session.flush()
    ServiceTicketFactory(assignee=user, status=TicketStatus.IN_PROGRESS.value)
    ServiceTicketFactory(
        assignee=user,
        status=TicketStatus.IN_PROGRESS.value,
        due_at=now - timedelta(days=1),
    )
    overdue_task = MaintenanceTaskFactory(
        assigned_technician=tech,
        status=TaskStatus.PENDING,
    )
    overdue_task.due_on = today - timedelta(days=1)
    pending_future = MaintenanceTaskFactory(
        assigned_technician=tech,
        status=TaskStatus.PENDING,
    )
    pending_future.due_on = today + timedelta(days=5)
    db_session.flush()
    summary = ds.technician_summary(db_session, user_id=user.id, technician_id=tech.id, today=today)
    assert summary["open_tickets"] == 2
    assert summary["overdue_tickets"] == 1
    assert summary["pending_tasks"] == 2
    assert summary["overdue_tasks"] == 1


def test_technician_summary_without_technician_row(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    user = UserFactory()
    db_session.flush()
    ServiceTicketFactory(assignee=user, status=TicketStatus.IN_PROGRESS.value)
    db_session.flush()
    summary = ds.technician_summary(db_session, user_id=user.id, technician_id=None)
    assert summary["open_tickets"] == 1
    assert summary["pending_tasks"] == 0
    assert summary["overdue_tasks"] == 0


def test_default_window_uses_last_30_days(
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    _patch_clock(monkeypatch, now)
    w = ds.default_window()
    assert w.days == 30
    assert w.end_inclusive == now.date()


def test_recent_interventions_executions_link_back(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    """Smoke: MaintenanceExecution attaches via the task FK without
    breaking the recent-interventions query."""
    _patch_clock(monkeypatch, now)
    iv = ServiceInterventionFactory()
    iv.started_at = now - timedelta(hours=1)
    task = MaintenanceTaskFactory(status=TaskStatus.DONE)
    MaintenanceExecutionFactory(task=task, intervention=iv)
    db_session.flush()
    rows = ds.recent_interventions(db_session)
    assert any(r.id == iv.id for r in rows)
