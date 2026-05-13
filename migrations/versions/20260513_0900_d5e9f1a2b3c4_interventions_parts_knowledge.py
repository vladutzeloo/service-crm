"""Interventions, parts, and knowledge.

Revision ID: d5e9f1a2b3c4
Revises: c3a4d7e8f1b9
Create Date: 2026-05-13 09:00:00.000000

Adds the v0.6 tables:

- ``service_intervention`` — field-job session header.
- ``intervention_action`` — discrete actions per intervention.
- ``intervention_finding`` — observations / diagnoses per intervention.
- ``part_master`` — lightweight catalog of replaceable parts.
- ``service_part_usage`` — per-intervention part draws.
- ``checklist_template`` + ``checklist_template_item`` — admin recipes.
- ``checklist_run`` + ``checklist_run_item`` — frozen snapshots per
  intervention.
- ``procedure_document`` + ``procedure_tag`` + ``procedure_document_tag``
  — searchable Markdown documents with M2M tags.

Also adds the ``intervention_id`` FK column to ``ticket_attachment`` —
the v0.5 plan deferred this to v0.6 so the FK target table exists.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import service_crm.shared.ulid as _ulid_mod

revision = "d5e9f1a2b3c4"
down_revision = "c3a4d7e8f1b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Interventions / parts ──────────────────────────────────────────────
    op.create_table(
        "service_intervention",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("ticket_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("technician_user_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["service_ticket.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["technician_user_id"], ["user_account.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("service_intervention", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_service_intervention_ticket_id"), ["ticket_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_service_intervention_technician_user_id"),
            ["technician_user_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_service_intervention_started_at"), ["started_at"], unique=False
        )

    op.create_table(
        "intervention_action",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("intervention_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["intervention_id"], ["service_intervention.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("intervention_action", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_intervention_action_intervention_id"),
            ["intervention_id"],
            unique=False,
        )

    op.create_table(
        "intervention_finding",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("intervention_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_root_cause", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["intervention_id"], ["service_intervention.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("intervention_finding", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_intervention_finding_intervention_id"),
            ["intervention_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_intervention_finding_is_root_cause"),
            ["is_root_cause"],
            unique=False,
        )

    op.create_table(
        "part_master",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default="pcs"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_part_master_code"),
    )
    with op.batch_alter_table("part_master", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_part_master_is_active"), ["is_active"], unique=False)

    op.create_table(
        "service_part_usage",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("intervention_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("part_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("part_code", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default="pcs"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["intervention_id"], ["service_intervention.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["part_id"], ["part_master.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("service_part_usage", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_service_part_usage_intervention_id"),
            ["intervention_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_service_part_usage_part_id"), ["part_id"], unique=False
        )

    # Add the placeholder column from v0.5 plan §5.3.
    with op.batch_alter_table("ticket_attachment", schema=None) as batch_op:
        batch_op.add_column(sa.Column("intervention_id", _ulid_mod.ULID(length=16), nullable=True))
        batch_op.create_foreign_key(
            "fk_ticket_attachment_intervention_id",
            "service_intervention",
            ["intervention_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            batch_op.f("ix_ticket_attachment_intervention_id"),
            ["intervention_id"],
            unique=False,
        )

    # ── Knowledge: checklists ──────────────────────────────────────────────
    op.create_table(
        "checklist_template",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_checklist_template_name"),
    )
    with op.batch_alter_table("checklist_template", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_checklist_template_is_active"), ["is_active"], unique=False
        )

    op.create_table(
        "checklist_template_item",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("template_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="bool"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("choice_options", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["checklist_template.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "key", name="uq_checklist_template_item_key"),
    )
    with op.batch_alter_table("checklist_template_item", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_checklist_template_item_template_id"),
            ["template_id"],
            unique=False,
        )

    op.create_table(
        "checklist_run",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("template_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("intervention_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["checklist_template.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["intervention_id"], ["service_intervention.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("checklist_run", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_checklist_run_template_id"), ["template_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_checklist_run_intervention_id"),
            ["intervention_id"],
            unique=False,
        )

    op.create_table(
        "checklist_run_item",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("run_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("template_item_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="bool"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("answer", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["checklist_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("checklist_run_item", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_checklist_run_item_run_id"), ["run_id"], unique=False)

    # ── Knowledge: procedures ─────────────────────────────────────────────
    op.create_table(
        "procedure_tag",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_procedure_tag_code"),
    )
    with op.batch_alter_table("procedure_tag", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_procedure_tag_is_active"), ["is_active"], unique=False)

    op.create_table(
        "procedure_document",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.String(length=400), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("procedure_document", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_procedure_document_is_active"), ["is_active"], unique=False
        )

    op.create_table(
        "procedure_document_tag",
        sa.Column("procedure_document_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("procedure_tag_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["procedure_document_id"], ["procedure_document.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["procedure_tag_id"], ["procedure_tag.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("procedure_document_id", "procedure_tag_id"),
    )

    # Postgres-only: GIN expression-indices for procedure search and
    # part-master code search.
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(
            """
            CREATE INDEX ix_procedure_document_search_vector ON procedure_document
            USING GIN (
                to_tsvector('simple',
                    coalesce(title, '') || ' ' ||
                    coalesce(summary, '') || ' ' ||
                    coalesce(body, ''))
            )
            """
        )
        op.execute(
            """
            CREATE INDEX ix_part_master_search_vector ON part_master
            USING GIN (
                to_tsvector('simple',
                    coalesce(code, '') || ' ' || coalesce(description, ''))
            )
            """
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_procedure_document_search_vector")
        op.execute("DROP INDEX IF EXISTS ix_part_master_search_vector")

    op.drop_table("procedure_document_tag")

    with op.batch_alter_table("procedure_document", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_procedure_document_is_active"))
    op.drop_table("procedure_document")

    with op.batch_alter_table("procedure_tag", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_procedure_tag_is_active"))
    op.drop_table("procedure_tag")

    with op.batch_alter_table("checklist_run_item", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_checklist_run_item_run_id"))
    op.drop_table("checklist_run_item")

    with op.batch_alter_table("checklist_run", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_checklist_run_intervention_id"))
        batch_op.drop_index(batch_op.f("ix_checklist_run_template_id"))
    op.drop_table("checklist_run")

    with op.batch_alter_table("checklist_template_item", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_checklist_template_item_template_id"))
    op.drop_table("checklist_template_item")

    with op.batch_alter_table("checklist_template", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_checklist_template_is_active"))
    op.drop_table("checklist_template")

    with op.batch_alter_table("ticket_attachment", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ticket_attachment_intervention_id"))
        batch_op.drop_constraint("fk_ticket_attachment_intervention_id", type_="foreignkey")
        batch_op.drop_column("intervention_id")

    with op.batch_alter_table("service_part_usage", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_service_part_usage_part_id"))
        batch_op.drop_index(batch_op.f("ix_service_part_usage_intervention_id"))
    op.drop_table("service_part_usage")

    with op.batch_alter_table("part_master", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_part_master_is_active"))
    op.drop_table("part_master")

    with op.batch_alter_table("intervention_finding", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_intervention_finding_is_root_cause"))
        batch_op.drop_index(batch_op.f("ix_intervention_finding_intervention_id"))
    op.drop_table("intervention_finding")

    with op.batch_alter_table("intervention_action", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_intervention_action_intervention_id"))
    op.drop_table("intervention_action")

    with op.batch_alter_table("service_intervention", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_service_intervention_started_at"))
        batch_op.drop_index(batch_op.f("ix_service_intervention_technician_user_id"))
        batch_op.drop_index(batch_op.f("ix_service_intervention_ticket_id"))
    op.drop_table("service_intervention")
