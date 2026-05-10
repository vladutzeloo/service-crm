# Service-CRM — Architecture Plan

> Output of the "Architecture Only" prompt in [`tasks.md`](./tasks.md).
> **Status: awaiting approval.** No application code lands until this is signed off.

## 0. How to read this file

This is a *plan*, not an implementation. It exists to make the architecture
decisions explicit before any Flask code is written, per the rule in
[`AGENTS.md`](../AGENTS.md): *"Do not code before architecture is agreed for
new modules or large changes."*

If a section ends with **"❓ awaiting approval"**, that is the gate.

## 1. Audit summary

### 1.1 What's in the repo today

| Area | File | Status |
| --- | --- | --- |
| Always-loadable agent context | [`AGENTS.md`](../AGENTS.md) | Authoritative — keep as-is |
| UI source map | [`docs/ui-reference.md`](./ui-reference.md) | Authoritative — keep as-is |
| Service domain | [`docs/service-domain.md`](./service-domain.md) | Authoritative — keep as-is |
| Implementation sequence | [`docs/tasks.md`](./tasks.md) | Authoritative — keep as-is |
| AI memory | [`docs/obsidian-brain.md`](./obsidian-brain.md) | External-only, no app code |
| Legacy context pack | [`docs/service-app-context-pack.md`](./service-app-context-pack.md) | Superseded by AGENTS.md + the docs/ files; keep as historical reference |
| Architecture (mine) | [`ARCHITECTURE.md`](../ARCHITECTURE.md) | Realigned in this PR — was FastAPI + my own domain, now Flask + your domain |
| Roadmap (mine) | [`ROADMAP.md`](../ROADMAP.md) | Realigned in this PR around the service-domain modules |
| Test strategy (mine) | [`python.tests.md`](../python.tests.md) | Realigned in this PR to Flask test client |
| Build config (mine) | [`pyproject.toml`](../pyproject.toml) | Realigned in this PR to Flask deps |
| CI / Release | `.github/workflows/{ci,release}.yml` | Stack-agnostic — keep, may need a Flask-specific tweak in 0.1.0 |

### 1.2 oee-calculator2.0 audit

The audit referenced in [`tasks.md`](./tasks.md) step 2 needs the sibling
repo to be on disk (per [`docs/ui-reference.md`](./ui-reference.md):
`../oee-calculator2.0`) or accessible via WebFetch. From inside this repo I
can't see the actual templates yet, so the architecture below is built
*against* the patterns documented in [`docs/ui-reference.md`](./ui-reference.md)
rather than read from source.

**Action item:** before the UI Foundation slice (0.2.0 — see Roadmap), I need
either (a) the `oee-calculator2.0` repo cloned alongside, or (b) the contents
of the eleven referenced files pasted/fetched. Otherwise I'll be guessing at
class names and macros.

## 2. Assumptions

Numbered so you can shoot them down individually.

1. **Stack is non-negotiable.** Flask + Jinja + SQLAlchemy + Alembic + pytest.
   No FastAPI, no SPA, no React. (From [`AGENTS.md`](../AGENTS.md) §"Project Truth".)
2. **UI is derived, not invented.** Every screen maps to a pattern in
   [`docs/ui-reference.md`](./ui-reference.md). Light mode default, no emoji,
   no left sidebar in technician screens, compact dashboards.
3. **Standalone for v1.** No code or DB coupling to VMES/OEE. Future
   integration is API/sync-job only. (From [`AGENTS.md`](../AGENTS.md) §"Architecture Rules".)
4. **Single-tenant deployment.** One business per deployment. Multi-tenant
   is explicitly out of scope.
5. **Importable package name is `service_crm`.** Matches `pyproject.toml`
   and is consistent with the prior planning round.
6. **PowerShell is the dev shell.** [`docs/commands.md`](./commands.md)
   ("Prefer PowerShell-compatible examples for this workspace").
7. **Postgres in production, SQLite in dev/test.** Postgres-only features
   (FTS, `JSONB`) get SQLite-compatible fallbacks.
8. **Auth is server-rendered sessions.** Flask-Login + Argon2 password
   hashing. No JWT, no OAuth in v1.
9. **The five service modules in [`AGENTS.md`](../AGENTS.md) §"Architecture Rules"** —
   `clients`, `equipment`, `tickets`, `maintenance`, `knowledge` — are the
   v1 module set, even though [`docs/service-domain.md`](./service-domain.md)
   lists ten *entities*. Mapping in §4.
