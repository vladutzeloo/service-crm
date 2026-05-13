"""Unit tests for ``service_crm.reports.services``."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from service_crm.maintenance.models import TaskStatus
from service_crm.reports import services as rs
from service_crm.shared.date_window import DateWindow
from service_crm.tickets.state import TicketStatus
from tests.factories import (
    ClientFactory,
    EquipmentFactory,
    MaintenanceExecutionFactory,
    MaintenancePlanFactory,
    MaintenanceTaskFactory,
    ServiceInterventionFactory,
    ServicePartUsageFactory,
    ServiceTicketFactory,
    TechnicianFactory,
    UserFactory,
)


@pytest.fixture
def window_short() -> DateWindow:
    return DateWindow(start=date(2026, 5, 1), end_exclusive=date(2026, 5, 14))


@pytest.fixture
def window_med() -> DateWindow:
    return DateWindow(start=date(2026, 1, 1), end_exclusive=date(2026, 5, 1))


@pytest.fixture
def window_long() -> DateWindow:
    return DateWindow(start=date(2025, 1, 1), end_exclusive=date(2026, 5, 1))


def _patch_clock(monkeypatch: pytest.MonkeyPatch, when: datetime) -> None:
    from service_crm.shared import clock

    monkeypatch.setattr(clock, "_now", lambda: when)


# ── Bucketing ────────────────────────────────────────────────────────────────


def test_choose_bucket_uses_day_for_short_windows(window_short: DateWindow) -> None:
    assert rs.choose_bucket(window_short) == rs.PERIOD_DAY


def test_choose_bucket_uses_week_for_medium_windows(window_med: DateWindow) -> None:
    assert rs.choose_bucket(window_med) == rs.PERIOD_WEEK


def test_choose_bucket_uses_month_for_long_windows(window_long: DateWindow) -> None:
    assert rs.choose_bucket(window_long) == rs.PERIOD_MONTH


def test_bucket_for_day_returns_same_day() -> None:
    assert rs.bucket_for(date(2026, 5, 13), rs.PERIOD_DAY) == date(2026, 5, 13)


def test_bucket_for_week_anchors_to_monday() -> None:
    assert rs.bucket_for(date(2026, 5, 13), rs.PERIOD_WEEK) == date(2026, 5, 11)


def test_bucket_for_month_anchors_to_first() -> None:
    assert rs.bucket_for(date(2026, 5, 13), rs.PERIOD_MONTH) == date(2026, 5, 1)


def test_bucket_for_unknown_raises() -> None:
    with pytest.raises(ValueError, match="bucket"):
        rs.bucket_for(date(2026, 5, 13), "year")


# ── tickets_by_status ────────────────────────────────────────────────────────


def test_tickets_by_status_groups_by_bucket_and_status(
    db_session: Session,
    window_short: DateWindow,
) -> None:
    """Sibling route tests commit data that leaks across the
    SAVEPOINT rollback (a known limitation tracked in v0.7 plan §6.6),
    so we restrict the assertion to a tight day window the test owns."""
    tight = DateWindow(start=date(2026, 5, 5), end_exclusive=date(2026, 5, 6))
    client = ClientFactory()
    db_session.flush()
    baseline_total = rs.tickets_by_status(db_session, window=tight).total_row[-1]
    t1 = ServiceTicketFactory(client=client, status=TicketStatus.NEW.value)
    t1.created_at = datetime(2026, 5, 5, 10, 0, 0)
    t2 = ServiceTicketFactory(client=client, status=TicketStatus.NEW.value)
    t2.created_at = datetime(2026, 5, 5, 12, 0, 0)
    t3 = ServiceTicketFactory(client=client, status=TicketStatus.CLOSED.value)
    t3.created_at = datetime(2026, 5, 5, 14, 0, 0)
    # outside the window — excluded.
    out = ServiceTicketFactory(client=client, status=TicketStatus.NEW.value)
    out.created_at = datetime(2026, 4, 20, 10, 0, 0)
    db_session.flush()
    result = rs.tickets_by_status(db_session, window=tight)
    assert result.total_row is not None
    assert result.total_row[-1] == baseline_total + 3
    # Single bucket since the window is one day.
    buckets = {r[0] for r in result.rows}
    assert buckets == {"2026-05-05"}


def test_tickets_by_status_uses_passed_label_function(
    db_session: Session,
    window_short: DateWindow,
) -> None:
    client = ClientFactory()
    db_session.flush()
    t = ServiceTicketFactory(client=client, status=TicketStatus.NEW.value)
    t.created_at = datetime(2026, 5, 5, 10, 0, 0)
    db_session.flush()
    result = rs.tickets_by_status(
        db_session,
        window=window_short,
        status_label=lambda code: f"L({code})",
    )
    assert result.rows[0][2] == "L(new)"


def test_tickets_by_status_empty_window(db_session: Session) -> None:
    """A window with no tickets (far past) yields the empty total."""
    empty_window = DateWindow(start=date(2024, 1, 1), end_exclusive=date(2024, 1, 2))
    result = rs.tickets_by_status(db_session, window=empty_window)
    assert result.rows == []
    assert result.total_row == ("", "", "TOTAL", 0)


# ── interventions_by_machine ─────────────────────────────────────────────────


def test_interventions_by_machine_sums_duration_and_open(
    db_session: Session,
) -> None:
    """Tight window owned by this test to dodge commit-leakage from
    sibling route tests (see v0.7 plan §6.6)."""
    tight = DateWindow(start=date(2024, 6, 1), end_exclusive=date(2024, 6, 15))
    client = ClientFactory()
    equipment = EquipmentFactory(client=client)
    db_session.flush()
    ticket = ServiceTicketFactory(client=client, equipment=equipment)
    iv_closed = ServiceInterventionFactory(ticket=ticket)
    iv_closed.started_at = datetime(2024, 6, 2, 9, 0, 0, tzinfo=UTC)
    iv_closed.ended_at = datetime(2024, 6, 2, 10, 0, 0, tzinfo=UTC)
    iv_open = ServiceInterventionFactory(ticket=ticket)
    iv_open.started_at = datetime(2024, 6, 5, 9, 0, 0, tzinfo=UTC)
    iv_open.ended_at = None
    db_session.flush()
    result = rs.interventions_by_machine(db_session, window=tight)
    rows_by_equipment = {r[0]: r for r in result.rows}
    row = rows_by_equipment[equipment.id.hex()]
    assert row[1] == equipment.label
    assert row[2] == 2  # count
    assert row[3] == 60  # minutes (one closed hour)
    assert row[4] == 1  # open


def test_interventions_by_machine_excludes_out_of_window(
    db_session: Session,
) -> None:
    tight = DateWindow(start=date(2024, 6, 10), end_exclusive=date(2024, 6, 11))
    client = ClientFactory()
    equipment = EquipmentFactory(client=client)
    db_session.flush()
    ticket = ServiceTicketFactory(client=client, equipment=equipment)
    iv = ServiceInterventionFactory(ticket=ticket)
    iv.started_at = datetime(2024, 5, 1, 9, 0, 0, tzinfo=UTC)
    db_session.flush()
    result = rs.interventions_by_machine(db_session, window=tight)
    assert all(r[0] != equipment.id.hex() for r in result.rows)


# ── parts_used ───────────────────────────────────────────────────────────────


def test_parts_used_sums_quantities_per_code(
    db_session: Session,
) -> None:
    tight = DateWindow(start=date(2024, 7, 1), end_exclusive=date(2024, 7, 15))
    client = ClientFactory()
    db_session.flush()
    ticket = ServiceTicketFactory(client=client)
    iv = ServiceInterventionFactory(ticket=ticket)
    iv.started_at = datetime(2024, 7, 2, 9, 0, 0, tzinfo=UTC)
    ServicePartUsageFactory(
        intervention=iv, part_code="PART-RPT-A", description="Bearing", quantity=3
    )
    ServicePartUsageFactory(
        intervention=iv, part_code="PART-RPT-A", description="Bearing", quantity=2
    )
    ServicePartUsageFactory(intervention=iv, part_code="PART-RPT-B", description="Belt", quantity=1)
    db_session.flush()
    result = rs.parts_used(db_session, window=tight)
    qty_by_code = {r[0]: r[2] for r in result.rows}
    assert qty_by_code.get("PART-RPT-A") == 5
    assert qty_by_code.get("PART-RPT-B") == 1


def test_parts_used_excludes_out_of_window(
    db_session: Session,
) -> None:
    tight = DateWindow(start=date(2024, 8, 1), end_exclusive=date(2024, 8, 2))
    client = ClientFactory()
    db_session.flush()
    ticket = ServiceTicketFactory(client=client)
    iv = ServiceInterventionFactory(ticket=ticket)
    iv.started_at = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)
    ServicePartUsageFactory(intervention=iv, part_code="PART-RPT-OLD", quantity=10)
    db_session.flush()
    result = rs.parts_used(db_session, window=tight)
    codes = {r[0] for r in result.rows}
    assert "PART-RPT-OLD" not in codes


# ── maintenance_due_vs_completed ─────────────────────────────────────────────


def test_maintenance_due_vs_completed_buckets_both_streams(
    db_session: Session,
) -> None:
    tight = DateWindow(start=date(2024, 9, 1), end_exclusive=date(2024, 9, 15))
    plan = MaintenancePlanFactory(is_active=True)
    due = MaintenanceTaskFactory(plan=plan)
    due.due_on = date(2024, 9, 5)
    done_task = MaintenanceTaskFactory(plan=plan, status=TaskStatus.DONE)
    done_task.due_on = date(2024, 9, 6)
    MaintenanceExecutionFactory(
        task=done_task,
        completed_at=datetime(2024, 9, 6, 12, 0, 0, tzinfo=UTC),
    )
    db_session.flush()
    result = rs.maintenance_due_vs_completed(db_session, window=tight)
    grouped = {r[0]: (r[1], r[2]) for r in result.rows}
    assert grouped.get("2024-09-05") == (1, 0)
    assert grouped.get("2024-09-06") == (1, 1)


# ── technician_workload ──────────────────────────────────────────────────────


def test_technician_workload_groups_interventions_and_executions(
    db_session: Session,
) -> None:
    tight = DateWindow(start=date(2024, 10, 1), end_exclusive=date(2024, 10, 15))
    user = UserFactory()
    tech = TechnicianFactory(user=user, display_name="Anya")
    db_session.flush()
    ticket = ServiceTicketFactory()
    iv = ServiceInterventionFactory(ticket=ticket, technician=user)
    iv.started_at = datetime(2024, 10, 5, 9, 0, 0, tzinfo=UTC)
    iv.ended_at = datetime(2024, 10, 5, 10, 30, 0, tzinfo=UTC)
    task = MaintenanceTaskFactory(assigned_technician=tech, status=TaskStatus.DONE)
    task.due_on = date(2024, 10, 6)
    MaintenanceExecutionFactory(
        task=task,
        completed_at=datetime(2024, 10, 6, 12, 0, 0, tzinfo=UTC),
    )
    db_session.flush()
    result = rs.technician_workload(db_session, window=tight)
    rows_by_tech = {r[0]: r for r in result.rows}
    row = rows_by_tech[tech.id.hex()]
    assert row[1] == "Anya"
    assert row[2] == 1
    assert row[3] == 90
    assert row[4] == 0
    assert row[5] == 1


def test_technician_workload_lists_unassigned_users(
    db_session: Session,
) -> None:
    """A user with an intervention but no Technician row still appears."""
    tight = DateWindow(start=date(2024, 11, 1), end_exclusive=date(2024, 11, 15))
    user = UserFactory(email="rogue@example.com")
    db_session.flush()
    ticket = ServiceTicketFactory()
    iv = ServiceInterventionFactory(ticket=ticket, technician=user)
    iv.started_at = datetime(2024, 11, 5, 9, 0, 0, tzinfo=UTC)
    db_session.flush()
    result = rs.technician_workload(db_session, window=tight)
    labels = {r[1] for r in result.rows}
    assert "rogue@example.com" in labels


# ── repeat_issues ────────────────────────────────────────────────────────────


def test_repeat_issues_returns_equipment_with_multiple_tickets(
    db_session: Session,
) -> None:
    tight = DateWindow(start=date(2024, 12, 1), end_exclusive=date(2024, 12, 15))
    client = ClientFactory(name="Acme")
    equipment = EquipmentFactory(client=client)
    other_equipment = EquipmentFactory(client=client)
    db_session.flush()
    for _ in range(3):
        t = ServiceTicketFactory(client=client, equipment=equipment)
        t.created_at = datetime(2024, 12, 5, 9, 0, 0)
    single = ServiceTicketFactory(client=client, equipment=other_equipment)
    single.created_at = datetime(2024, 12, 5, 9, 0, 0)
    db_session.flush()
    result = rs.repeat_issues(db_session, window=tight)
    codes = {r[0] for r in result.rows}
    assert equipment.id.hex() in codes
    assert other_equipment.id.hex() not in codes


def test_repeat_issues_respects_min_tickets(
    db_session: Session,
) -> None:
    tight = DateWindow(start=date(2023, 1, 1), end_exclusive=date(2023, 1, 15))
    client = ClientFactory()
    equipment = EquipmentFactory(client=client)
    db_session.flush()
    for _ in range(2):
        t = ServiceTicketFactory(client=client, equipment=equipment)
        t.created_at = datetime(2023, 1, 5, 9, 0, 0)
    db_session.flush()
    result_strict = rs.repeat_issues(db_session, window=tight, min_tickets=3)
    assert all(r[0] != equipment.id.hex() for r in result_strict.rows)
    result_lenient = rs.repeat_issues(db_session, window=tight, min_tickets=2)
    assert any(r[0] == equipment.id.hex() for r in result_lenient.rows)


# ── planning_summary_for_links ───────────────────────────────────────────────


def test_planning_summary_for_links_returns_template_name(
    db_session: Session,
) -> None:
    plan = MaintenancePlanFactory(is_active=True)
    db_session.flush()
    assert rs.planning_summary_for_links(plan=plan) == plan.template.name
