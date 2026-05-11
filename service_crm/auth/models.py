"""Auth models — ``User`` and ``Role``.

Per the approved architecture plan §4: both inherit ``Auditable`` so
create/update/delete events land in ``audit_event`` automatically.

The email column is unique case-insensitively. We persist the
already-lowercased form (service layer normalises on write) and back it
with a functional unique index on ``lower(email)`` so the DB enforces
the same invariant on both Postgres and SQLite.
"""

from __future__ import annotations

from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from ..shared import ulid
from ..shared.audit import Auditable


class Role(db.Model, Auditable):  # type: ignore[name-defined,misc]
    __tablename__ = "role"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    users: Mapped[list[User]] = relationship(
        "User",
        back_populates="role",
        passive_deletes="all",  # ON DELETE RESTRICT on the FK; mirror here.
    )

    def __repr__(self) -> str:
        return f"<Role {self.name!r}>"


class User(db.Model, Auditable, UserMixin):  # type: ignore[name-defined,misc]
    __tablename__ = "user_account"  # ``user`` is reserved in Postgres.

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    # No ``index=True`` here: ``ix_user_account_email_lower`` in
    # ``__table_args__`` already serves exact-match lookups (lower() of a
    # lowercase string is the value itself) and enforces uniqueness.
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    role_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("role.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    preferred_language: Mapped[str | None] = mapped_column(String(5), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    role: Mapped[Role] = relationship("Role", back_populates="users")

    __table_args__ = (
        # DB-level case-insensitive uniqueness. Works on Postgres and SQLite.
        Index("ix_user_account_email_lower", text("lower(email)"), unique=True),
    )

    def get_id(self) -> str:
        """Flask-Login expects a string identifier; hex-encode the ULID."""
        return self.id.hex()

    def __repr__(self) -> str:
        return f"<User {self.email!r}>"