10. **Claude is for plan/critique, GPT-5/Codex is for implementation**, per
    [`AGENTS.md`](../AGENTS.md) §"Task Split". This plan and the project
    skills under `.claude/skills/` are Claude's lane.

❓ **Awaiting approval on assumptions 1–10.**

## 3. Proposed standalone architecture

### 3.1 Application factory

```
service_crm/__init__.py
    def create_app(config: type[Config] = ProdConfig) -> Flask:
        app = Flask(__name__)
        app.config.from_object(config)
        extensions.init_app(app)
        register_blueprints(app)
        register_cli(app)
        register_error_handlers(app)
        return app
```

Why: testability (per-test app instance), config swapping (Test/Dev/Prod),
no module-level side effects.

### 3.2 Layout (target)

The importable package is `service_crm`. Each business module is a Flask
**blueprint** that owns its own models, routes, forms, services, and the
templates that are unique to it. Cross-cutting things (base layout, design
tokens, audit log) live in `shared/`.

```
service_crm/
├── __init__.py            # create_app()
├── extensions.py          # db, login_manager, csrf, migrate
├── config.py              # Dev / Test / Prod config classes
├── cli.py                 # `flask seed`, `flask reset-db`, etc.
├── auth/                  # blueprint: User, Role
├── clients/               # blueprint: Client, Contact, Location, ServiceContract
├── equipment/             # blueprint: Equipment, EquipmentModel,
│                          #   EquipmentControllerType, EquipmentWarranty
├── tickets/               # blueprint: ServiceTicket, TicketStatusHistory,
│                          #   TicketComment, TicketAttachment, TicketPriority,
│                          #   TicketType, ServiceIntervention,
│                          #   InterventionAction, InterventionFinding,
│                          #   PartMaster, ServicePartUsage
├── maintenance/           # blueprint: MaintenancePlan, MaintenanceTask,
│                          #   MaintenanceExecution, MaintenanceTemplate
├── knowledge/             # blueprint: ChecklistTemplate, ChecklistTemplateItem,
│                          #   ChecklistRun, ChecklistRunItem,
│                          #   ProcedureDocument, ProcedureTag
├── planning/              # blueprint: Technician, TechnicianAssignment,
│                          #   TechnicianCapacitySlot, TechnicianSkill (v2)
├── dashboard/             # blueprint — operational dashboard (manager + technician)
├── shared/
│   ├── audit.py           # SQLAlchemy event-listener audit log
│   ├── ulid.py            # ULID type, stored as UUID on PG, BLOB(16) on SQLite
│   ├── money.py           # Decimal-only Money value object (if pricing lands)
│   ├── clock.py           # mockable now()
│   └── filters.py         # Jinja filters shared across templates
├── templates/
│   ├── base.html          # mirrors oee-calculator2.0/templates/base.html
│   ├── partials/
│   │   └── theme_init.html
│   ├── auth/
│   ├── clients/
│   ├── equipment/
│   ├── tickets/
│   ├── maintenance/
│   ├── knowledge/
│   └── dashboard/
└── static/
    ├── css/style.css      # mirrors oee-calculator2.0/static/css/style.css
    └── js/
migrations/                # alembic at repo root
tests/                     # mirrors service_crm/ one-for-one
```

Two layering rules that keep this honest:

1. **Routes are thin.** `routes.py` parses the request, calls a function in
   `services.py`, renders a template. No SQL, no business rules.
2. **Services own the ORM.** Cross-module access goes through the other
   module's `services.py`, never through its `models.py` directly. This
   is the seam that lets us split a blueprint into its own deployable
   later if we ever need to.

### 3.3 Cross-cutting decisions (kept from prior round)

- **Money** — `decimal.Decimal` end-to-end, persisted as `NUMERIC(12, 2)`,
  wrapped in `shared/money.py`. Reaches v1 only if pricing/invoicing lands;
  if not, defer.
- **Time** — UTC in storage, business timezone for display.
  `shared.clock.now()` is the only place that calls `datetime.now`.
- **IDs** — ULIDs at the edges, stored as native `UUID` on Postgres and
  `BLOB(16)` on SQLite. Internal FKs use the same column type.
