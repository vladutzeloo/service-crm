# Service-CRM — Architecture

> Status: **planning, Flask edition.** Realigned to match the user-supplied
> direction in [`AGENTS.md`](./AGENTS.md), [`docs/service-domain.md`](./docs/service-domain.md),
> [`docs/ui-reference.md`](./docs/ui-reference.md) and [`docs/tasks.md`](./docs/tasks.md).
>
> This document describes *what* we are building and *how the layers fit*.
> The roadmap of *when* each piece ships is in [`ROADMAP.md`](./ROADMAP.md).
> The currently-pending architectural proposal (assumptions, model set,
> approval gate) is in [`docs/architecture-plan.md`](./docs/architecture-plan.md).

## 1. Product summary

Service-CRM is a **standalone, self-hostable Flask app for service teams** —
client management, equipment registry, service tickets and interventions,
checklists/SOPs, and operational dashboards. It is opinionated and narrow on
purpose; explicit non-goals are in [`AGENTS.md`](./AGENTS.md).

The design language is reused verbatim from
[`vladutzeloo/oee-calculator2.0`](https://github.com/vladutzeloo/oee-calculator2.0).
We **do not** import business logic from that repo — only its UI patterns,
templates, and CSS tokens (mapping in [`docs/ui-reference.md`](./docs/ui-reference.md)).

## 2. Primary users & jobs-to-be-done

| User           | Top jobs                                                                  |
| -------------- | ------------------------------------------------------------------------- |
| Front-desk     | Register a client + equipment, open a ticket, schedule an intervention    |
| Technician     | See queued tickets, log an intervention, fill a checklist, mark complete  |
| Manager / Owner| Operational dashboard: open tickets, today's interventions, due maintenance |
| Future         | Customer/portal access, VMES/OEE integration via API/sync (post-v1)       |

## 3. Stack

| Layer         | Choice                                  | Why                                                        |
| ------------- | --------------------------------------- | ---------------------------------------------------------- |
| Language      | Python 3.11+                            | Project standard                                           |
| Web framework | Flask                                   | Mandated by AGENTS.md; confirmed in [ADR-0001](./docs/adr/0001-flask-vs-fastapi.md) |
| Templating    | Jinja2 (server-rendered)                | Mandated; matches oee-calculator2.0                        |
| ORM           | SQLAlchemy 2.x + Flask-SQLAlchemy       | Mandated                                                   |
| Migrations    | Alembic (via Flask-Migrate)             | Mandated; reviewable + reversible                          |
| Forms         | Flask-WTF + WTForms                     | CSRF + validation in one place                             |
| Auth          | Flask-Login + Argon2 (`argon2-cffi`)    | Server-rendered sessions, single-tenant                    |
| i18n          | Flask-Babel + Babel                     | RO + EN from day one; `{% trans %}` in Jinja, `gettext_lazy` in WTForms |
| DB (prod)     | PostgreSQL 15+                          | Money + audit + FTS                                        |
| DB (dev/test) | SQLite                                  | Zero-setup, runs in CI                                     |
| Background    | APScheduler (later: RQ + Redis)         | Start in-process; graduate when justified                  |
| Testing       | pytest + pytest-cov + factory-boy + Hypothesis | See [`python.tests.md`](./python.tests.md)          |
| Lint / Type   | ruff + mypy                             | Cheap, fast feedback                                       |
| Packaging     | `pyproject.toml` (PEP 621), Docker      | One install path for hackers, one for operators            |
| Shell         | PowerShell-friendly                     | [`docs/commands.md`](./docs/commands.md)                   |

The deliberate constraint is **"runs from a single container against a single
Postgres"**. Anything that breaks that constraint needs an explicit roadmap
entry.

## 4. Application architecture

### 4.1 App factory + blueprints

```python
# service_crm/__init__.py
def create_app(config: type[Config] = ProdConfig) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)
    extensions.init_app(app)        # db, migrate, login_manager, csrf
    register_blueprints(app)        # auth, clients, equipment, tickets, ...
    register_cli(app)               # flask seed, flask reset-db, ...
    register_error_handlers(app)
    return app
```

Why a factory: per-test app instance, swappable config, no module-level side
effects. Every test in [`python.tests.md`](./python.tests.md) starts from
`create_app(TestConfig)`.

### 4.2 Layout

```
service_crm/                 # importable package
├── __init__.py              # create_app() factory + register_*() helpers
├── extensions.py            # db, migrate, login_manager, csrf, babel  (all .init_app())
├── config.py                # Dev / Test / Prod config classes (12-factor)
├── cli.py                   # Flask CLI commands
├── auth/                    # blueprint: User, Role, login/logout
├── clients/                 # blueprint: Client, Contact, Location, ServiceContract
├── equipment/               # blueprint: Equipment, EquipmentModel,
│                            #   EquipmentControllerType, EquipmentWarranty
├── tickets/                 # blueprint: ServiceTicket, TicketStatusHistory,
│                            #   TicketComment, TicketAttachment, TicketType,
│                            #   TicketPriority, ServiceIntervention,
│                            #   InterventionAction, InterventionFinding,
│                            #   PartMaster, ServicePartUsage; state.py state machine
├── maintenance/             # blueprint: MaintenancePlan, MaintenanceTask,
│                            #   MaintenanceExecution, MaintenanceTemplate
├── knowledge/               # blueprint: ChecklistTemplate, ChecklistTemplateItem,
│                            #   ChecklistRun, ChecklistRunItem,
│                            #   ProcedureDocument, ProcedureTag
├── planning/                # blueprint: Technician, TechnicianAssignment,
│                            #   TechnicianCapacitySlot, TechnicianSkill (v2)
├── dashboard/               # blueprint: operational dashboard (admin + operator)
├── shared/                  # cross-cutting (audit, ulid, money, clock, filters, i18n helpers)
├── templates/               # Jinja, mirrors oee-calculator2.0 layout
│   ├── base.html
│   ├── partials/
│   ├── _macros/
│   └── auth/  clients/  equipment/  tickets/  maintenance/
│        knowledge/  planning/  dashboard/
└── static/
    ├── css/style.css        # vendored from oee-calculator2.0 + project additions
    ├── manifest.webmanifest
    ├── service-worker.js
    ├── icons/
    └── js/
locale/                      # gettext catalogs at repo root
├── ro/LC_MESSAGES/messages.po
└── en/LC_MESSAGES/messages.po
migrations/                  # alembic, lives at repo root
tests/                       # mirrors service_crm/ one-for-one
babel.cfg                    # extraction config
```

Each blueprint owns its own `models.py`, `routes.py`, `forms.py`, and
`services.py`. Templates live centrally under `service_crm/templates/<bp>/`
because Jinja inheritance from `base.html` is easier when all templates
share a single search path — the same pattern oee-calculator2.0 uses.

### 4.3 Layering rules

Two rules that keep the layers honest:

1. **Routes are thin.** A `routes.py` view parses the request, calls a
   function in the blueprint's `services.py`, and renders a template. No
   SQL, no business rules.
2. **Services own the ORM.** Cross-blueprint access goes through the other
   blueprint's `services.py`, never through its `models.py` directly. This
   is the seam that lets us split a blueprint into its own deployable
   later if we ever need to.

A unit test that passes a fake DB session into a service function should be
the cheapest test in the suite — see [`python.tests.md`](./python.tests.md) §2.1.

### 4.4 Cross-cutting

- **Money** — never floats. `decimal.Decimal` end-to-end, persisted as
  `NUMERIC(12, 2)`. A `Money(amount, currency)` value object lives in
  `service_crm/shared/money.py`. (Reaches v1 only if pricing/invoicing
  lands; defer otherwise.)
- **Time** — UTC in storage, business timezone in UI. A single
  `service_crm.shared.clock.now()` helper makes time mockable in tests.
- **IDs** — ULIDs at the edges (sortable, URL-safe, no enumeration).
  ULIDs are 128-bit, binary-compatible with UUIDs, so they're stored as
  native `UUID` on Postgres and `BLOB(16)` on SQLite. The `ULID` type
  lives in `service_crm/shared/ulid.py`.
- **Audit log** — every mutation writes an immutable `AuditEvent` row with
  free-form `before`/`after` JSON. Writes are produced by SQLAlchemy
  `after_insert` / `after_update` / `after_delete` event listeners on an
  `Auditable` mixin, so every model that inherits from it is covered
  automatically. Request context (acting user, request id, reason) is
  attached via a `contextvars.ContextVar` set by a `before_request` hook.
- **Search** — Postgres `tsvector` + GIN index; SQLite FTS5 with a matching
  tokenizer config so dev and prod behave the same (stemming + ranked
  results in both).
- **Config** — 12-factor. `service_crm/config.py` is the only module that
  reads `os.environ`.
- **i18n** — Flask-Babel from day one. Default locale `ro`, secondary `en`.
  Locale selector: user pref → `?lang=` query → `Accept-Language` →
  default. Catalogs at `locale/ro/LC_MESSAGES/messages.po` and
  `locale/en/LC_MESSAGES/messages.po`; `.mo` files compiled at container
  build (not committed). Stored DB enums and lookup `code` columns are
  stable English; UI translates display labels via `_()` /
  `{% trans %}` / `gettext_lazy`. Date and number formatting via Babel
  helpers, never hand-rolled. Full bar in
  [`docs/v1-implementation-goals.md`](./docs/v1-implementation-goals.md) §3.2.

## 5. UI architecture

The visual system is **vendored** from oee-calculator2.0 (per
[`docs/ui-reference.md`](./docs/ui-reference.md)) — copied, not submoduled,
so the standalone constraint holds. Pattern mapping:

| Service-CRM screen          | Vendored pattern (in oee-calculator2.0)              |
| --------------------------- | ---------------------------------------------------- |
| Global shell, topbar        | `templates/base.html` + `partials/theme_init.html`   |
| Operational dashboard       | `templates/admin/dashboard.html`                     |
| Tickets list / list-CRUD    | `templates/admin/orders.html`                        |
| Master-data list (clients)  | `templates/admin/items.html`                         |
| Detail page (ticket, equipment, client) | `templates/admin/item_detail.html`       |
| Filter / report screen      | `templates/admin/reports.html`                       |
| Planning / scheduling       | `templates/admin/planning.html`                      |
| Modal form                  | `templates/forecast_orders.html`                     |
| Dense operational cockpit   | `templates/capacity.html`                            |
| Technician screen (no sidebar) | `templates/operator/dashboard.html`               |

Forbidden, per [`docs/ui-reference.md`](./docs/ui-reference.md): inventing a
new design language, swapping in a component library, gradient/neon styling,
emoji icons, left sidebars on technician screens.

### 5.1 Mobile / PWA (v1 = "PWA-light")

The same Flask app serves desktop browsers and phones; there is no
separate mobile UI and no native mobile build. v1 ships **PWA-light**:
responsive Jinja templates, an installable Web App Manifest, and a small
service worker that caches the shell and static assets. **Online is
required for writes**; an offline write queue is post-1.0 (see
[`ROADMAP.md`](./ROADMAP.md) v1.2).

Pieces that ship in v1 (concrete acceptance criteria in
[`docs/v1-implementation-goals.md`](./docs/v1-implementation-goals.md) §2):

- `service_crm/static/manifest.webmanifest` — name, icons (192/512/maskable),
  `display: standalone`, `start_url`, `theme_color`, `background_color`.
- `service_crm/static/service-worker.js` — versioned cache key tied to
  `VERSION`; precaches the app shell + static assets; runtime-caches
  recently rendered dashboard HTML; `skip waiting + reload` on cache
  mismatch so a bad SW can't pin users on stale UI.
- Responsive macros in `_macros/` — tables collapse to stacked card lists
  below 640 px (`.table-stacked`).
- Touch-target floor of **44 × 44 pt** on every interactive element.
- Mobile-keyboard hints — `type` (`email`/`tel`/`number`/`date`),
  `inputmode`, `autocomplete` set on every relevant field.
- Camera capture for intervention photos via
  `<input type="file" accept="image/*" capture="environment">`. No JS
  beyond the file-input handler.
- Server-side image compression (Pillow) — long edge ≤ 2048 px, WebP q85.
- Idempotency tokens on every state-changing form, deduped server-side
  for 24 h on `(user_id, token)` so a retry from a flaky mobile network
  can't double-create.

What's **not** in v1.0 — and where it goes:

- IndexedDB write queue + replay → v1.2 ([`ROADMAP.md`](./ROADMAP.md)).
- Web Push notifications → v1.1.
- Background sync API → v1.2 alongside the offline queue.
- Native iOS/Android apps → never in this codebase.

## 6. Risks & open questions

- **`oee-calculator2.0` access** — the architecture-only audit in
  [`docs/tasks.md`](./docs/tasks.md) step 2 needs the sibling repo on disk
  or via WebFetch. Until that lands, UI-related decisions are based on
  pattern *names* in [`docs/ui-reference.md`](./docs/ui-reference.md) rather
  than the actual templates. Tracked in
  [`docs/architecture-plan.md`](./docs/architecture-plan.md) §1.2.
- **Blueprints with internal models vs. flat `models/`** — proposed in
  [`docs/architecture-plan.md`](./docs/architecture-plan.md) §3.2; pending
  approval.
- **Maintenance scope** — does it deserve its own blueprint or live inside
  `equipment/`? Pending approval.
- **`Auditable` mixin vs. explicit service-side audits** — pending approval.
- **Postgres FTS / SQLite FTS5** — feasible but adds a tokenizer config we
  need to verify behaves the same on both backends. Worth testing in 0.2.0.
- **Alembic + SQLite** — needs `render_as_batch=True`. Worth verifying in
  the 0.1.0 walking skeleton.
- **iOS PWA quirks** — iOS Safari has gaps (storage limits; camera-in-PWA
  edge cases). Mitigation: every camera path also has a regular file-input
  fallback, and we manually pass real-device QA on iOS each release. See
  [`docs/v1-implementation-goals.md`](./docs/v1-implementation-goals.md) §6.
- **Service worker shipping a stale shell** — a bad SW can pin users on
  broken assets. Mitigation: cache key tied to `VERSION`, plus a
  `skip waiting + reload` path on mismatch.

## 7. Decision log

Architectural decisions live as numbered ADRs in `docs/adr/NNNN-title.md`
([MADR](https://adr.github.io/madr/)). The first ADRs to write before
v0.1 ships:

- ADR-0001: Flask + Jinja over a SPA / FastAPI.
- ADR-0002: Single-tenant deployment model.
- ADR-0003: UI design language is vendored from `oee-calculator2.0`.
- ADR-0004: Blueprints own their models, routes, forms, services; templates
  centralised under `service_crm/templates/<bp>/`.
- ADR-0005: ULID at the edges, native `UUID` storage on Postgres.
- ADR-0006: Audit via SQLAlchemy event listeners on an `Auditable` mixin.
- ADR-0007: Mobile = PWA-light in v1; full offline write queue deferred
  to v1.2.
- ADR-0008: Bilingual RO + EN from day one (RO default), via Flask-Babel.
- [ADR-0001](./docs/adr/0001-flask-vs-fastapi.md) — *accepted* — Flask
  over FastAPI for v1.
