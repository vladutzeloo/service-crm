"""Server-side idempotency-key dedup.

Every state-changing form rendered through the ``form_shell`` macro
carries a server-issued UUID hex token (the ``idempotency_token`` hidden
input added in 0.2.0). The server records ``(user_id, token)`` on first
submit; a retry with the same pair is rejected so a stuck user mashing
the submit button doesn't double-write.

The window is 24 h — long enough that a backgrounded mobile form that
auto-submits on resume still hits the dedup row, short enough that the
table stays small. ``flask sweep-idempotency`` (registered in
:mod:`service_crm.cli`) deletes expired rows; v0.7 will run it from
APScheduler.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..extensions import db
from . import clock, ulid

WINDOW = timedelta(hours=24)
_MAX_TOKEN_LEN = 64


class IdempotencyKey(db.Model):  # type: ignore[name-defined,misc]
    """Recorded ``(user_id, token)`` for a state-changing request."""

    __tablename__ = "idempotency_key"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    user_id: Mapped[bytes] = mapped_column(ulid.ULID, nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    route: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=clock.now
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (UniqueConstraint("user_id", "token", name="uq_idempotency_user_token"),)


def record(session: Session, *, user_id: bytes, token: str, route: str = "") -> bool:
    """Try to record ``(user_id, token)``.

    Returns ``True`` on a fresh record (request should proceed) and
    ``False`` if the pair was already recorded (request should be
    treated as a no-op duplicate).

    Empty or oversized tokens are accepted but never deduplicated —
    they're treated as "no token supplied", so the request proceeds.
    """
    token = (token or "").strip()
    if not token or len(token) > _MAX_TOKEN_LEN:
        return True
    existing = (
        session.query(IdempotencyKey)
        .filter(IdempotencyKey.user_id == user_id, IdempotencyKey.token == token)
        .one_or_none()
    )
    if existing is not None:
        return False
    now = clock.now()
    session.add(
        IdempotencyKey(
            user_id=user_id,
            token=token,
            route=route[:200],
            created_at=now,
            expires_at=now + WINDOW,
        )
    )
    session.flush()
    return True


def sweep(session: Session) -> int:
    """Delete expired rows. Returns the count removed."""
    now = clock.now()
    rows = session.query(IdempotencyKey).filter(IdempotencyKey.expires_at <= now).all()
    for row in rows:
        session.delete(row)
    session.flush()
    return len(rows)
