"""Service-layer tests for the tickets blueprint.

Covers the create/update/transition flow, the equipment-belongs-to-
client guard, the cross-cutting reason-required-for-cancel rule, the
search filter, comments, attachments (without the upload pipeline —
see ``test_uploads.py``), and the lookup CRUD helpers.
"""

from __future__ import annotations

import io

import pytest
from sqlalchemy.orm import Session

from service_crm.tickets import services
from service_crm.tickets.models import (
    TicketComment,
    TicketPriority,
    TicketStatusHistory,
    TicketType,
)
from service_crm.tickets.state import IllegalTransition, TicketStatus
from tests.factories import (
    ClientFactory,
    EquipmentFactory,
    ServiceTicketFactory,
    TicketCommentFactory,
    UserFactory,
)

# ── Lookups ─────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_list_ticket_types_filters_active(db_session: Session) -> None:
    types = services.list_ticket_types(db_session)
    assert all(t.is_active for t in types)
    all_types = services.list_ticket_types(db_session, active_only=False)
    assert {t.code for t in types} <= {t.code for t in all_types}


@pytest.mark.integration
def test_list_ticket_priorities_filters_active(db_session: Session) -> None:
    prios = services.list_ticket_priorities(db_session)
    assert all(p.is_active for p in prios)


@pytest.mark.integration
def test_require_ticket_type_bad_hex(db_session: Session) -> None:
    with pytest.raises(ValueError):
        services.require_ticket_type(db_session, "not-hex")


@pytest.mark.integration
def test_require_ticket_type_unknown(db_session: Session) -> None:
    with pytest.raises(ValueError):
        services.require_ticket_type(db_session, "00" * 16)


@pytest.mark.integration
def test_require_ticket_priority_bad_hex(db_session: Session) -> None:
    with pytest.raises(ValueError):
        services.require_ticket_priority(db_session, "not-hex")


@pytest.mark.integration
def test_require_ticket_priority_unknown(db_session: Session) -> None:
    with pytest.raises(ValueError):
        services.require_ticket_priority(db_session, "00" * 16)


@pytest.mark.integration
def test_default_lookups(db_session: Session) -> None:
    assert services.default_ticket_type(db_session).code == "incident"  # type: ignore[union-attr]
    assert services.default_ticket_priority(db_session).code == "normal"  # type: ignore[union-attr]


@pytest.mark.integration
def test_update_ticket_type(db_session: Session) -> None:
    t = db_session.query(TicketType).filter(TicketType.code == "incident").one()
    services.update_ticket_type(db_session, t, label="Incidentul", is_active=False)
    db_session.flush()
    refreshed = db_session.query(TicketType).filter(TicketType.id == t.id).one()
    assert refreshed.label == "Incidentul"
    assert refreshed.is_active is False


@pytest.mark.integration
def test_update_ticket_priority(db_session: Session) -> None:
    p = db_session.query(TicketPriority).filter(TicketPriority.code == "low").one()
    services.update_ticket_priority(db_session, p, label="LOW!", is_active=False)
    db_session.flush()
    refreshed = db_session.query(TicketPriority).filter(TicketPriority.id == p.id).one()
    assert refreshed.label == "LOW!"
    assert refreshed.is_active is False


# ── Tickets: require / create / update ──────────────────────────────────────


@pytest.mark.integration
def test_require_ticket_bad_hex(db_session: Session) -> None:
    with pytest.raises(ValueError):
        services.require_ticket(db_session, "not-hex")


@pytest.mark.integration
def test_require_ticket_unknown(db_session: Session) -> None:
    with pytest.raises(ValueError):
        services.require_ticket(db_session, "00" * 16)


