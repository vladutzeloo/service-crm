"""Service layer for auth.

Password helpers (Argon2id), email normalisation, user lookups,
and the post-login bookkeeping (``last_login_at``).

Why Argon2id with the library defaults:
- OWASP-recommended; rejects the GPU brute-force surface that bcrypt is
  starting to show.
- ``argon2-cffi`` ships sane defaults (memory_cost=64 MiB, time_cost=3,
  parallelism=4 in the current release) and bundles its own format
  string, so we never store a salt explicitly.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..shared import clock
from .models import User

_hasher = PasswordHasher()


def hash_password(plaintext: str) -> str:
    """Hash a plaintext password with Argon2id. Returns the encoded form."""
    return _hasher.hash(plaintext)


def verify_password(plaintext: str, encoded: str) -> bool:
    """Constant-time verify of *plaintext* against an Argon2 ``encoded`` hash.

    Returns ``False`` on mismatch. Any other failure (malformed hash,
    different algorithm) re-raises so the caller learns about it.
    """
    try:
        return _hasher.verify(encoded, plaintext)
    except VerifyMismatchError:
        return False


def normalize_email(email: str) -> str:
    """Lower-case + strip. Mirrors the functional unique index in the DB."""
    return email.strip().lower()


def get_user_by_email(session: Session, email: str) -> User | None:
    """Look up a user by email, case-insensitively.

    The functional ``ix_user_account_email_lower`` index makes this
    O(log n) on both Postgres and SQLite. Returns ``None`` when no row
    matches; callers handle the unauthenticated path.
    """
    needle = normalize_email(email)
    if not needle:
        return None
    return session.query(User).filter(func.lower(User.email) == needle).one_or_none()


def record_login(session: Session, user: User) -> None:
    """Stamp ``last_login_at`` on a freshly-authenticated user.

    Caller is responsible for the surrounding transaction; this only
    writes a single column.
    """
    user.last_login_at = clock.now()
    session.flush()
