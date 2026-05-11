"""Client-domain tables: client, contact, location, service_contract.

Revision ID: 8f3a2c1d4e5b
Revises: 40b50949771c
Create Date: 2026-05-11 13:00:00.000000

On Postgres a GIN index is added on an inline ``to_tsvector`` expression
covering ``client.name``, ``client.email``, and ``client.phone`` so that
the full-text search in ``clients/services.py`` is performant. SQLite
uses LIKE (adequate for dev/test). FTS5 virtual tables can be added
post-0.3.0 if SQLite search performance becomes a concern.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import service_crm.shared.ulid as _ulid_mod

revision = "8f3a2c1d4e5b"
down_revision = "40b50949771c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("client", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_client_is_active"), ["is_active"], unique=False)
        batch_op.create_index(batch_op.f("ix_client_name"), ["name"], unique=False)

    op.create_table(
        "contact",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("client_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["client.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("contact", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_contact_client_id"), ["client_id"], unique=False)

    op.create_table(
        "location",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("client_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("address", sa.Text(), nullable=False, server_default=""),
        sa.Column("city", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("country", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["client.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("location", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_location_client_id"), ["client_id"], unique=False)

    op.create_table(
        "service_contract",
        sa.Column("id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("client_id", _ulid_mod.ULID(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("reference", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "ends_on IS NULL OR ends_on > starts_on",
            name="ck_service_contract_dates",
        ),
        sa.ForeignKeyConstraint(["client_id"], ["client.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("service_contract", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_service_contract_client_id"), ["client_id"], unique=False
        )

    # Postgres-only: GIN index on tsvector expression for client full-text search.
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(
            """
            CREATE INDEX ix_client_search_vector ON client
            USING GIN (
                to_tsvector('simple',
                    coalesce(name, '') || ' ' ||
                    coalesce(email, '') || ' ' ||
                    coalesce(phone, ''))
            )
            """
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_client_search_vector")

    with op.batch_alter_table("service_contract", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_service_contract_client_id"))
    op.drop_table("service_contract")

    with op.batch_alter_table("location", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_location_client_id"))
    op.drop_table("location")

    with op.batch_alter_table("contact", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_contact_client_id"))
    op.drop_table("contact")

    with op.batch_alter_table("client", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_client_name"))
        batch_op.drop_index(batch_op.f("ix_client_is_active"))
    op.drop_table("client")
