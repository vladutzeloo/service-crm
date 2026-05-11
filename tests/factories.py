"""``factory-boy`` builders for test entities.

Use these everywhere a test needs a row. The factory makes intent
obvious at the call site (``UserFactory(is_active=False)`` reads like
English) and keeps the email-lowercasing rule out of every test.

Conventions:
- Factories use the ``alchemy`` strategy bound to ``db.session`` via
  ``conftest.py``'s ``_attach_factory_session`` fixture.
- ``UserFactory`` defaults to the ``technician`` role; bump to ``admin``
  or ``manager`` explicitly when needed.
- ``UserFactory`` defaults to the password ``"test-pass"`` so test
  helpers can log a user in without juggling password fixtures.
"""

from __future__ import annotations

import factory
from factory.alchemy import SQLAlchemyModelFactory

from service_crm.auth import services as auth_services
from service_crm.auth.models import Role, User
from service_crm.extensions import db


class RoleFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Role
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    name = factory.Sequence(lambda n: f"role-{n}")
    description = ""


# Argon2 is intentionally expensive (~100 ms per hash); UserFactory would
# pay that cost for every row otherwise. We hash the default password
# once at import time and reuse it. Tests that need a non-default
# password set ``password=...`` and pay the cost only for those rows.
_DEFAULT_PASSWORD = "test-pass"  # placeholder, not a real secret
_DEFAULT_PASSWORD_HASH = auth_services.hash_password(_DEFAULT_PASSWORD)


class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    email = factory.Sequence(lambda n: f"user-{n}@example.com")
    is_active = True
    preferred_language = None
    last_login_at = None

    # Class-level marker; the post-generation hook below converts it to a
    # password_hash. Tests that don't care just default to "test-pass".
    password = _DEFAULT_PASSWORD

    @factory.lazy_attribute
    def role(self) -> Role:
        # Bind to the seeded ``technician`` role by default.
        seeded = db.session.query(Role).filter_by(name="technician").one_or_none()
        if seeded is not None:
            return seeded
        # Fall back to creating one (for tests that downgrade + re-upgrade
        # the schema, dropping the seed in the process).
        return RoleFactory(name="technician")

    @factory.lazy_attribute
    def password_hash(self) -> str:
        # Reuse the pre-computed hash for the default; only pay Argon2's
        # cost when a test asks for a different password.
        if self.password == _DEFAULT_PASSWORD:
            return _DEFAULT_PASSWORD_HASH
        return auth_services.hash_password(self.password)

    @classmethod
    def _create(cls, model_class: type, *args: object, **kwargs: object) -> User:
        # Drop the cleartext ``password`` field — it isn't a model column.
        kwargs.pop("password", None)
        kwargs["email"] = auth_services.normalize_email(str(kwargs.get("email", "")))
        return super()._create(model_class, *args, **kwargs)  # type: ignore[no-any-return]
