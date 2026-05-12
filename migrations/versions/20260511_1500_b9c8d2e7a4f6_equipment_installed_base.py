"""Equipment-domain tables.

Revision ID: b9c8d2e7a4f6
Revises: 8f3a2c1d4e5b
Create Date: 2026-05-11 15:00:00.000000

Adds the installed-base entities for ROADMAP 0.4.0:

- ``equipment_controller_type`` — lookup (Fanuc, Siemens, …).
- ``equipment_model`` — manufacturer + model code lookup, FK to
  controller type.
- ``equipment`` — installed machine, FKs to client, location, model,
  controller type.
- ``equipment_warranty`` — warranty record per machine, CHECK
  constraint ``ends_on > starts_on``.

Indexes are added on every FK column plus the searchable text columns
(``serial_number`` and ``asset_tag`` on ``equipment``). The Postgres
GIN expression-index for full-text search across equipment is added at
the bottom, mirroring the pattern used for ``client`` in the previous
migration.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import service_crm.shared.ulid as _ulid_mod

revision = "b9c8d2e7a4f6"
down_revision = "8f3a2c1d4e5b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "equipment_controller_type",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_equipment_controller_type_code"),
    )

    op.create_table(
        "equipment_model",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("manufacturer", sa.String(length=120), nullable=False),
        sa.Column("model_code", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("controller_type_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["controller_type_id"],
            ["equipment_controller_type.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manufacturer", "model_code", name="uq_equipment_model_manuf_code"),
    )
    with op.batch_alter_table("equipment_model", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_equipment_model_controller_type_id"),
            ["controller_type_id"],
            unique=False,
        )

    op.create_table(
        "equipment",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("client_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("location_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("equipment_model_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("controller_type_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("serial_number", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("asset_tag", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("install_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["client.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["location.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["equipment_model_id"], ["equipment_model.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["controller_type_id"],
            ["equipment_controller_type.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("equipment", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_equipment_client_id"), ["client_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_equipment_location_id"), ["location_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_equipment_equipment_model_id"),
            ["equipment_model_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_equipment_controller_type_id"),
            ["controller_type_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_equipment_serial_number"), ["serial_number"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_equipment_asset_tag"), ["asset_tag"], unique=False)
        batch_op.create_index(batch_op.f("ix_equipment_is_active"), ["is_active"], unique=False)

    op.create_table(
        "equipment_warranty",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("equipment_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("reference", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("provider", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ends_on > starts_on", name="ck_equipment_warranty_dates"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("equipment_warranty", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_equipment_warranty_equipment_id"),
            ["equipment_id"],
            unique=False,
        )

    # Postgres-only: GIN index on tsvector expression for equipment search.
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(
            """
            CREATE INDEX ix_equipment_search_vector ON equipment
            USING GIN (
                to_tsvector('simple',
                    coalesce(serial_number, '') || ' ' ||
                    coalesce(asset_tag, ''))
            )
            """
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_equipment_search_vector")

    with op.batch_alter_table("equipment_warranty", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_equipment_warranty_equipment_id"))
    op.drop_table("equipment_warranty")

    with op.batch_alter_table("equipment", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_equipment_is_active"))
        batch_op.drop_index(batch_op.f("ix_equipment_asset_tag"))
        batch_op.drop_index(batch_op.f("ix_equipment_serial_number"))
        batch_op.drop_index(batch_op.f("ix_equipment_controller_type_id"))
        batch_op.drop_index(batch_op.f("ix_equipment_equipment_model_id"))
        batch_op.drop_index(batch_op.f("ix_equipment_location_id"))
        batch_op.drop_index(batch_op.f("ix_equipment_client_id"))
    op.drop_table("equipment")

    with op.batch_alter_table("equipment_model", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_equipment_model_controller_type_id"))
    op.drop_table("equipment_model")

    op.drop_table("equipment_controller_type")
