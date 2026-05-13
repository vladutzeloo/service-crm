"""Service-layer tests for the planning blueprint."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from service_crm.planning import services
from service_crm.planning.models import Technician
from tests.factories import (
    ServiceInterventionFactory,
    ServiceTicketFactory,
    TechnicianAssignmentFactory,
    TechnicianCapacitySlotFactory,
    TechnicianFactory,
    UserFactory,
)


def test_list_technicians_filters_active(db_session):
    a = TechnicianFactory(display_name="tech-list-A-zz", is_active=True)
    b = TechnicianFactory(display_name="tech-list-B-zz", is_active=False)
    db_session.flush()
    active_names = {t.display_name for t in services.list_technicians(db_session)}
    all_names = {t.display_name for t in services.list_technicians(db_session, active_only=False)}
    assert a.display_name in active_names
    assert b.display_name not in active_names
    assert {a.display_name, b.display_name} <= all_names


def test_require_technician_unknown(db_session):
    with pytest.raises(ValueError, match="not found"):
        services.require_technician(db_session, "00" * 16)
    with pytest.raises(ValueError, match="invalid"):
        services.require_technician(db_session, "zz")


def test_require_technician_for_user(db_session):
    user = UserFactory()
    tech = TechnicianFactory(user=user)
    db_session.flush()
    assert services.require_technician_for_user(db_session, user.id) == tech
    other_user = UserFactory()
    db_session.flush()
    assert services.require_technician_for_user(db_session, other_user.id) is None


def test_create_technician_happy(db_session):
    user = UserFactory()
    db_session.flush()
    tech = services.create_technician(
        db_session,
        user_id=user.id,
        display_name="Alice",
        weekly_capacity_minutes=480,
        notes="hi",
    )
    assert tech.display_name == "Alice"
    assert tech.weekly_capacity_minutes == 480


def test_create_technician_defaults_display_name(db_session):
    user = UserFactory(email="defaults-display-name@example.com")
    db_session.flush()
    tech = services.create_technician(db_session, user_id=user.id)
    assert tech.display_name == "defaults-display-name@example.com"


def test_create_technician_validation(db_session):
    with pytest.raises(ValueError, match="user not found"):
        services.create_technician(db_session, user_id=b"\0" * 16)
    user = UserFactory(is_active=False)
    db_session.flush()
    with pytest.raises(ValueError, match="inactive"):
        services.create_technician(db_session, user_id=user.id)
    user2 = UserFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="non-negative"):
        services.create_technician(db_session, user_id=user2.id, weekly_capacity_minutes=-1)
    services.create_technician(db_session, user_id=user2.id)
    with pytest.raises(ValueError, match="already exists"):
        services.create_technician(db_session, user_id=user2.id)


def test_update_technician(db_session):
    tech = TechnicianFactory(display_name="A")
    db_session.flush()
    services.update_technician(
        db_session,
        tech,
        display_name="B",
        timezone="UTC",
        weekly_capacity_minutes=600,
        notes="updated",
        is_active=False,
    )
    assert tech.display_name == "B"
    assert tech.timezone == "UTC"
    assert tech.is_active is False


def test_update_technician_blank_falls_back(db_session):
    tech = TechnicianFactory(display_name="A", timezone="Europe/Bucharest")
    db_session.flush()
    services.update_technician(
        db_session,
        tech,
        display_name="",
        timezone="",
        weekly_capacity_minutes=tech.weekly_capacity_minutes,
        notes="",
        is_active=True,
    )
    # Falls back to user email and existing timezone.
    assert tech.display_name == tech.user.email
    assert tech.timezone == "Europe/Bucharest"


def test_update_technician_validation(db_session):
    tech = TechnicianFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="non-negative"):
        services.update_technician(
            db_session,
            tech,
            display_name="x",
            timezone="UTC",
            weekly_capacity_minutes=-1,
            notes="",
            is_active=True,
        )


def test_upsert_capacity_slot(db_session):
    tech = TechnicianFactory()
    db_session.flush()
    day = date(2026, 6, 1)
    slot = services.upsert_capacity_slot(
        db_session, technician_id=tech.id, day=day, capacity_minutes=240
    )
    assert slot.capacity_minutes == 240
    # Idempotent: same key updates rather than duplicates.
    slot2 = services.upsert_capacity_slot(
        db_session, technician_id=tech.id, day=day, capacity_minutes=300, notes="busy"
    )
    assert slot2.id == slot.id
    assert slot2.capacity_minutes == 300
    assert slot2.notes == "busy"


def test_upsert_capacity_slot_validation(db_session):
    tech = TechnicianFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="non-negative"):
        services.upsert_capacity_slot(
            db_session, technician_id=tech.id, day=date(2026, 6, 1), capacity_minutes=-1
        )
    with pytest.raises(ValueError, match="technician not found"):
        services.upsert_capacity_slot(
            db_session,
            technician_id=b"\0" * 16,
            day=date(2026, 6, 1),
            capacity_minutes=120,
        )


def test_list_capacity_slots_filters(db_session):
    tech_a = TechnicianFactory()
    tech_b = TechnicianFactory()
    db_session.flush()
    s_a = TechnicianCapacitySlotFactory(technician=tech_a, day=date(2026, 6, 1))
    s_b = TechnicianCapacitySlotFactory(technician=tech_b, day=date(2026, 6, 1))
    s_a2 = TechnicianCapacitySlotFactory(technician=tech_a, day=date(2026, 6, 5))
    db_session.flush()
    by_tech_a = services.list_capacity_slots(db_session, technician_id=tech_a.id)
    assert {s_a, s_a2} <= set(by_tech_a)
    assert s_b not in by_tech_a
    after_day2 = services.list_capacity_slots(db_session, start=date(2026, 6, 2))
    assert s_a2 in after_day2
    assert s_a not in after_day2
    on_day1 = services.list_capacity_slots(db_session, start=date(2026, 6, 1), end=date(2026, 6, 1))
    assert {s_a, s_b} <= set(on_day1)


def test_delete_capacity_slot(db_session):
    slot = TechnicianCapacitySlotFactory()
    db_session.flush()
    services.delete_capacity_slot(db_session, slot)
    assert db_session.query(type(slot)).filter_by(id=slot.id).first() is None


def test_require_capacity_slot(db_session):
    with pytest.raises(ValueError, match="not found"):
        services.require_capacity_slot(db_session, "00" * 16)
    with pytest.raises(ValueError, match="invalid"):
        services.require_capacity_slot(db_session, "zz")


def test_create_assignment_happy(db_session):
    tech = TechnicianFactory()
    ticket = ServiceTicketFactory()
    db_session.flush()
    asg = services.create_assignment(
        db_session, technician_id=tech.id, ticket_id=ticket.id, notes="hi"
    )
    assert asg.ticket_id == ticket.id
    assert asg.technician_id == tech.id
    assert asg.notes == "hi"


def test_create_assignment_validation(db_session):
    tech = TechnicianFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="needs a ticket"):
        services.create_assignment(db_session, technician_id=tech.id)
    with pytest.raises(ValueError, match="technician not found"):
        services.create_assignment(
            db_session,
            technician_id=b"\0" * 16,
            ticket_id=ServiceTicketFactory().id,
        )
    inactive = TechnicianFactory(is_active=False)
    db_session.flush()
    with pytest.raises(ValueError, match="inactive"):
        services.create_assignment(
            db_session, technician_id=inactive.id, ticket_id=ServiceTicketFactory().id
        )
    with pytest.raises(ValueError, match="ticket not found"):
        services.create_assignment(db_session, technician_id=tech.id, ticket_id=b"\0" * 16)
    with pytest.raises(ValueError, match="intervention not found"):
        services.create_assignment(db_session, technician_id=tech.id, intervention_id=b"\0" * 16)


def test_list_assignments_filters(db_session):
    tech_a = TechnicianFactory()
    tech_b = TechnicianFactory()
    a = TechnicianAssignmentFactory(technician=tech_a)
    TechnicianAssignmentFactory(technician=tech_b)
    db_session.flush()
    rows = services.list_assignments(db_session, technician_id=tech_a.id)
    assert rows == [a]
    assert len(services.list_assignments(db_session)) >= 2


def test_require_and_delete_assignment(db_session):
    asg = TechnicianAssignmentFactory()
    db_session.flush()
    found = services.require_assignment(db_session, asg.id.hex())
    assert found == asg
    services.delete_assignment(db_session, asg)
    assert db_session.query(type(asg)).filter_by(id=asg.id).first() is None
    with pytest.raises(ValueError, match="not found"):
        services.require_assignment(db_session, "00" * 16)
    with pytest.raises(ValueError, match="invalid"):
        services.require_assignment(db_session, "zz")


def _row_for(rows, tech):
    return next(r for r in rows if r["technician"] == tech)


def test_daily_load_uses_weekly_average_when_no_slot(db_session, frozen_clock):
    """No capacity slot for a day → fallback to ``weekly_capacity_minutes / 7``."""
    tech = TechnicianFactory(weekly_capacity_minutes=2400)
    db_session.flush()
    start = frozen_clock.date()
    end = start + timedelta(days=2)
    rows = services.daily_load(db_session, start=start, end=end)
    my_row = _row_for(rows, tech)
    for cell in my_row["days"]:
        assert cell["capacity_minutes"] == 2400 // 7


def test_daily_load_uses_explicit_slot(db_session, frozen_clock):
    tech = TechnicianFactory(weekly_capacity_minutes=2400)
    day = frozen_clock.date()
    TechnicianCapacitySlotFactory(technician=tech, day=day, capacity_minutes=120)
    db_session.flush()
    rows = services.daily_load(db_session, start=day, end=day)
    my_row = _row_for(rows, tech)
    assert my_row["days"][0]["capacity_minutes"] == 120


def test_daily_load_counts_assignments(db_session, frozen_clock):
    tech = TechnicianFactory()
    ticket = ServiceTicketFactory(number=950_002)
    intervention = ServiceInterventionFactory(ticket=ticket, started_at=frozen_clock)
    TechnicianAssignmentFactory(technician=tech, ticket=None, intervention=intervention)
    db_session.flush()
    rows = services.daily_load(db_session, start=frozen_clock.date(), end=frozen_clock.date())
    my_row = _row_for(rows, tech)
    assert my_row["days"][0]["assignment_count"] == 1


def test_daily_load_swaps_inverted_range(db_session, frozen_clock):
    tech = TechnicianFactory()
    db_session.flush()
    start = frozen_clock.date()
    end = start - timedelta(days=1)
    rows = services.daily_load(db_session, start=start, end=end)
    my_row = _row_for(rows, tech)
    # Range got normalised; two days returned.
    assert len(my_row["days"]) == 2


def test_daily_load_empty_when_no_active_techs(db_session, frozen_clock):
    # Avoid leaks: only the technician created here exists in this branch.
    # We deactivate it; assertion is "the row count doesn't include this tech".
    tech = TechnicianFactory(is_active=False, display_name="inactive-load-tech")
    db_session.flush()
    rows = services.daily_load(db_session, start=frozen_clock.date(), end=frozen_clock.date())
    names = {r["technician"].display_name for r in rows}
    assert tech.display_name not in names


# Quiet ruff: Technician import is referenced indirectly via factories
_ = Technician