- **Audit log** — SQLAlchemy `after_insert`/`after_update`/`after_delete`
  listeners on an `Auditable` mixin. Request context (acting user, request
  id, reason) attached via a `contextvars.ContextVar` set by middleware.
- **Search** — Postgres `tsvector` + GIN; SQLite FTS5 with the same
  tokenizer config so dev and prod behave the same.

### 3.4 What the OEE-derived UI buys us

Because we are *consuming* an existing design language (per
[`docs/ui-reference.md`](./ui-reference.md)), the UI work breaks into:

1. **Vendoring** — copy `base.html`, `partials/theme_init.html`, and the
   relevant chunks of `style.css` into `service_crm/templates/` and
   `service_crm/static/css/`. Not import, not git-submodule — *copy*, so
   the standalone constraint holds.
2. **Adapting the patterns** — `templates/admin/dashboard.html` is the
   pattern for our operational dashboard; `templates/admin/orders.html`
   is the pattern for our tickets list; `templates/operator/dashboard.html`
   is the pattern for the technician screen.
3. **Forbidden** — inventing a new design system, swapping in Bootstrap /
   Tailwind / Bulma / a component library, or using emoji icons.

❓ **Awaiting approval on: blueprints-with-internal-models layout (vs.
flat `models/` and `services/` directories).**

## 4. Proposed SQLAlchemy model set (v1)

Mapping the entities from [`docs/service-domain.md`](./service-domain.md)
(adopted in full from [`docs/blueprint.md`](./blueprint.md) §8) to
blueprints. The richer entity set is the result of the 2026-05-10
decision to "adopt blueprint's CNC domain in full".

| Blueprint     | Owns models                                                            |
| ------------- | ---------------------------------------------------------------------- |
| `auth`        | `User`, `Role`                                                         |
| `clients`     | `Client`, `Contact`, `Location`, `ServiceContract`                     |
| `equipment`   | `Equipment`, `EquipmentModel`, `EquipmentControllerType`, `EquipmentWarranty` |
| `tickets`     | `ServiceTicket`, `TicketStatusHistory`, `TicketComment`, `TicketAttachment`, `TicketPriority` (lookup), `TicketType` (lookup), `ServiceIntervention`, `InterventionAction`, `InterventionFinding`, `PartMaster`, `ServicePartUsage` |
| `maintenance` | `MaintenancePlan`, `MaintenanceTask`, `MaintenanceExecution`, `MaintenanceTemplate` |
| `knowledge`   | `ChecklistTemplate`, `ChecklistTemplateItem`, `ChecklistRun`, `ChecklistRunItem`, `ProcedureDocument`, `ProcedureTag` |
| `planning`    | `Technician`, `TechnicianAssignment`, `TechnicianCapacitySlot`, `TechnicianSkill` *(v2)* |

### 4.1 Sketch (not the final DDL — this is the shape)

