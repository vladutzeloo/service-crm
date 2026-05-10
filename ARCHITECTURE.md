# Service CRM — Architecture & Planning

> Status: **planning** — no code has landed yet. This document is the source of
> truth for what we are building and why. The [ROADMAP](./ROADMAP.md) tracks
> when each piece ships.

## 1. Product summary

Service CRM is a **standalone, self-hostable CRM for service-oriented small
businesses** — repair shops, IT/MSP outfits, HVAC, appliance repair, mobile
field technicians, and similar. It is opinionated and narrow on purpose: it
manages customers, the equipment they own, the work performed on that
equipment, and the money that changes hands as a result.

Non-goals (explicit):

- Marketing automation, email campaigns, lead funnels.
- A general-purpose sales pipeline (Hubspot/Salesforce territory).
- Multi-tenant SaaS hosting. A single deployment serves a single business.
  Multiple businesses run multiple deployments.
- Mobile-first UX. Mobile is supported but the design center is a desk.

## 2. Primary users & jobs-to-be-done

| User           | Top jobs                                                                  |
| -------------- | ------------------------------------------------------------------------- |
| Front-desk     | Intake a customer + asset, open a work order, quote/invoice, take payment |
| Technician     | See queued jobs, log time and parts, mark complete                        |
| Owner/manager  | See backlog, technician utilization, revenue, outstanding A/R             |
| Customer       | (v0.4+) Self-service portal: status of their job, history, invoices       |

## 3. Domain model (initial cut)

```
Customer 1───* Asset 1───* WorkOrder 1───* WorkLog
                                  │
                                  ├──* PartUsage *──1 InventoryItem
                                  └──1 Invoice 1──* Payment

User (technician/admin) 1──* WorkLog
```

Key entities and the invariants they enforce:

- **Customer** — person or company. Soft-delete only; financial history must
  remain queryable.
- **Asset** — the *thing* being serviced (laptop, furnace, vehicle). Belongs
  to one customer at a time; ownership transfers are an audited event.
- **WorkOrder** — the unit of work. State machine:
  `draft → scheduled → in_progress → awaiting_parts → completed → invoiced → closed`,
  with `cancelled` reachable from any pre-`invoiced` state.
- **WorkLog** — append-only labor entries (technician, start/stop, notes).
- **InventoryItem / PartUsage** — stock decrement happens on `PartUsage`
  insert, not on invoice. This matches what actually happens on the bench.
- **Invoice / Payment** — invoices are immutable once issued; corrections are
  credit notes, not edits. (Required for any jurisdiction with VAT/sales-tax
  audit obligations.)

## 4. Architecture

### 4.1 Stack

| Layer         | Choice                                       | Why                                                       |
| ------------- | -------------------------------------------- | --------------------------------------------------------- |
| Language      | Python 3.11+                                 | Mandated by the project; matches small-shop ops skill set |
| Web framework | FastAPI                                      | Async, OpenAPI for free, type-driven, easy to test        |
| ORM           | SQLAlchemy 2.x + Alembic                     | Mature, supports both Postgres and SQLite                 |
| DB (prod)     | PostgreSQL 15+                               | Money + audit + FTS                                       |
| DB (dev/test) | SQLite                                       | Zero-setup for contributors and CI                        |
| Auth          | Session cookies + Argon2 password hashing    | Single-tenant, server-rendered admin                      |
| Frontend      | Server-rendered Jinja2 + HTMX + Alpine.js    | No SPA build pipeline; ships in one container             |
| Background    | APScheduler (v0.x), RQ + Redis (v1.0+)       | Start in-process, graduate when load justifies it         |
| Packaging     | `pyproject.toml` (PEP 621), Docker image     | One install path for hackers, one for operators           |

The deliberate constraint is **"runs from a single container against a single
Postgres"**. Anything that breaks that constraint needs an explicit roadmap
entry.

### 4.2 Layout (target)

The importable package is `service_crm` (matches `pyproject.toml` and the
mirror layout in [python.tests.md §1](./python.tests.md#1-layout)).

```
service_crm/            # the importable Python package
├── api/                # FastAPI routers
├── web/                # Jinja templates + HTMX endpoints
├── domain/             # Pure-Python models, state machines, money math
├── db/                 # SQLAlchemy models, session, alembic env
├── services/           # Use-cases (issue_invoice, record_payment, ...)
├── auth/               # Sessions, password hashing, RBAC
├── jobs/               # Scheduled / background tasks
├── clock.py            # `now()` shim (mockable in tests)
└── settings.py         # Pydantic Settings, 12-factor env
migrations/             # Alembic, lives at the repo root
tests/                  # See python.tests.md
docs/
pyproject.toml
Dockerfile
```

Two rules that keep the layers honest:

1. `service_crm.domain` imports nothing from `service_crm.db`,
   `service_crm.api`, or `service_crm.web`. Domain is pure functions and
   dataclasses — trivially unit-testable.
2. `service_crm.api` and `service_crm.web` never touch `db.session`
   directly; they call `service_crm.services`. Services are the only
   callers of the ORM.

### 4.3 Cross-cutting

- **Money** — never floats. `decimal.Decimal` end-to-end, persisted as
  `NUMERIC(12, 2)`. A `Money(amount, currency)` value object lives in
  `service_crm/domain/money.py`.
- **Time** — UTC in storage, business timezone in UI. A single
  `service_crm.clock.now()` helper makes time mockable in tests.
- **IDs** — ULIDs for externally-visible IDs (sortable, URL-safe, no
  enumeration). ULIDs are 128-bit and binary-compatible with UUIDs, so on
  Postgres they are stored in native `UUID` columns (16 bytes, fast index,
  small foot­print) and rendered/parsed as Crockford-base32 at the edges.
  On SQLite — dev/test only — they fall back to a `BLOB(16)` column with the
  same binary encoding so behavior matches.
- **Audit log** — every mutation writes an immutable `AuditEvent` row with
  free-form `before`/`after` JSON. We don't trust developers to remember:
  the writes are produced by SQLAlchemy `after_insert` / `after_update` /
  `after_delete` event listeners on a marker base class (`Auditable`), so
  any model that inherits from it is covered automatically. Service-level
  context (acting user, request id, reason) is attached via a contextvar
  set by the request middleware, so the listener has everything it needs
  without each service remembering to call an `audit(...)` helper.
- **Config** — 12-factor. `service_crm/settings.py` is the only place that
  reads env.

## 5. Risks & open questions

- **Tax compliance** — invoice immutability and credit-note semantics need
  legal review per market. We only commit to EU-style VAT in v1.0; US sales
  tax via TaxJar/Avalara is post-1.0.
- **Offline technician mode** — explicitly out of scope until v1.2. Field
  techs use the mobile web view online.
- **Migrations on SQLite** — Alembic + SQLite needs `render_as_batch=True`.
  Worth verifying early so we don't paint ourselves into a corner.
- **HTMX vs SPA** — we are betting that HTMX scales to the whole app. If a
  single screen forces us into React, we cordon it off rather than rewriting.

## 6. Decision log

Architectural decisions live as numbered ADRs in `docs/adr/NNNN-title.md`
(format: [MADR](https://adr.github.io/madr/)). The first ADRs to write before
v0.1 ships:

- ADR-0001: FastAPI + Jinja + HTMX over a SPA.
- ADR-0002: Single-tenant deployment model.
- ADR-0003: Invoices are immutable; corrections are credit notes.
- ADR-0004: Inventory decrements on part usage, not on invoice.
