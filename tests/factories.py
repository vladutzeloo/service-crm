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
from service_crm.knowledge.models import (
    ChecklistRun,
    ChecklistRunItem,
    ChecklistTemplate,
    ChecklistTemplateItem,
    ProcedureDocument,
    ProcedureTag,
)
from service_crm.tickets.intervention_models import (
    InterventionAction,
    InterventionFinding,
    PartMaster,
    ServiceIntervention,
    ServicePartUsage,
)
from service_crm.tickets.models import (
    ServiceTicket,
    TicketAttachment,
    TicketComment,
    TicketPriority,
    TicketType,
)
from service_crm.tickets.state import TicketStatus


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


# ── Tickets ───────────────────────────────────────────────────────────────────


class TicketTypeFactory(SQLAlchemyModelFactory):
    class Meta:
        model = TicketType
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    code = factory.Sequence(lambda n: f"type-{n}")
    label = factory.Sequence(lambda n: f"Type {n}")
    is_active = True
    is_default = False


class TicketPriorityFactory(SQLAlchemyModelFactory):
    class Meta:
        model = TicketPriority
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    code = factory.Sequence(lambda n: f"prio-{n}")
    label = factory.Sequence(lambda n: f"Priority {n}")
    rank = factory.Sequence(lambda n: n)
    is_active = True
    is_default = False


class ServiceTicketFactory(SQLAlchemyModelFactory):
    class Meta:
        model = ServiceTicket
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    client = factory.SubFactory(ClientFactory)
    equipment = None
    type = None
    priority = None
    assignee = None
    number = factory.Sequence(lambda n: n + 1)
    title = factory.Sequence(lambda n: f"Ticket {n}")
    description = ""
    status = TicketStatus.NEW.value
    due_at = None
    sla_due_at = None
    scheduled_at = None
    closed_at = None

    @factory.lazy_attribute
    def client_id(self) -> bytes:
        return self.client.id  # type: ignore[return-value]

    @factory.lazy_attribute
    def equipment_id(self) -> bytes | None:
        return self.equipment.id if self.equipment else None  # type: ignore[return-value]

    @factory.lazy_attribute
    def type_id(self) -> bytes | None:
        return self.type.id if self.type else None  # type: ignore[return-value]

    @factory.lazy_attribute
    def priority_id(self) -> bytes | None:
        return self.priority.id if self.priority else None  # type: ignore[return-value]

    @factory.lazy_attribute
    def assignee_user_id(self) -> bytes | None:
        return self.assignee.id if self.assignee else None  # type: ignore[return-value]


class TicketCommentFactory(SQLAlchemyModelFactory):
    class Meta:
        model = TicketComment
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    ticket = factory.SubFactory(ServiceTicketFactory)
    author = None
    body = factory.Sequence(lambda n: f"Comment body {n}")
    is_active = True

    @factory.lazy_attribute
    def ticket_id(self) -> bytes:
        return self.ticket.id  # type: ignore[return-value]

    @factory.lazy_attribute
    def author_user_id(self) -> bytes | None:
        return self.author.id if self.author else None  # type: ignore[return-value]


class TicketAttachmentFactory(SQLAlchemyModelFactory):
    class Meta:
        model = TicketAttachment
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    ticket = factory.SubFactory(ServiceTicketFactory)
    uploader = None
    filename = factory.Sequence(lambda n: f"file-{n}.txt")
    content_type = "text/plain"
    size_bytes = 42
    storage_key = factory.Sequence(lambda n: f"tickets/dummy/{n:08x}.txt")
    is_active = True

    @factory.lazy_attribute
    def ticket_id(self) -> bytes:
        return self.ticket.id  # type: ignore[return-value]

    @factory.lazy_attribute
    def uploader_user_id(self) -> bytes | None:
        return self.uploader.id if self.uploader else None  # type: ignore[return-value]


# ── Interventions / parts ─────────────────────────────────────────────────────


class ServiceInterventionFactory(SQLAlchemyModelFactory):
    class Meta:
        model = ServiceIntervention
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    ticket = factory.SubFactory(ServiceTicketFactory)
    technician = None
    # An hour in the past so ``stop_intervention(clock.now())`` is never
    # rejected for ``ended_at < started_at`` on hosts where wall-clock
    # time differs from the test's frozen fixture.
    started_at = factory.LazyFunction(
        lambda: (
            __import__("service_crm.shared.clock", fromlist=["now"]).now()
            - __import__("datetime").timedelta(hours=1)
        )
    )
    ended_at = None
    summary = ""

    @factory.lazy_attribute
    def ticket_id(self) -> bytes:
        return self.ticket.id  # type: ignore[return-value]

    @factory.lazy_attribute
    def technician_user_id(self) -> bytes | None:
        return self.technician.id if self.technician else None  # type: ignore[return-value]


