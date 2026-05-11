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
from service_crm.clients.models import Client, Contact, Location, ServiceContract
from service_crm.equipment.models import (
    Equipment,
    EquipmentControllerType,
    EquipmentModel,
    EquipmentWarranty,
)
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


# ── Clients ───────────────────────────────────────────────────────────────────


class ClientFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Client
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    name = factory.Sequence(lambda n: f"Client {n}")
    email = factory.Sequence(lambda n: f"client{n}@example.com")
    phone = ""
    notes = ""
    is_active = True


class ContactFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Contact
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    client = factory.SubFactory(ClientFactory)
    name = factory.Sequence(lambda n: f"Contact {n}")
    role = ""
    email = factory.Sequence(lambda n: f"contact{n}@example.com")
    phone = ""
    is_primary = False

    @factory.lazy_attribute
    def client_id(self) -> bytes:
        return self.client.id  # type: ignore[return-value]


class LocationFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Location
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    client = factory.SubFactory(ClientFactory)
    label = factory.Sequence(lambda n: f"Location {n}")
    address = ""
    city = ""
    country = ""

    @factory.lazy_attribute
    def client_id(self) -> bytes:
        return self.client.id  # type: ignore[return-value]


class ContractFactory(SQLAlchemyModelFactory):
    class Meta:
        model = ServiceContract
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    client = factory.SubFactory(ClientFactory)
    title = factory.Sequence(lambda n: f"Contract {n}")
    reference = ""
    starts_on = factory.LazyFunction(lambda: __import__("datetime").date(2026, 1, 1))
    ends_on = None
    is_active = True
    notes = ""

    @factory.lazy_attribute
    def client_id(self) -> bytes:
        return self.client.id  # type: ignore[return-value]


# ── Equipment ─────────────────────────────────────────────────────────────────


class ControllerTypeFactory(SQLAlchemyModelFactory):
    class Meta:
        model = EquipmentControllerType
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    code = factory.Sequence(lambda n: f"CTRL-{n}")
    name = factory.Sequence(lambda n: f"Controller {n}")
    notes = ""


class EquipmentModelFactory(SQLAlchemyModelFactory):
    class Meta:
        model = EquipmentModel
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    manufacturer = factory.Sequence(lambda n: f"Manuf {n}")
    model_code = factory.Sequence(lambda n: f"MX-{n}")
    display_name = ""
    controller_type_id = None
    notes = ""


class EquipmentFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Equipment
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    client = factory.SubFactory(ClientFactory)
    location = None
    equipment_model = None
    controller_type = None
    serial_number = factory.Sequence(lambda n: f"SN-{n:06d}")
    asset_tag = factory.Sequence(lambda n: f"AT-{n:04d}")
    install_date = None
    notes = ""
    is_active = True

    @factory.lazy_attribute
    def client_id(self) -> bytes:
        return self.client.id  # type: ignore[return-value]

    @factory.lazy_attribute
    def location_id(self) -> bytes | None:
        return self.location.id if self.location else None  # type: ignore[return-value]

    @factory.lazy_attribute
    def equipment_model_id(self) -> bytes | None:
        return self.equipment_model.id if self.equipment_model else None  # type: ignore[return-value]

    @factory.lazy_attribute
    def controller_type_id(self) -> bytes | None:
        return self.controller_type.id if self.controller_type else None  # type: ignore[return-value]


class EquipmentWarrantyFactory(SQLAlchemyModelFactory):
    class Meta:
        model = EquipmentWarranty
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    equipment = factory.SubFactory(EquipmentFactory)
    reference = factory.Sequence(lambda n: f"W-{n}")
    provider = ""
    starts_on = factory.LazyFunction(lambda: __import__("datetime").date(2026, 1, 1))
    ends_on = factory.LazyFunction(lambda: __import__("datetime").date(2027, 1, 1))
    notes = ""

    @factory.lazy_attribute
    def equipment_id(self) -> bytes:
        return self.equipment.id  # type: ignore[return-value]
