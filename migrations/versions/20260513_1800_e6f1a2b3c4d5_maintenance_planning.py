"""Maintenance + planning — ROADMAP 0.7.0.

Revision ID: e6f1a2b3c4d5
Revises: d5e9f1a2b3c4
Create Date: 2026-05-13 18:00:00.000000

Adds the v0.7 tables:

- ``maintenance_template`` — reusable recipe.
- ``maintenance_plan`` — per-equipment schedule.
- ``maintenance_task`` — generated due-task instance.
- ``maintenance_execution`` — completion record.
- ``technician`` — planning-side mirror of ``user_account``.
- ``technician_assignment`` — ticket / intervention assignment.
- ``technician_capacity_slot`` — per-day declared capacity.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import service_crm.shared.ulid as _ulid_mod

revision = "e6f1a2b3c4d5"
down_revision = "d5e9f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Maintenance ────────────────────────────────────────────────────────
    op.create_table(
        "maintenance_template",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("cadence_days", sa.Integer(), nullable=False, server_default="180"),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("checklist_template_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["checklist_template_id"],
            ["checklist_template.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_maintenance_template_name"),
        sa.CheckConstraint("cadence_days > 0", name="ck_maintenance_template_cadence_positive"),
    )
    with op.batch_alter_table("maintenance_template", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_maintenance_template_checklist_template_id"),
            ["checklist_template_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_maintenance_template_is_active"), ["is_active"], unique=False
        )

    op.create_table(
        "maintenance_plan",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("equipment_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("template_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("cadence_days", sa.Integer(), nullable=False),
        sa.Column("last_done_on", sa.Date(), nullable=True),
        sa.Column("next_due_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["template_id"], ["maintenance_template.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("cadence_days > 0", name="ck_maintenance_plan_cadence_positive"),
    )
    with op.batch_alter_table("maintenance_plan", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_maintenance_plan_equipment_id"), ["equipment_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_maintenance_plan_template_id"), ["template_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_maintenance_plan_next_due_on"), ["next_due_on"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_maintenance_plan_is_active"), ["is_active"], unique=False
        )

    # ── Planning: technician ──────────────────────────────────────────────
    op.create_table(
        "technician",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("user_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column(
            "timezone",
            sa.String(length=60),
            nullable=False,
            server_default="Europe/Bucharest",
        ),
        sa.Column(
            "weekly_capacity_minutes",
            sa.Integer(),
            nullable=False,
            server_default="2400",
        ),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_technician_user_id"),
        sa.CheckConstraint(
            "weekly_capacity_minutes >= 0",
            name="ck_technician_weekly_capacity_non_negative",
        ),
    )
    with op.batch_alter_table("technician", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_technician_is_active"), ["is_active"], unique=False)

    # ── Maintenance task / execution (now that technician exists for FK) ──
    op.create_table(
        "maintenance_task",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("plan_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("assigned_technician_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("ticket_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["maintenance_plan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_technician_id"], ["technician.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ticket_id"], ["service_ticket.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("maintenance_task", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_maintenance_task_plan_id"), ["plan_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_maintenance_task_due_on"), ["due_on"], unique=False)
        batch_op.create_index(batch_op.f("ix_maintenance_task_status"), ["status"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_maintenance_task_assigned_technician_id"),
            ["assigned_technician_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_maintenance_task_ticket_id"), ["ticket_id"], unique=False
        )

    op.create_table(
        "maintenance_execution",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("task_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("intervention_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["maintenance_task.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["intervention_id"], ["service_intervention.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("maintenance_execution", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_maintenance_execution_task_id"), ["task_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_maintenance_execution_intervention_id"),
            ["intervention_id"],
            unique=False,
        )

    # ── Planning: assignments + capacity slots ────────────────────────────
    op.create_table(
        "technician_assignment",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("technician_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("ticket_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("intervention_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["technician_id"], ["technician.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["service_ticket.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["intervention_id"], ["service_intervention.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "ticket_id IS NOT NULL OR intervention_id IS NOT NULL",
            name="ck_technician_assignment_target",
        ),
    )
    with op.batch_alter_table("technician_assignment", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_technician_assignment_technician_id"),
            ["technician_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_technician_assignment_ticket_id"), ["ticket_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_technician_assignment_intervention_id"),
            ["intervention_id"],
            unique=False,
        )

    op.create_table(
        "technician_capacity_slot",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("technician_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("capacity_minutes", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["technician_id"], ["technician.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("technician_id", "day", name="uq_technician_capacity_slot_day"),
        sa.CheckConstraint(
            "capacity_minutes >= 0",
            name="ck_technician_capacity_slot_non_negative",
        ),
    )
    with op.batch_alter_table("technician_capacity_slot", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_technician_capacity_slot_technician_id"),
            ["technician_id"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_technician_capacity_slot_day"), ["day"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("technician_capacity_slot", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_technician_capacity_slot_day"))
        batch_op.drop_index(batch_op.f("ix_technician_capacity_slot_technician_id"))
    op.drop_table("technician_capacity_slot")

    with op.batch_alter_table("technician_assignment", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_technician_assignment_intervention_id"))
        batch_op.drop_index(batch_op.f("ix_technician_assignment_ticket_id"))
        batch_op.drop_index(batch_op.f("ix_technician_assignment_technician_id"))
    op.drop_table("technician_assignment")

    with op.batch_alter_table("maintenance_execution", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_maintenance_execution_intervention_id"))
        batch_op.drop_index(batch_op.f("ix_maintenance_execution_task_id"))
    op.drop_table("maintenance_execution")

    with op.batch_alter_table("maintenance_task", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_maintenance_task_ticket_id"))
        batch_op.drop_index(batch_op.f("ix_maintenance_task_assigned_technician_id"))
        batch_op.drop_index(batch_op.f("ix_maintenance_task_status"))
        batch_op.drop_index(batch_op.f("ix_maintenance_task_due_on"))
        batch_op.drop_index(batch_op.f("ix_maintenance_task_plan_id"))
    op.drop_table("maintenance_task")

    with op.batch_alter_table("technician", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_technician_is_active"))
    op.drop_table("technician")

    with op.batch_alter_table("maintenance_plan", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_maintenance_plan_is_active"))
        batch_op.drop_index(batch_op.f("ix_maintenance_plan_next_due_on"))
        batch_op.drop_index(batch_op.f("ix_maintenance_plan_template_id"))
        batch_op.drop_index(batch_op.f("ix_maintenance_plan_equipment_id"))
    op.drop_table("maintenance_plan")

    with op.batch_alter_table("maintenance_template", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_maintenance_template_is_active"))
        batch_op.drop_index(batch_op.f("ix_maintenance_template_checklist_template_id"))
    op.drop_table("maintenance_template")