class InterventionActionFactory(SQLAlchemyModelFactory):
    class Meta:
        model = InterventionAction
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    intervention = factory.SubFactory(ServiceInterventionFactory)
    description = factory.Sequence(lambda n: f"Action {n}")
    duration_minutes = None

    @factory.lazy_attribute
    def intervention_id(self) -> bytes:
        return self.intervention.id  # type: ignore[return-value]


class InterventionFindingFactory(SQLAlchemyModelFactory):
    class Meta:
        model = InterventionFinding
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    intervention = factory.SubFactory(ServiceInterventionFactory)
    description = factory.Sequence(lambda n: f"Finding {n}")
    is_root_cause = False

    @factory.lazy_attribute
    def intervention_id(self) -> bytes:
        return self.intervention.id  # type: ignore[return-value]


class PartMasterFactory(SQLAlchemyModelFactory):
    class Meta:
        model = PartMaster
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    code = factory.Sequence(lambda n: f"PART-{n:04d}")
    description = factory.Sequence(lambda n: f"Part {n}")
    unit = "pcs"
    notes = ""
    is_active = True


class ServicePartUsageFactory(SQLAlchemyModelFactory):
    class Meta:
        model = ServicePartUsage
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    intervention = factory.SubFactory(ServiceInterventionFactory)
    part = None
    part_code = factory.Sequence(lambda n: f"PART-{n:04d}")
    description = ""
    quantity = 1
    unit = "pcs"

    @factory.lazy_attribute
    def intervention_id(self) -> bytes:
        return self.intervention.id  # type: ignore[return-value]

    @factory.lazy_attribute
    def part_id(self) -> bytes | None:
        return self.part.id if self.part else None  # type: ignore[return-value]


# ── Knowledge ─────────────────────────────────────────────────────────────────


class ChecklistTemplateFactory(SQLAlchemyModelFactory):
    class Meta:
        model = ChecklistTemplate
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    name = factory.Sequence(lambda n: f"Checklist {n}")
    description = ""
    is_active = True


class ChecklistTemplateItemFactory(SQLAlchemyModelFactory):
    class Meta:
        model = ChecklistTemplateItem
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    template = factory.SubFactory(ChecklistTemplateFactory)
    position = factory.Sequence(lambda n: n)
    key = factory.Sequence(lambda n: f"item_{n}")
    label = factory.Sequence(lambda n: f"Item {n}")
    kind = "bool"
    is_required = True
    choice_options = None

    @factory.lazy_attribute
    def template_id(self) -> bytes:
        return self.template.id  # type: ignore[return-value]


class ChecklistRunFactory(SQLAlchemyModelFactory):
    class Meta:
        model = ChecklistRun
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    template = factory.SubFactory(ChecklistTemplateFactory)
    intervention = None
    snapshot = factory.LazyAttribute(
        lambda o: {"template_id": o.template.id.hex(), "name": o.template.name, "items": []}
    )
    completed_at = None

    @factory.lazy_attribute
    def template_id(self) -> bytes:
        return self.template.id  # type: ignore[return-value]

    @factory.lazy_attribute
    def intervention_id(self) -> bytes | None:
        return self.intervention.id if self.intervention else None  # type: ignore[return-value]


class ChecklistRunItemFactory(SQLAlchemyModelFactory):
    class Meta:
        model = ChecklistRunItem
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    run = factory.SubFactory(ChecklistRunFactory)
    template_item_id = factory.LazyFunction(
        lambda: __import__("service_crm.shared.ulid", fromlist=["new"]).new()
    )
    position = factory.Sequence(lambda n: n)
    key = factory.Sequence(lambda n: f"item_{n}")
    label = factory.Sequence(lambda n: f"Item {n}")
    kind = "bool"
    is_required = True
    answer = None
    notes = ""

    @factory.lazy_attribute
    def run_id(self) -> bytes:
        return self.run.id  # type: ignore[return-value]


class ProcedureTagFactory(SQLAlchemyModelFactory):
    class Meta:
        model = ProcedureTag
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    code = factory.Sequence(lambda n: f"tag-{n}")
    name = factory.Sequence(lambda n: f"Tag {n}")
    is_active = True


class ProcedureDocumentFactory(SQLAlchemyModelFactory):
    class Meta:
        model = ProcedureDocument
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    title = factory.Sequence(lambda n: f"Procedure {n}")
    summary = ""
    body = ""
    is_active = True
