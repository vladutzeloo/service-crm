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
├── auth/                  # blueprint
│   ├── __init__.py        # bp = Blueprint(...)
│   ├── models.py          # User, Role
│   ├── routes.py          # login/logout/profile
│   ├── forms.py           # WTForms
│   └── services.py        # password hashing, session helpers
├── clients/               # blueprint — Client, Contact, Location
├── equipment/             # blueprint — Equipment / installed base
├── tickets/               # blueprint — ServiceTicket, ServiceIntervention, ServicePartUsage
├── maintenance/           # blueprint — maintenance plans + due/overdue surfacing
├── knowledge/             # blueprint — ChecklistTemplate, ChecklistRun, ProcedureDocument
├── dashboard/             # blueprint — operational dashboard (no left sidebar version)
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

Mapping the ten entities from [`docs/service-domain.md`](./service-domain.md)
to the five blueprints from [`AGENTS.md`](../AGENTS.md):

| Blueprint     | Owns models                                                            |
| ------------- | ---------------------------------------------------------------------- |
| `auth`        | `User`, `Role`                                                         |
| `clients`     | `Client`, `Contact`, `Location`                                        |
| `equipment`   | `Equipment`                                                            |
| `tickets`     | `ServiceTicket`, `ServiceIntervention`, `ServicePartUsage`             |
| `maintenance` | `MaintenancePlan`, `MaintenanceDueItem` *(derived view, not a table)*  |
| `knowledge`   | `ChecklistTemplate`, `ChecklistRun`, `ProcedureDocument`               |

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
    OPEN = "open"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    AWAITING_PARTS = "awaiting_parts"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"

class TicketPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

# Postgres uses the SEQUENCE; SQLAlchemy treats Sequence() as a no-op on
# SQLite, so on SQLite the service layer falls back to MAX(number)+1 inside
# the same transaction. Either way `number` is unique and human-friendly.
ticket_number_seq = Sequence("ticket_number_seq", start=1)

class ServiceTicket(db.Model, Auditable):
    id           = mapped_column(ULID, primary_key=True, default=ulid_new)
    number       = mapped_column(Integer, ticket_number_seq, unique=True, nullable=False,
                                 server_default=ticket_number_seq.next_value())
    client_id    = mapped_column(ForeignKey("client.id"), nullable=False, index=True)
    location_id  = mapped_column(ForeignKey("location.id"), nullable=True)
    equipment_id = mapped_column(ForeignKey("equipment.id"), nullable=True)
    title        = mapped_column(String(200), nullable=False)
    description  = mapped_column(Text, default="")
    status       = mapped_column(SAEnum(TicketStatus), default=TicketStatus.OPEN, index=True)
    priority     = mapped_column(SAEnum(TicketPriority), default=TicketPriority.NORMAL)
    due_date     = mapped_column(Date, nullable=True)
    opened_at    = mapped_column(DateTime(timezone=True), default=clock.now)
    closed_at    = mapped_column(DateTime(timezone=True), nullable=True)
    interventions = relationship("ServiceIntervention", back_populates="ticket", cascade="all, delete-orphan")

class ServiceIntervention(db.Model, Auditable):
    id            = mapped_column(ULID, primary_key=True, default=ulid_new)
    ticket_id     = mapped_column(ForeignKey("service_ticket.id", ondelete="CASCADE"))
    technician_id = mapped_column(ForeignKey("user.id"), nullable=False)
    started_at    = mapped_column(DateTime(timezone=True))
    ended_at      = mapped_column(DateTime(timezone=True), nullable=True)
    notes         = mapped_column(Text, default="")
    ticket        = relationship("ServiceTicket", back_populates="interventions")
    parts         = relationship("ServicePartUsage", back_populates="intervention", cascade="all, delete-orphan")

class ServicePartUsage(db.Model, Auditable):
    id              = mapped_column(ULID, primary_key=True, default=ulid_new)
    intervention_id = mapped_column(ForeignKey("service_intervention.id", ondelete="CASCADE"))
    part_code       = mapped_column(String(80), nullable=False)
    description     = mapped_column(String(200), default="")
    qty             = mapped_column(Integer, default=1)
    intervention    = relationship("ServiceIntervention", back_populates="parts")

# service_crm/maintenance/models.py
class MaintenancePlan(db.Model, Auditable):
    id              = mapped_column(ULID, primary_key=True, default=ulid_new)
    equipment_id    = mapped_column(ForeignKey("equipment.id"), nullable=False, index=True)
    cadence_days    = mapped_column(Integer, nullable=False)  # e.g. every 90 days
    last_done_at    = mapped_column(Date, nullable=True)
    next_due_at     = mapped_column(Date, nullable=True, index=True)  # computed; index for "due soon"
    checklist_template_id = mapped_column(ForeignKey("checklist_template.id"), nullable=True)

# service_crm/knowledge/models.py
class ChecklistTemplate(db.Model, Auditable):
    id    = mapped_column(ULID, primary_key=True, default=ulid_new)
    name  = mapped_column(String(200), nullable=False)
    items = mapped_column(JSON, default=list)        # [{key, label, kind: 'bool'|'text'|'number'}]

class ChecklistRun(db.Model, Auditable):
    id              = mapped_column(ULID, primary_key=True, default=ulid_new)
    template_id     = mapped_column(ForeignKey("checklist_template.id"))
    intervention_id = mapped_column(ForeignKey("service_intervention.id"), nullable=True)
    equipment_id    = mapped_column(ForeignKey("equipment.id"), nullable=True)
    snapshot        = mapped_column(JSON, nullable=False)  # frozen template at run time
    answers         = mapped_column(JSON, default=dict)
    completed_at    = mapped_column(DateTime(timezone=True), nullable=True)

class ProcedureDocument(db.Model, Auditable):
    id      = mapped_column(ULID, primary_key=True, default=ulid_new)
    title   = mapped_column(String(200), nullable=False)
    body_md = mapped_column(Text, default="")
    tags    = mapped_column(JSON, default=list)
```

Constraints worth calling out (these get tests in
[`python.tests.md`](../python.tests.md) §"Integration"):

- `Equipment.location_id`, when set, must point at a `Location` whose
  `client_id` matches `Equipment.client_id`. Enforced via service layer
  + a CHECK-style integration test.
- `ServiceTicket.equipment_id`, when set, must belong to
  `ServiceTicket.client_id`. Same pattern.
- `ChecklistRun.snapshot` is **frozen** at run-time; subsequent template
  edits never mutate historical runs.
- Soft-delete: `Client.is_active = False` rather than DELETE; financial /
  service history must remain queryable. (Same pattern as my prior round.)

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

| Step | Artifact                                                                    |
| ---- | --------------------------------------------------------------------------- |
| 1    | `service_crm/__init__.py`, `extensions.py`, `config.py`, `cli.py`           |
| 2    | `service_crm/templates/base.html`, `static/css/style.css` (vendored OEE)    |
| 3    | `service_crm/auth/` — User/Role + login/logout + tests                      |
| 4    | `service_crm/clients/` — Client/Contact/Location + CRUD + tests             |
| 5    | `service_crm/equipment/` — Equipment + CRUD + tests                         |
| 6    | `service_crm/tickets/` — Tickets + interventions + parts + status flow      |
| 7    | `service_crm/maintenance/` — plans + due/overdue surfacing                  |
| 8    | `service_crm/knowledge/` — checklists + procedures                          |
| 9    | `service_crm/dashboard/` — operational dashboard tying it together          |

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
