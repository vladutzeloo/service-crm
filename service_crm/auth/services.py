"""Service layer for auth.

Only the password and email-normalisation helpers in this PR; login,
logout and session management land with ``/module-slice auth``.

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