```python
# service_crm/clients/models.py
class Client(db.Model, Auditable):
    id           = mapped_column(ULID, primary_key=True, default=ulid_new)
    name         = mapped_column(String(200), nullable=False, index=True)
    is_active    = mapped_column(Boolean, default=True, nullable=False)
    notes        = mapped_column(Text, default="")
    created_at   = mapped_column(DateTime(timezone=True), default=clock.now)
    contacts     = relationship("Contact", back_populates="client", cascade="all, delete-orphan")
    locations    = relationship("Location", back_populates="client", cascade="all, delete-orphan")
    equipment    = relationship("Equipment", back_populates="client")

class Contact(db.Model, Auditable):
    id        = mapped_column(ULID, primary_key=True, default=ulid_new)
    client_id = mapped_column(ForeignKey("client.id", ondelete="CASCADE"), nullable=False)
    name      = mapped_column(String(200), nullable=False)
    role      = mapped_column(String(80), default="")
    email     = mapped_column(String(200), default="")
    phone     = mapped_column(String(50),  default="")
    client    = relationship("Client", back_populates="contacts")

class Location(db.Model, Auditable):
    id        = mapped_column(ULID, primary_key=True, default=ulid_new)
    client_id = mapped_column(ForeignKey("client.id", ondelete="CASCADE"), nullable=False)
    label     = mapped_column(String(200), nullable=False)
    address   = mapped_column(Text, default="")
    client    = relationship("Client", back_populates="locations")
    equipment = relationship("Equipment", back_populates="location")

# service_crm/equipment/models.py
class Equipment(db.Model, Auditable):
    id           = mapped_column(ULID, primary_key=True, default=ulid_new)
    client_id    = mapped_column(ForeignKey("client.id"), nullable=False, index=True)
    location_id  = mapped_column(ForeignKey("location.id"), nullable=True, index=True)
    name         = mapped_column(String(200), nullable=False)
    serial       = mapped_column(String(120), unique=True, nullable=True)
    manufacturer = mapped_column(String(120), default="")
    model        = mapped_column(String(120), default="")
    installed_at = mapped_column(Date, nullable=True)
    is_active    = mapped_column(Boolean, default=True, nullable=False)
    client       = relationship("Client", back_populates="equipment")
    location     = relationship("Location", back_populates="equipment")
    tickets      = relationship("ServiceTicket", back_populates="equipment")

# service_crm/tickets/models.py
class TicketStatus(str, Enum):
    """Ticket lifecycle per docs/blueprint.md §10 / docs/service-domain.md.

    Stored values are stable English identifiers; display labels are
    translated (RO/EN) per docs/v1-implementation-goals.md §3.2.
    """
    NEW = "new"
    QUALIFIED = "qualified"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    WAITING_PARTS = "waiting_parts"
    MONITORING = "monitoring"
    COMPLETED = "completed"
    CLOSED = "closed"
    CANCELLED = "cancelled"

# Postgres uses the SEQUENCE; SQLAlchemy treats Sequence() as a no-op on
# SQLite, so on SQLite the service layer falls back to MAX(number)+1 inside
# the same transaction. Either way `number` is unique and human-friendly.
ticket_number_seq = Sequence("ticket_number_seq", start=1)

class TicketPriority(db.Model, Auditable):
    """Lookup table — per blueprint §8 ticket priorities are configurable."""
    id    = mapped_column(ULID, primary_key=True, default=ulid_new)
    code  = mapped_column(String(40), unique=True, nullable=False)  # e.g. "low"
    label = mapped_column(String(80), nullable=False)               # translated in UI

class TicketType(db.Model, Auditable):
    """Lookup — incident / preventive / commissioning / warranty / ..."""
    id    = mapped_column(ULID, primary_key=True, default=ulid_new)
    code  = mapped_column(String(40), unique=True, nullable=False)
    label = mapped_column(String(80), nullable=False)

class ServiceTicket(db.Model, Auditable):
    id            = mapped_column(ULID, primary_key=True, default=ulid_new)
    number        = mapped_column(Integer, ticket_number_seq, unique=True, nullable=False,
                                  server_default=ticket_number_seq.next_value())
    client_id     = mapped_column(ForeignKey("client.id"), nullable=False, index=True)
    location_id   = mapped_column(ForeignKey("location.id"), nullable=True)
    equipment_id  = mapped_column(ForeignKey("equipment.id"), nullable=True, index=True)
    type_id       = mapped_column(ForeignKey("ticket_type.id"), nullable=False)
    priority_id   = mapped_column(ForeignKey("ticket_priority.id"), nullable=False)
    title         = mapped_column(String(200), nullable=False)
    description   = mapped_column(Text, default="")
    status        = mapped_column(SAEnum(TicketStatus), default=TicketStatus.NEW, index=True)
    due_date      = mapped_column(Date, nullable=True, index=True)
    sla_due_at    = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at     = mapped_column(DateTime(timezone=True), default=clock.now)
    closed_at     = mapped_column(DateTime(timezone=True), nullable=True)
    interventions = relationship("ServiceIntervention", back_populates="ticket",
                                 cascade="all, delete-orphan")
    history       = relationship("TicketStatusHistory", back_populates="ticket",
                                 cascade="all, delete-orphan")
    comments      = relationship("TicketComment", back_populates="ticket",
                                 cascade="all, delete-orphan")
    attachments   = relationship("TicketAttachment", back_populates="ticket",
                                 cascade="all, delete-orphan")

class TicketStatusHistory(db.Model):
    """Append-only state-transition log. No Auditable mixin — this *is* the audit."""
    id         = mapped_column(ULID, primary_key=True, default=ulid_new)
    ticket_id  = mapped_column(ForeignKey("service_ticket.id", ondelete="CASCADE"))
    from_state = mapped_column(SAEnum(TicketStatus), nullable=True)  # NULL on create
    to_state   = mapped_column(SAEnum(TicketStatus), nullable=False)
    actor_id   = mapped_column(ForeignKey("user.id"), nullable=False)
    reason     = mapped_column(Text, default="")
    at         = mapped_column(DateTime(timezone=True), default=clock.now, index=True)
    ticket     = relationship("ServiceTicket", back_populates="history")

class TicketComment(db.Model, Auditable):
    id        = mapped_column(ULID, primary_key=True, default=ulid_new)
    ticket_id = mapped_column(ForeignKey("service_ticket.id", ondelete="CASCADE"))
    author_id = mapped_column(ForeignKey("user.id"), nullable=False)
    body      = mapped_column(Text, nullable=False)
    at        = mapped_column(DateTime(timezone=True), default=clock.now, index=True)
    ticket    = relationship("ServiceTicket", back_populates="comments")

class TicketAttachment(db.Model, Auditable):
    id           = mapped_column(ULID, primary_key=True, default=ulid_new)
    ticket_id    = mapped_column(ForeignKey("service_ticket.id", ondelete="CASCADE"))
    intervention_id = mapped_column(ForeignKey("service_intervention.id"), nullable=True)
    filename     = mapped_column(String(200), nullable=False)
    content_type = mapped_column(String(120), nullable=False)
    size_bytes   = mapped_column(Integer, nullable=False)
    storage_key  = mapped_column(String(300), nullable=False)  # path under instance/uploads/
    ticket       = relationship("ServiceTicket", back_populates="attachments")

class ServiceIntervention(db.Model, Auditable):
    id            = mapped_column(ULID, primary_key=True, default=ulid_new)
    ticket_id     = mapped_column(ForeignKey("service_ticket.id", ondelete="CASCADE"))
    technician_id = mapped_column(ForeignKey("user.id"), nullable=False)
    started_at    = mapped_column(DateTime(timezone=True))
    ended_at      = mapped_column(DateTime(timezone=True), nullable=True)
    notes         = mapped_column(Text, default="")
    ticket        = relationship("ServiceTicket", back_populates="interventions")
    actions       = relationship("InterventionAction", back_populates="intervention",
                                 cascade="all, delete-orphan")
    findings      = relationship("InterventionFinding", back_populates="intervention",
                                 cascade="all, delete-orphan")
    parts         = relationship("ServicePartUsage", back_populates="intervention",
                                 cascade="all, delete-orphan")

class InterventionAction(db.Model, Auditable):
    """A discrete action performed during an intervention (e.g. "replaced spindle bearing")."""
    id              = mapped_column(ULID, primary_key=True, default=ulid_new)
    intervention_id = mapped_column(ForeignKey("service_intervention.id", ondelete="CASCADE"))
    description     = mapped_column(Text, nullable=False)
    duration_min    = mapped_column(Integer, nullable=True)
    intervention    = relationship("ServiceIntervention", back_populates="actions")

class InterventionFinding(db.Model, Auditable):
    """An observation / diagnosis (e.g. "axis encoder showing intermittent dropout")."""
    id              = mapped_column(ULID, primary_key=True, default=ulid_new)
    intervention_id = mapped_column(ForeignKey("service_intervention.id", ondelete="CASCADE"))
    description     = mapped_column(Text, nullable=False)
    is_root_cause   = mapped_column(Boolean, default=False)
    intervention    = relationship("ServiceIntervention", back_populates="findings")

class PartMaster(db.Model, Auditable):
    """Lightweight catalog. Not a warehouse — see blueprint §2 out-of-scope."""
    id          = mapped_column(ULID, primary_key=True, default=ulid_new)
    code        = mapped_column(String(80), unique=True, nullable=False)
    description = mapped_column(String(200), nullable=False)
    is_active   = mapped_column(Boolean, default=True)

class ServicePartUsage(db.Model, Auditable):
    id              = mapped_column(ULID, primary_key=True, default=ulid_new)
    intervention_id = mapped_column(ForeignKey("service_intervention.id", ondelete="CASCADE"))
    part_id         = mapped_column(ForeignKey("part_master.id"), nullable=True)  # NULL = ad-hoc
    part_code       = mapped_column(String(80), nullable=False)  # snapshot for ad-hoc + history
    description     = mapped_column(String(200), default="")
    qty             = mapped_column(Integer, default=1)
    intervention    = relationship("ServiceIntervention", back_populates="parts")

# service_crm/equipment/models.py — additions for the CNC domain
class EquipmentModel(db.Model, Auditable):
    """Manufacturer + model lookup."""
    id           = mapped_column(ULID, primary_key=True, default=ulid_new)
    manufacturer = mapped_column(String(120), nullable=False)
    model        = mapped_column(String(120), nullable=False)
    family       = mapped_column(String(120), default="")
    __table_args__ = (UniqueConstraint("manufacturer", "model"),)

class EquipmentControllerType(db.Model, Auditable):
    """Fanuc / Siemens / Heidenhain / Haas / Mazatrol / ..."""
    id   = mapped_column(ULID, primary_key=True, default=ulid_new)
    code = mapped_column(String(60), unique=True, nullable=False)
    name = mapped_column(String(120), nullable=False)

class EquipmentWarranty(db.Model, Auditable):
    id           = mapped_column(ULID, primary_key=True, default=ulid_new)
    equipment_id = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    starts_on    = mapped_column(Date, nullable=False)
    ends_on      = mapped_column(Date, nullable=False, index=True)
    coverage     = mapped_column(Text, default="")  # free-form description

# service_crm/maintenance/models.py
class MaintenanceTemplate(db.Model, Auditable):
    """Reusable recipe (bundles a checklist + parts list + estimated time)."""
    id                    = mapped_column(ULID, primary_key=True, default=ulid_new)
    name                  = mapped_column(String(200), nullable=False)
    checklist_template_id = mapped_column(ForeignKey("checklist_template.id"), nullable=True)
    estimated_minutes     = mapped_column(Integer, nullable=True)

class MaintenancePlan(db.Model, Auditable):
    id           = mapped_column(ULID, primary_key=True, default=ulid_new)
    equipment_id = mapped_column(ForeignKey("equipment.id"), nullable=False, index=True)
    template_id  = mapped_column(ForeignKey("maintenance_template.id"), nullable=False)
    cadence_days = mapped_column(Integer, nullable=False)
    last_done_at = mapped_column(Date, nullable=True)
    next_due_at  = mapped_column(Date, nullable=True, index=True)  # recomputed by APScheduler
    is_active    = mapped_column(Boolean, default=True)

class MaintenanceTask(db.Model, Auditable):
    """A generated due-task instance from a plan."""
    id          = mapped_column(ULID, primary_key=True, default=ulid_new)
    plan_id     = mapped_column(ForeignKey("maintenance_plan.id", ondelete="CASCADE"))
    due_on      = mapped_column(Date, nullable=False, index=True)
    assigned_to = mapped_column(ForeignKey("technician.id"), nullable=True)
    ticket_id   = mapped_column(ForeignKey("service_ticket.id"), nullable=True)  # if escalated
    is_done     = mapped_column(Boolean, default=False, index=True)

class MaintenanceExecution(db.Model, Auditable):
    """Completed task with findings + parts."""
    id              = mapped_column(ULID, primary_key=True, default=ulid_new)
    task_id         = mapped_column(ForeignKey("maintenance_task.id", ondelete="CASCADE"))
    intervention_id = mapped_column(ForeignKey("service_intervention.id"), nullable=True)
    completed_at    = mapped_column(DateTime(timezone=True), default=clock.now)
    notes           = mapped_column(Text, default="")

# service_crm/knowledge/models.py
class ChecklistTemplate(db.Model, Auditable):
    id        = mapped_column(ULID, primary_key=True, default=ulid_new)
    name      = mapped_column(String(200), nullable=False)
    is_active = mapped_column(Boolean, default=True)
    items     = relationship("ChecklistTemplateItem", back_populates="template",
                             cascade="all, delete-orphan", order_by="ChecklistTemplateItem.position")

class ChecklistTemplateItem(db.Model, Auditable):
    id          = mapped_column(ULID, primary_key=True, default=ulid_new)
    template_id = mapped_column(ForeignKey("checklist_template.id", ondelete="CASCADE"))
    position    = mapped_column(Integer, nullable=False)
    key         = mapped_column(String(80), nullable=False)
    label       = mapped_column(String(200), nullable=False)
    kind        = mapped_column(String(20), nullable=False)  # bool | text | number | choice
    is_required = mapped_column(Boolean, default=True)
    template    = relationship("ChecklistTemplate", back_populates="items")

class ChecklistRun(db.Model, Auditable):
    id              = mapped_column(ULID, primary_key=True, default=ulid_new)
    template_id     = mapped_column(ForeignKey("checklist_template.id"))
    intervention_id = mapped_column(ForeignKey("service_intervention.id"), nullable=True)
    equipment_id    = mapped_column(ForeignKey("equipment.id"), nullable=True)
    snapshot        = mapped_column(JSON, nullable=False)  # frozen template at run time
    completed_at    = mapped_column(DateTime(timezone=True), nullable=True)
    items           = relationship("ChecklistRunItem", back_populates="run",
                                   cascade="all, delete-orphan")

class ChecklistRunItem(db.Model, Auditable):
    """One answered line in a run. Decoupled from the template so historical
    runs survive template edits (template_item_id stored as-was)."""
    id               = mapped_column(ULID, primary_key=True, default=ulid_new)
    run_id           = mapped_column(ForeignKey("checklist_run.id", ondelete="CASCADE"))
    template_item_id = mapped_column(ULID, nullable=False)  # not a FK — decoupled
    answer           = mapped_column(JSON, nullable=True)
    notes            = mapped_column(Text, default="")
    run              = relationship("ChecklistRun", back_populates="items")

class ProcedureTag(db.Model, Auditable):
    id   = mapped_column(ULID, primary_key=True, default=ulid_new)
    code = mapped_column(String(40), unique=True, nullable=False)
    name = mapped_column(String(120), nullable=False)

class ProcedureDocument(db.Model, Auditable):
    id      = mapped_column(ULID, primary_key=True, default=ulid_new)
    title   = mapped_column(String(200), nullable=False)
    body_md = mapped_column(Text, default="")
    tags    = relationship("ProcedureTag", secondary="procedure_document_tag")

# service_crm/planning/models.py
class Technician(db.Model, Auditable):
    """1:1 with User but separate so we can track planning attributes
    (capacity, timezone, working hours) without bloating User."""
    id        = mapped_column(ULID, primary_key=True, default=ulid_new)
    user_id   = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), unique=True)
    timezone  = mapped_column(String(60), default="Europe/Bucharest")
    is_active = mapped_column(Boolean, default=True)

class TechnicianAssignment(db.Model, Auditable):
    """Ticket / intervention assigned to a technician."""
    id              = mapped_column(ULID, primary_key=True, default=ulid_new)
    technician_id   = mapped_column(ForeignKey("technician.id", ondelete="CASCADE"), index=True)
    ticket_id       = mapped_column(ForeignKey("service_ticket.id"), nullable=True)
    intervention_id = mapped_column(ForeignKey("service_intervention.id"), nullable=True)
    assigned_at     = mapped_column(DateTime(timezone=True), default=clock.now)

class TechnicianCapacitySlot(db.Model, Auditable):
    """Declared capacity per day / shift."""
    id            = mapped_column(ULID, primary_key=True, default=ulid_new)
    technician_id = mapped_column(ForeignKey("technician.id", ondelete="CASCADE"), index=True)
    day           = mapped_column(Date, nullable=False, index=True)
    capacity_min  = mapped_column(Integer, nullable=False)  # minutes available
    __table_args__ = (UniqueConstraint("technician_id", "day"),)
```

