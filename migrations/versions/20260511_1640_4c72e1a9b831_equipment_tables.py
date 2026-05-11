"""Equipment-domain tables.

Tables: equipment_model, equipment_controller_type, equipment, equipment_warranty.

Revision ID: 4c72e1a9b831
Revises: 8f3a2c1d4e5b
Create Date: 2026-05-11 16:40:00.000000

Seeds EquipmentControllerType with the most common CNC controller families.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import service_crm.shared.ulid as _ulid_mod

revision = "4c72e1a9b831"
down_revision = "8f3a2c1d4e5b"
branch_labels = None
depends_on = None

# Default controller type seeds — stable English codes, localised labels in the UI.
_CONTROLLER_SEEDS = [
    ("fanuc", "Fanuc"),
    ("siemens", "Siemens Sinumerik"),
    ("heidenhain", "Heidenhain"),
    ("haas", "Haas"),
    ("mazatrol", "Mazatrol"),
    ("mitsubishi", "Mitsubishi M70/M80"),
    ("num", "NUM"),
    ("other", "Other"),
]


def upgrade() -> None:
    op.create_table(
        "equipment_model",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("manufacturer", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("family", sa.String(length=120), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manufacturer", "model", name="uq_equipment_model"),
    )

    op.create_table(
        "equipment_controller_type",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_equipment_controller_type_code"),
    )
    with op.batch_alter_table("equipment_controller_type", schema=None) as batch_op:
        batch_op.create_index("ix_equipment_controller_type_code", ["code"], unique=True)

    # Seed default controller types.
    conn = op.get_bind()
    for code, name in _CONTROLLER_SEEDS:
        uid = _ulid_mod.new()
        uid_val = uid.hex() if conn.dialect.name == "postgresql" else uid
        conn.execute(
            sa.text(
                "INSERT INTO equipment_controller_type (id, code, name) VALUES (:id, :code, :name)"
            ),
            {"id": uid_val, "code": code, "name": name},
        )

    op.create_table(
        "equipment",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("client_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("location_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("equipment_model_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("controller_type_id", _ulid_mod.ULID(length=16), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("serial", sa.String(length=120), nullable=True),
        sa.Column("manufacturer", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("installed_at", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
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
        sa.UniqueConstraint("serial", name="uq_equipment_serial"),
    )
    with op.batch_alter_table("equipment", schema=None) as batch_op:
        batch_op.create_index("ix_equipment_client_id", ["client_id"], unique=False)
        batch_op.create_index("ix_equipment_is_active", ["is_active"], unique=False)
        batch_op.create_index("ix_equipment_location_id", ["location_id"], unique=False)
        batch_op.create_index(
            "ix_equipment_equipment_model_id", ["equipment_model_id"], unique=False
        )
        batch_op.create_index(
            "ix_equipment_controller_type_id", ["controller_type_id"], unique=False
        )

    op.create_table(
        "equipment_warranty",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("equipment_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("coverage", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ends_on > starts_on", name="ck_equipment_warranty_dates"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("equipment_warranty", schema=None) as batch_op:
        batch_op.create_index("ix_equipment_warranty_equipment_id", ["equipment_id"], unique=False)
        batch_op.create_index("ix_equipment_warranty_ends_on", ["ends_on"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("equipment_warranty", schema=None) as batch_op:
        batch_op.drop_index("ix_equipment_warranty_ends_on")
        batch_op.drop_index("ix_equipment_warranty_equipment_id")
    op.drop_table("equipment_warranty")

    with op.batch_alter_table("equipment", schema=None) as batch_op:
        batch_op.drop_index("ix_equipment_controller_type_id")
        batch_op.drop_index("ix_equipment_equipment_model_id")
        batch_op.drop_index("ix_equipment_location_id")
        batch_op.drop_index("ix_equipment_is_active")
        batch_op.drop_index("ix_equipment_client_id")
    op.drop_table("equipment")

    with op.batch_alter_table("equipment_controller_type", schema=None) as batch_op:
        batch_op.drop_index("ix_equipment_controller_type_code")
    op.drop_table("equipment_controller_type")

    op.drop_table("equipment_model")
