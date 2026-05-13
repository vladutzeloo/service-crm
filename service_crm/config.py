"""Flask config classes.

Plain ``object`` subclasses, read by :func:`flask.Config.from_object`.
We deliberately avoid pydantic-settings: Flask config is one-shot and
the typed-validation surface isn't worth the dep. Reach for ``os.environ``
through the helpers below.

Environment variables consumed (all optional except ``SECRET_KEY`` in
:class:`ProdConfig`):

- ``DATABASE_URL`` — SQLAlchemy URL. Defaults to a SQLite file under
  ``instance/`` for dev, an in-memory SQLite for tests.
- ``SECRET_KEY`` — Flask session signing key. Required in prod.
- ``WTF_CSRF_TIME_LIMIT`` — seconds before a CSRF token expires.
"""

from __future__ import annotations

import os
from pathlib import Path

_INSTANCE_DIR = Path(__file__).resolve().parent.parent / "instance"


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw)


class BaseConfig:
    """Defaults shared by every environment."""

    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL", f"sqlite:///{_INSTANCE_DIR / 'dev.sqlite3'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ECHO: bool = _bool("SQLALCHEMY_ECHO", False)

    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-do-not-use-in-prod")

    WTF_CSRF_ENABLED: bool = True
    WTF_CSRF_TIME_LIMIT: int = _int("WTF_CSRF_TIME_LIMIT", 3600)

    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    # Auditable mixin reads this; see service_crm/shared/audit.py.
    AUDIT_LOG_ENABLED: bool = True

    # i18n. Catalogs under ``locale/<code>/LC_MESSAGES/messages.po``.
    BABEL_DEFAULT_LOCALE: str = "ro"
    BABEL_DEFAULT_TIMEZONE: str = "Europe/Bucharest"
    BABEL_TRANSLATION_DIRECTORIES: str = "locale"

    # APScheduler — gated so tests / dev don't spin up a background
    # thread by default. ``ProdConfig`` flips :data:`SCHEDULER_ENABLED`
    # on. Intervals are configurable per ``docs/v0.7-plan.md`` §3.3.
    SCHEDULER_ENABLED: bool = _bool("SCHEDULER_ENABLED", False)
    SCHEDULER_MAINTENANCE_INTERVAL_MIN: int = _int("SCHEDULER_MAINTENANCE_INTERVAL_MIN", 60)
    SCHEDULER_IDEMPOTENCY_INTERVAL_H: int = _int("SCHEDULER_IDEMPOTENCY_INTERVAL_H", 6)


class DevConfig(BaseConfig):
    DEBUG: bool = True
    TESTING: bool = False


class TestConfig(BaseConfig):
    DEBUG: bool = False
    TESTING: bool = True
    # In-memory SQLite by default; override via DATABASE_URL for the
    # Postgres leg of the dual-DB CI matrix.
    SQLALCHEMY_DATABASE_URI: str = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    WTF_CSRF_ENABLED: bool = False
    SECRET_KEY: str = "test-secret"
    SCHEDULER_ENABLED: bool = False


class ProdConfig(BaseConfig):
    DEBUG: bool = False
    TESTING: bool = False
    SESSION_COOKIE_SECURE: bool = True
    SCHEDULER_ENABLED: bool = _bool("SCHEDULER_ENABLED", True)

    @classmethod
    def validate(cls) -> None:
        """Fail-fast on missing required env vars."""
        if cls.SECRET_KEY == BaseConfig.SECRET_KEY:
            raise RuntimeError("SECRET_KEY must be set in production.")