Constraints worth calling out (these get tests in
[`python.tests.md`](../python.tests.md) §"Integration"):

- `Equipment.location_id`, when set, must point at a `Location` whose
  `client_id` matches `Equipment.client_id`. Service-layer guard +
  integration test.
- `ServiceTicket.equipment_id`, when set, must belong to
  `ServiceTicket.client_id`. Same pattern.
- `ServiceTicket.status` transitions are constrained to the lifecycle
  in [`docs/service-domain.md`](./service-domain.md) "Ticket Lifecycle".
  Pure-Python `transition()` function in `tickets/state.py`; ≥ 95 %
  line+branch coverage.
- Every `ServiceTicket.status` change writes a `TicketStatusHistory`
  row in the same transaction — enforced by a SQLAlchemy `before_flush`
  hook + an integration test that asserts no history-less transitions.
- `ChecklistRun.snapshot` and `ChecklistRunItem.template_item_id` are
  **frozen** at run-time; subsequent template edits never mutate
  historical runs. Tested with an "edit-after-snapshot" property test.
- `MaintenancePlan.next_due_at` is recomputed by the APScheduler job;
  the column has a non-null index for "due soon" queries.
- `MaintenanceTask.is_done` flips only via `MaintenanceExecution`
  insert. A standalone update on `is_done` is a service-layer error.