@pytest.mark.integration
def test_create_ticket_minimal(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()
    ticket = services.create_ticket(db_session, client_id=client.id, title="Help!")
    db_session.flush()
    assert ticket.client_id == client.id
    assert ticket.status == TicketStatus.NEW.value
    assert ticket.number >= 1
    # The audit listener writes the initial history row.
    rows = (
        db_session.query(TicketStatusHistory)
        .filter(TicketStatusHistory.ticket_id == ticket.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].from_state is None


@pytest.mark.integration
def test_create_ticket_unknown_client(db_session: Session) -> None:
    with pytest.raises(ValueError, match="client not found"):
        services.create_ticket(db_session, client_id=b"\x00" * 16, title="x")


@pytest.mark.integration
def test_create_ticket_requires_title(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="title is required"):
        services.create_ticket(db_session, client_id=client.id, title="   ")


@pytest.mark.integration
def test_create_ticket_equipment_belongs_to_client_guard(db_session: Session) -> None:
    c1 = ClientFactory()
    c2 = ClientFactory()
    eq = EquipmentFactory(client=c2)
    db_session.flush()
    with pytest.raises(ValueError, match="equipment does not belong"):
        services.create_ticket(db_session, client_id=c1.id, equipment_id=eq.id, title="x")


@pytest.mark.integration
def test_create_ticket_equipment_not_found(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="equipment not found"):
        services.create_ticket(
            db_session, client_id=client.id, equipment_id=b"\x00" * 16, title="x"
        )


@pytest.mark.integration
def test_create_ticket_unknown_type(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="ticket type not found"):
        services.create_ticket(db_session, client_id=client.id, type_id=b"\x00" * 16, title="x")


@pytest.mark.integration
def test_create_ticket_unknown_priority(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="ticket priority not found"):
        services.create_ticket(db_session, client_id=client.id, priority_id=b"\x00" * 16, title="x")


@pytest.mark.integration
def test_create_ticket_with_equipment_and_assignee(db_session: Session) -> None:
    """Happy path through both ``_validate_equipment_belongs_to_client``
    and ``_validate_user_active`` (no early return; both checks pass)."""
    client = ClientFactory()
    eq = EquipmentFactory(client=client)
    user = UserFactory(is_active=True)
    db_session.flush()
    ticket = services.create_ticket(
        db_session,
        client_id=client.id,
        equipment_id=eq.id,
        assignee_user_id=user.id,
        title="happy-with-fk",
    )
    db_session.flush()
    assert ticket.equipment_id == eq.id
    assert ticket.assignee_user_id == user.id


@pytest.mark.integration
def test_create_ticket_inactive_assignee_rejected(db_session: Session) -> None:
    client = ClientFactory()
    user = UserFactory(is_active=False)
    db_session.flush()
    with pytest.raises(ValueError, match="inactive"):
        services.create_ticket(db_session, client_id=client.id, assignee_user_id=user.id, title="x")


@pytest.mark.integration
def test_create_ticket_assignee_not_found(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="assignee not found"):
        services.create_ticket(
            db_session, client_id=client.id, assignee_user_id=b"\x00" * 16, title="x"
        )


@pytest.mark.integration
def test_ticket_number_increments(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()
    t1 = services.create_ticket(db_session, client_id=client.id, title="a")
    t2 = services.create_ticket(db_session, client_id=client.id, title="b")
    db_session.flush()
    assert t2.number == t1.number + 1


@pytest.mark.integration
def test_update_ticket_happy_path(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    services.update_ticket(
        db_session,
        ticket,
        title="Updated",
        description="Updated desc",
        equipment_id=None,
        type_id=None,
        priority_id=None,
        assignee_user_id=None,
        due_at=None,
        sla_due_at=None,
    )
    db_session.flush()
    assert ticket.title == "Updated"
    assert ticket.description == "Updated desc"


@pytest.mark.integration
def test_update_ticket_requires_title(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="title is required"):
        services.update_ticket(
            db_session,
            ticket,
            title="  ",
            description="",
            equipment_id=None,
            type_id=None,
            priority_id=None,
            assignee_user_id=None,
            due_at=None,
            sla_due_at=None,
        )


@pytest.mark.integration
def test_update_ticket_equipment_guard(db_session: Session) -> None:
    c1 = ClientFactory()
    c2 = ClientFactory()
    eq_other = EquipmentFactory(client=c2)
    ticket = ServiceTicketFactory(client=c1)
    db_session.flush()
    with pytest.raises(ValueError, match="equipment does not belong"):
        services.update_ticket(
            db_session,
            ticket,
            title="x",
            description="",
            equipment_id=eq_other.id,
            type_id=None,
            priority_id=None,
            assignee_user_id=None,
            due_at=None,
            sla_due_at=None,
        )


@pytest.mark.integration
def test_update_ticket_unknown_type(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="ticket type not found"):
        services.update_ticket(
            db_session,
            ticket,
            title="x",
            description="",
            equipment_id=None,
            type_id=b"\x00" * 16,
            priority_id=None,
            assignee_user_id=None,
            due_at=None,
            sla_due_at=None,
        )


@pytest.mark.integration
def test_update_ticket_unknown_priority(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="ticket priority not found"):
        services.update_ticket(
            db_session,
            ticket,
            title="x",
            description="",
            equipment_id=None,
            type_id=None,
            priority_id=b"\x00" * 16,
            assignee_user_id=None,
            due_at=None,
            sla_due_at=None,
        )


# ── Transitions ─────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_transition_legal_move_writes_history(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    services.transition_ticket(db_session, ticket, to_state=TicketStatus.QUALIFIED, role="admin")
    db_session.flush()
    rows = (
        db_session.query(TicketStatusHistory)
        .filter(TicketStatusHistory.ticket_id == ticket.id)
        .order_by(TicketStatusHistory.occurred_at)
        .all()
    )
    assert rows[-1].to_state == TicketStatus.QUALIFIED.value
    assert rows[-1].from_state == TicketStatus.NEW.value


@pytest.mark.integration
def test_transition_illegal_raises(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    with pytest.raises(IllegalTransition):
        services.transition_ticket(
            db_session, ticket, to_state=TicketStatus.IN_PROGRESS, role="admin"
        )


@pytest.mark.integration
def test_transition_cancel_requires_reason(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="reason is required"):
        services.transition_ticket(
            db_session, ticket, to_state=TicketStatus.CANCELLED, role="admin"
        )


@pytest.mark.integration
def test_transition_cancel_with_reason(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    services.transition_ticket(
        db_session,
        ticket,
        to_state=TicketStatus.CANCELLED,
        role="admin",
        reason="dupe",
        reason_code="duplicate",
    )
    db_session.flush()
    last = (
        db_session.query(TicketStatusHistory)
        .filter(TicketStatusHistory.ticket_id == ticket.id)
        .order_by(TicketStatusHistory.occurred_at.desc())
        .first()
    )
    assert last is not None
    assert last.reason == "dupe"
    assert last.reason_code == "duplicate"
    assert ticket.status == TicketStatus.CANCELLED.value


@pytest.mark.integration
def test_transition_close_stamps_closed_at(db_session: Session) -> None:
    ticket = ServiceTicketFactory(status=TicketStatus.COMPLETED.value)
    db_session.flush()
    services.transition_ticket(db_session, ticket, to_state=TicketStatus.CLOSED, role="admin")
    db_session.flush()
    assert ticket.closed_at is not None


# ── Listing / filtering ─────────────────────────────────────────────────────


@pytest.mark.integration
def test_list_tickets_filters_by_status(db_session: Session) -> None:
    ServiceTicketFactory(status=TicketStatus.NEW.value, title="A")
    ServiceTicketFactory(status=TicketStatus.IN_PROGRESS.value, title="B")
    db_session.flush()
    items, total = services.list_tickets(db_session, statuses=[TicketStatus.IN_PROGRESS.value])
    assert total >= 1
    assert all(t.status == TicketStatus.IN_PROGRESS.value for t in items)


@pytest.mark.integration
def test_list_tickets_open_only_excludes_terminal(db_session: Session) -> None:
    ServiceTicketFactory(status=TicketStatus.CLOSED.value, title="Closed1")
    ServiceTicketFactory(status=TicketStatus.NEW.value, title="Open1")
    db_session.flush()
    items, _total = services.list_tickets(db_session, open_only=True)
    assert all(t.status != TicketStatus.CLOSED.value for t in items)


@pytest.mark.integration
def test_list_tickets_search_filter(db_session: Session) -> None:
    ServiceTicketFactory(title="Unique-searchable-token")
    db_session.flush()
    items, _total = services.list_tickets(db_session, q="searchable")
    assert any("Unique-searchable-token" in t.title for t in items)


@pytest.mark.integration
def test_list_tickets_filters_by_client(db_session: Session) -> None:
    c1 = ClientFactory()
    c2 = ClientFactory()
    ServiceTicketFactory(client=c1, title="c1-ticket")
    ServiceTicketFactory(client=c2, title="c2-ticket")
    db_session.flush()
    items, _total = services.list_tickets(db_session, client_id=c1.id)
    assert all(t.client_id == c1.id for t in items)


@pytest.mark.integration
def test_list_tickets_filters_by_assignee(db_session: Session) -> None:
    user = UserFactory()
    db_session.flush()
    ServiceTicketFactory(assignee=user, title="mine")
    db_session.flush()
    items, _total = services.list_tickets(db_session, assignee_user_id=user.id)
    assert all(t.assignee_user_id == user.id for t in items)


@pytest.mark.integration
def test_list_tickets_filters_by_type_priority_equipment(db_session: Session) -> None:
    t_type = db_session.query(TicketType).filter(TicketType.code == "preventive").one()
    t_prio = db_session.query(TicketPriority).filter(TicketPriority.code == "high").one()
    client = ClientFactory()
    eq = EquipmentFactory(client=client)
    db_session.flush()
    ServiceTicketFactory(client=client, equipment=eq, type=t_type, priority=t_prio, title="match")
    db_session.flush()
    items, _t = services.list_tickets(
        db_session,
        type_id=t_type.id,
        priority_id=t_prio.id,
        equipment_id=eq.id,
    )
    assert items
    assert all(
        t.type_id == t_type.id and t.priority_id == t_prio.id and t.equipment_id == eq.id
        for t in items
    )


@pytest.mark.integration
def test_status_counts_groups(db_session: Session) -> None:
    ServiceTicketFactory(status=TicketStatus.NEW.value)
    ServiceTicketFactory(status=TicketStatus.NEW.value)
    ServiceTicketFactory(status=TicketStatus.IN_PROGRESS.value)
    db_session.flush()
    counts = services.status_counts(db_session)
    assert counts.get(TicketStatus.NEW.value, 0) >= 2
    assert counts.get(TicketStatus.IN_PROGRESS.value, 0) >= 1


@pytest.mark.integration
def test_list_for_equipment_and_client(db_session: Session) -> None:
    client = ClientFactory()
    eq = EquipmentFactory(client=client)
    ServiceTicketFactory(client=client, equipment=eq)
    db_session.flush()
    assert services.list_for_equipment(db_session, eq.id)
    assert services.list_for_client(db_session, client.id)


# ── Comments ────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_add_comment_happy_path(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    user = UserFactory()
    db_session.flush()
    c = services.add_comment(db_session, ticket_id=ticket.id, author_user_id=user.id, body="Hello")
    assert c.body == "Hello"
    assert services.list_comments(db_session, ticket.id) == [c]


@pytest.mark.integration
def test_add_comment_requires_body(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="body is required"):
        services.add_comment(db_session, ticket_id=ticket.id, author_user_id=None, body="   ")


@pytest.mark.integration
def test_add_comment_size_cap(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    too_big = "x" * (TicketComment.BODY_MAX_BYTES + 1)
    with pytest.raises(ValueError, match="exceeds"):
        services.add_comment(db_session, ticket_id=ticket.id, author_user_id=None, body=too_big)


@pytest.mark.integration
def test_add_comment_unknown_ticket(db_session: Session) -> None:
    with pytest.raises(ValueError, match="ticket not found"):
        services.add_comment(db_session, ticket_id=b"\x00" * 16, author_user_id=None, body="x")


@pytest.mark.integration
def test_soft_delete_comment_hides_from_list(db_session: Session) -> None:
    c = TicketCommentFactory()
    db_session.flush()
    services.soft_delete_comment(db_session, c)
    assert services.list_comments(db_session, c.ticket_id) == []


# ── Attachments ─────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_require_attachment_bad_hex(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    with pytest.raises(ValueError):
        services.require_attachment(db_session, "not-hex", ticket)


@pytest.mark.integration
def test_require_attachment_wrong_ticket(db_session: Session) -> None:
    t1 = ServiceTicketFactory()
    t2 = ServiceTicketFactory()
    from tests.factories import TicketAttachmentFactory as _F

    a = _F(ticket=t1)
    db_session.flush()
    with pytest.raises(ValueError):
        services.require_attachment(db_session, a.id.hex(), t2)


@pytest.mark.integration
def test_add_attachment_persists_metadata(db_session: Session, tmp_path: object) -> None:
    """Add a small text attachment; happy path through store_upload."""
    from flask import current_app

    from service_crm.shared import uploads as _uploads

    current_app.config["UPLOADS_ROOT"] = str(tmp_path)
    _uploads.reset_uploads_root()
    ticket = ServiceTicketFactory()
    user = UserFactory()
    db_session.flush()
    payload = io.BytesIO(b"hello world")
    a = services.add_attachment(
        db_session,
        ticket=ticket,
        uploader_user_id=user.id,
        stream=payload,
        filename="hello.txt",
        declared_content_type="text/plain",
    )
    assert a.filename == "hello.txt"
    assert a.size_bytes == len(b"hello world")
    assert a.uploader_user_id == user.id
    current_app.config.pop("UPLOADS_ROOT", None)


@pytest.mark.integration
def test_soft_delete_attachment_requires_reason(db_session: Session) -> None:
    from tests.factories import TicketAttachmentFactory as _F

    a = _F()
    db_session.flush()
    with pytest.raises(ValueError, match="reason is required"):
        services.soft_delete_attachment(db_session, a, reason="  ")


@pytest.mark.integration
def test_soft_delete_attachment_hides_from_list(db_session: Session) -> None:
    from tests.factories import TicketAttachmentFactory as _F

    a = _F()
    db_session.flush()
    services.soft_delete_attachment(db_session, a, reason="mistake")
    assert services.list_attachments(db_session, a.ticket_id) == []


@pytest.mark.integration
def test_list_history_returns_rows(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    rows = services.list_history(db_session, ticket.id)
    assert len(rows) == 1  # the creation row


# ── Dialect-specific branches (Postgres paths exercised via monkeypatch) ─────


@pytest.mark.unit
def test_search_filter_postgres_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Postgres path returns a ``to_tsvector(...) @@ plainto_tsquery(...)``
    expression. We don't execute it — just check it compiles."""
    monkeypatch.setattr("service_crm.tickets.services._dialect", lambda: "postgresql")
    flt = services._ticket_search_filter("hello world")
    assert flt is not None
    assert "to_tsvector" in str(flt.compile(compile_kwargs={"literal_binds": True}))


@pytest.mark.unit
def test_search_filter_empty_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("service_crm.tickets.services._dialect", lambda: "sqlite")
    assert services._ticket_search_filter("   ") is None


@pytest.mark.integration
def test_next_ticket_number_postgres_path(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ``_dialect`` reports Postgres, ``_next_ticket_number`` reads
    from ``ticket_number_seq``. The sequence is owned by the migration,
    so the service layer no longer issues DDL — we fake ``nextval`` to
    exercise the branch without a real Postgres backend.
    """
    monkeypatch.setattr("service_crm.tickets.services._dialect", lambda: "postgresql")

    calls: list[str] = []

    def fake_execute(stmt, *args, **kwargs):  # type: ignore[no-untyped-def]
        text = str(stmt)
        calls.append(text)
        if "nextval" in text:

            class _R:
                def scalar_one(self) -> int:
                    return 4242

            return _R()
        raise AssertionError(f"unexpected SQL: {text}")  # pragma: no cover

    monkeypatch.setattr(db_session, "execute", fake_execute)
    n = services._next_ticket_number(db_session)
    assert n == 4242
    assert any("nextval" in c for c in calls)
    assert not any("CREATE SEQUENCE" in c for c in calls)
