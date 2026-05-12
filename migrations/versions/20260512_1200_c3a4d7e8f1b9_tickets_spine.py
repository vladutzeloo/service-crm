"""Tickets-domain tables.

Revision ID: c3a4d7e8f1b9
Revises: b9c8d2e7a4f6
Create Date: 2026-05-12 12:00:00.000000

Adds the v0.5 ticket workflow tables:

- ``ticket_type`` — lookup (``incident``, ``preventive``, …).
- ``ticket_priority`` — lookup (``low``, ``normal``, ``high``, ``urgent``).
- ``service_ticket`` — the ticket header, FKs to client + equipment +
  type + priority + assignee.
- ``ticket_status_history`` — append-only audit of status changes.
- ``ticket_comment`` — free-text comment (plain text, 8 KB cap).
- ``ticket_attachment`` — metadata for an upload on disk.
- ``idempotency_key`` — shared, server-side dedup of state-changing
  form submissions.

Seeds ``ticket_type`` and ``ticket_priority`` with the v1 codes.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import service_crm.shared.ulid as _ulid_mod

revision = "c3a4d7e8f1b9"
down_revision = "b9c8d2e7a4f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticket_type",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_ticket_type_code"),
    )
    with op.batch_alter_table("ticket_type", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ticket_type_is_active"), ["is_active"], unique=False)

    op.create_table(
        "ticket_priority",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_ticket_priority_code"),
    )
    with op.batch_alter_table("ticket_priority", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_ticket_priority_is_active"), ["is_active"], unique=False
        )

    op.create_table(
        "service_ticket",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("client_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("equipment_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("type_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("priority_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("assignee_user_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="new"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["client.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["type_id"], ["ticket_type.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["priority_id"], ["ticket_priority.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["user_account.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("service_ticket", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_service_ticket_number"), ["number"], unique=True)
        batch_op.create_index(
            batch_op.f("ix_service_ticket_client_id"), ["client_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_service_ticket_equipment_id"), ["equipment_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_service_ticket_type_id"), ["type_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_service_ticket_priority_id"), ["priority_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_service_ticket_assignee_user_id"),
            ["assignee_user_id"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_service_ticket_status"), ["status"], unique=False)

    op.create_table(
        "ticket_status_history",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("ticket_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("from_state", sa.String(length=40), nullable=True),
        sa.Column("to_state", sa.String(length=40), nullable=False),
        sa.Column("actor_user_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("reason_code", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["service_ticket.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user_account.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ticket_status_history", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_ticket_status_history_ticket_id"), ["ticket_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_ticket_status_history_actor_user_id"),
            ["actor_user_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_ticket_status_history_occurred_at"),
            ["occurred_at"],
            unique=False,
        )

    op.create_table(
        "ticket_comment",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("ticket_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("author_user_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["service_ticket.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["user_account.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ticket_comment", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_ticket_comment_ticket_id"), ["ticket_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_ticket_comment_author_user_id"),
            ["author_user_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_ticket_comment_is_active"), ["is_active"], unique=False
        )

    op.create_table(
        "ticket_attachment",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("ticket_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("uploader_user_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("filename", sa.String(length=200), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_key", sa.String(length=400), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["service_ticket.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploader_user_id"], ["user_account.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ticket_attachment", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_ticket_attachment_ticket_id"), ["ticket_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_ticket_attachment_uploader_user_id"),
            ["uploader_user_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_ticket_attachment_is_active"), ["is_active"], unique=False
        )

    op.create_table(
        "idempotency_key",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("user_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("route", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "token", name="uq_idempotency_user_token"),
    )
    with op.batch_alter_table("idempotency_key", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_idempotency_key_user_id"), ["user_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_idempotency_key_expires_at"), ["expires_at"], unique=False
        )

    # Postgres-only: GIN expression-index on title + description for the
    # tickets list search box, plus the sequence that feeds
    # ``ServiceTicket.number``. SQLite uses ``MAX(number) + 1`` instead
    # (see ``service_crm.tickets.services._next_ticket_number``).
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(
            """
            CREATE INDEX ix_service_ticket_search_vector ON service_ticket
            USING GIN (
                to_tsvector('simple',
                    coalesce(title, '') || ' ' ||
                    coalesce(description, ''))
            )
            """
        )
        op.execute("CREATE SEQUENCE IF NOT EXISTS ticket_number_seq START 1")

    # Seed ticket_type and ticket_priority lookups. ULIDs generated in
    # Python and bound via the parameter API so the bytes payload is
    # dialect-agnostic.
    from service_crm.shared import clock as _clock
    from service_crm.shared import ulid as _ulid

    now = _clock.now()
    types_seed = [
        ("incident", "Incident", True),
        ("preventive", "Preventive", False),
        ("commissioning", "Commissioning", False),
        ("warranty", "Warranty", False),
        ("installation", "Installation", False),
        ("audit", "Audit", False),
    ]
    type_table = sa.table(
        "ticket_type",
        sa.column("id", _ulid_mod.ULID(length=16)),
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("is_default", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        type_table,
        [
            {
                "id": _ulid.new(),
                "code": code,
                "label": label,
                "is_active": True,
                "is_default": is_default,
                "created_at": now,
                "updated_at": now,
            }
            for (code, label, is_default) in types_seed
        ],
    )

    prio_seed = [
        ("low", "Low", 10, False),
        ("normal", "Normal", 20, True),
        ("high", "High", 30, False),
        ("urgent", "Urgent", 40, False),
    ]
    prio_table = sa.table(
        "ticket_priority",
        sa.column("id", _ulid_mod.ULID(length=16)),
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("rank", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("is_default", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        prio_table,
        [
            {
                "id": _ulid.new(),
                "code": code,
                "label": label,
                "rank": rank,
                "is_active": True,
                "is_default": is_default,
                "created_at": now,
                "updated_at": now,
            }
            for (code, label, rank, is_default) in prio_seed
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_service_ticket_search_vector")
        op.execute("DROP SEQUENCE IF EXISTS ticket_number_seq")

    with op.batch_alter_table("idempotency_key", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_idempotency_key_expires_at"))
        batch_op.drop_index(batch_op.f("ix_idempotency_key_user_id"))
    op.drop_table("idempotency_key")

    with op.batch_alter_table("ticket_attachment", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ticket_attachment_is_active"))
        batch_op.drop_index(batch_op.f("ix_ticket_attachment_uploader_user_id"))
        batch_op.drop_index(batch_op.f("ix_ticket_attachment_ticket_id"))
    op.drop_table("ticket_attachment")

    with op.batch_alter_table("ticket_comment", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ticket_comment_is_active"))
        batch_op.drop_index(batch_op.f("ix_ticket_comment_author_user_id"))
        batch_op.drop_index(batch_op.f("ix_ticket_comment_ticket_id"))
    op.drop_table("ticket_comment")

    with op.batch_alter_table("ticket_status_history", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ticket_status_history_occurred_at"))
        batch_op.drop_index(batch_op.f("ix_ticket_status_history_actor_user_id"))
        batch_op.drop_index(batch_op.f("ix_ticket_status_history_ticket_id"))
    op.drop_table("ticket_status_history")

    with op.batch_alter_table("service_ticket", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_service_ticket_status"))
        batch_op.drop_index(batch_op.f("ix_service_ticket_assignee_user_id"))
        batch_op.drop_index(batch_op.f("ix_service_ticket_priority_id"))
        batch_op.drop_index(batch_op.f("ix_service_ticket_type_id"))
        batch_op.drop_index(batch_op.f("ix_service_ticket_equipment_id"))
        batch_op.drop_index(batch_op.f("ix_service_ticket_client_id"))
        batch_op.drop_index(batch_op.f("ix_service_ticket_number"))
    op.drop_table("service_ticket")

    with op.batch_alter_table("ticket_priority", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ticket_priority_is_active"))
    op.drop_table("ticket_priority")

    with op.batch_alter_table("ticket_type", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ticket_type_is_active"))
    op.drop_table("ticket_type")