- `EquipmentWarranty.ends_on > EquipmentWarranty.starts_on`. CHECK
  constraint + integration test.
- Soft-delete: `Client.is_active = False`, `Equipment.is_active = False`,
  `Technician.is_active = False`, `PartMaster.is_active = False`,
  `MaintenancePlan.is_active = False`. Hard delete is reserved for
  the GDPR forget endpoint (per
  [`docs/v1-implementation-goals.md`](./v1-implementation-goals.md) §1.8).
- Lookup tables (`TicketType`, `TicketPriority`,
  `EquipmentControllerType`, `ProcedureTag`) store stable English
  `code` values and `label` strings. UI translates labels via
  Flask-Babel; codes never touch the user.

❓ **Awaiting approval on: the entity↔blueprint mapping in §4 and the
constraint list above.**

## 5. Files to create vs. adapt

### 5.1 Already in this PR (planning artifacts only — no app code yet)

- `docs/architecture-plan.md` *(this file)*
- `docs/commands.md` — placeholders replaced with concrete Flask commands.
- `ARCHITECTURE.md` — realigned to Flask + the service domain.
- `ROADMAP.md` — realigned around the five blueprints, sequenced per [`tasks.md`](./tasks.md).
- `python.tests.md` — realigned to Flask test client + pytest + factory-boy.
- `pyproject.toml` — Flask deps, dev-tool config, hatchling build.
- `README.md` — pointer index to AGENTS.md and the docs/.
- `.claude/skills/` — five project-level skills mirroring the workflows in [`tasks.md`](./tasks.md).

