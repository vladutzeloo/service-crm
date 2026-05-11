"""Initial schema: ``user_account``, ``role``, ``audit_event``; seeds the
three default roles (admin, manager, technician).

Revision ID: 40b50949771c
Revises:
Create Date: 2026-05-11 06:28:20.585243
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import service_crm.shared.ulid as _ulid_mod
from service_crm.shared import clock, ulid

# revision identifiers, used by Alembic.
revision = "40b50949771c"
down_revision = None
branch_labels = None
depends_on = None


_ROLE_SEED = [
    ("admin", "Full administrative access to every module."),
    ("manager", "Operational oversight: tickets, planning, dashboards."),
    ("technician", "Field execution: assigned tickets, interventions, checklists."),
]


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "action",
            sa.Enum("create", "update", "delete", name="audit_action"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("actor_user_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("audit_event", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_audit_event_entity_type"), ["entity_type"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_audit_event_ts"), ["ts"], unique=False)

    op.create_table(
        "role",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "user_account",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("role_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("preferred_language", sa.String(length=5), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("user_account", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_user_account_email"), ["email"], unique=False)
        batch_op.create_index(batch_op.f("ix_user_account_role_id"), ["role_id"], unique=False)
        # Functional case-insensitive unique index. Autogenerate skips
        # expression-based indexes (SQLite reflection limitation), so we
        # add it explicitly here. Works on Postgres and SQLite.
        batch_op.create_index(
            "ix_user_account_email_lower",
            [sa.text("lower(email)")],
            unique=True,
        )

    # Seed the three default roles. IDs are generated at migration time
    # so each fresh install gets its own; tests and services look roles
    # up by ``name`` (which has its own UNIQUE constraint), never by id.
    now = clock.now()
    op.bulk_insert(
        sa.table(
            "role",
            sa.column("id", _ulid_mod.ULID(length=16)),
            sa.column("name", sa.String()),
            sa.column("description", sa.String()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": ulid.new(),
                "name": name,
                "description": description,
                "created_at": now,
                "updated_at": now,
            }
            for (name, description) in _ROLE_SEED
        ],
    )


def downgrade() -> None:
    with op.batch_alter_table("user_account", schema=None) as batch_op:
        batch_op.drop_index("ix_user_account_email_lower")
        batch_op.drop_index(batch_op.f("ix_user_account_role_id"))
        batch_op.drop_index(batch_op.f("ix_user_account_email"))

    op.drop_table("user_account")
    op.drop_table("role")

    with op.batch_alter_table("audit_event", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_audit_event_ts"))
        batch_op.drop_index(batch_op.f("ix_audit_event_entity_type"))

    op.drop_table("audit_event")