### 5.2 To create after approval (in order — see [`ROADMAP.md`](../ROADMAP.md))

| Step | Milestone | Artifact                                                                                            |
| ---- | --------- | --------------------------------------------------------------------------------------------------- |
| 1    | 0.1.0     | `service_crm/__init__.py`, `extensions.py`, `config.py`, `cli.py`; auth (`User`, `Role`); Flask-Babel + RO/EN catalogs scaffold |
| 2    | 0.2.0     | `service_crm/templates/base.html`, `static/css/style.css`, manifest, service worker (vendored OEE)  |
| 3    | 0.3.0     | `service_crm/clients/` — `Client`/`Contact`/`Location`/`ServiceContract` + CRUD + tests             |
| 4    | 0.4.0     | `service_crm/equipment/` — `Equipment`/`EquipmentModel`/`EquipmentControllerType`/`EquipmentWarranty` |
| 5    | 0.5.0     | `service_crm/tickets/` — full ticket + status history + comments + attachments + state machine      |
| 6    | 0.6.0     | `service_crm/tickets/` — interventions + actions + findings + part usage; `service_crm/knowledge/` checklists + procedures |
| 7    | 0.7.0     | `service_crm/maintenance/` — plans / tasks / executions / templates + APScheduler `next_due_at` recompute |
| 8    | 0.7.0     | `service_crm/planning/` — technicians + assignments + capacity slots                                |
| 9    | 0.8.0     | `service_crm/dashboard/` — manager + technician views, KPI panels per `docs/service-domain.md` "Dashboard V1" |

Each step lands as its own PR with a roadmap milestone.

## 6. Open questions / approval gate

- ❓ Are assumptions 1–10 in §2 correct?
- ❓ Blueprint-internal models (proposed) vs. flat `service_crm/models/` (alternative)?
- ❓ Module mapping in §4 — is `maintenance` correctly its own blueprint, or
      does it belong inside `equipment`?
- ❓ Is the `Auditable` mixin acceptable, or would you rather we audit only
      explicit service calls?
- ❓ Should the `dashboard` blueprint own the technician/operator screen
      *and* the manager/admin screen, or do they need separate blueprints
      (matches the `templates/admin/` vs `templates/operator/` split in OEE)?
- ❓ Once approved, who runs the implementation — me, GPT-5/Codex per
      [`AGENTS.md`](../AGENTS.md) §"Task Split", or a mix?

When these are answered I'll cut the first implementation PR (the app
factory + extensions, no business code), targeting `v0.1.0` per
[`ROADMAP.md`](../ROADMAP.md).
