# Service-CRM — Roadmap

We follow [Semantic Versioning 2.0.0](https://semver.org/):
`MAJOR.MINOR.PATCH`. Pre-1.0, **MINOR bumps may break things**; from 1.0
onwards, only MAJOR bumps may.

The milestones below mirror the implementation sequence in
[`docs/tasks.md`](./docs/tasks.md), the modules listed in
[`AGENTS.md`](./AGENTS.md) §"Architecture Rules", and the entities defined
in [`docs/service-domain.md`](./docs/service-domain.md). Every milestone is
gated on architecture sign-off per [`docs/architecture-plan.md`](./docs/architecture-plan.md).
The per-version testing capabilities that ship with each minor release
are tracked in [`docs/testing-cadence.md`](./docs/testing-cadence.md) §4.

Tags are `vX.Y.Z`. Pushing a tag triggers
[`.github/workflows/release.yml`](./.github/workflows/release.yml), which
validates `VERSION` + `CHANGELOG.md`, runs the suite, and publishes a
GitHub Release. See [`.github/RELEASING.md`](./.github/RELEASING.md).

## Release cadence

- **Patch (`0.x.Y`)** — as soon as a fix is ready and tested.
- **Minor (`0.Y.0`)** — roughly one milestone per minor.
- **Major** — only `1.0.0`, then we stabilize.

A release happens when the `## [Unreleased]` section of the changelog has
shipped scope worth cutting, CI is green on `main`, and the migration story
from the previous tag has been verified.

---

## 0.0.x — Planning (current)

Documentation and skills only — no application code.

- [x] `AGENTS.md`, `docs/service-domain.md`, `docs/ui-reference.md`,
      `docs/tasks.md`, `docs/commands.md`, `docs/obsidian-brain.md` (user-supplied).
- [x] CI + release workflow scaffolding (stack-agnostic).
- [x] `pyproject.toml`, `VERSION`, `CHANGELOG.md`, `.gitignore`.
- [x] `ARCHITECTURE.md`, `ROADMAP.md`, `python.tests.md` realigned to Flask.
- [x] `docs/architecture-plan.md` — architectural plan **approved 2026-05-10**.
- [x] `.claude/skills/` — project-level Claude Code skills mirroring [`docs/tasks.md`](./docs/tasks.md).

## 0.1.0 — "Walking skeleton"

The smallest thing that runs. Nothing user-visible beyond plumbing.
Mirrors [`docs/tasks.md`](./docs/tasks.md) steps 1–6 (audit + propose + review
already done; this milestone executes the approved plan).

- [ ] `service_crm/__init__.py` — `create_app()` factory.
- [ ] `service_crm/extensions.py` — `db`, `migrate`, `login_manager`, `csrf`.
- [ ] `service_crm/config.py` — Dev / Test / Prod config classes.
- [ ] `service_crm/cli.py` — `flask reset-db`, `flask seed`.
- [ ] Alembic wired against Postgres and SQLite (`render_as_batch=True`).
- [ ] `auth/` blueprint: `User`, `Role`, login/logout, Argon2 hashing.
- [ ] First migration (`users`, `roles`).
- [ ] Healthcheck route + version endpoint.
- [ ] Dockerfile + `docker compose up` runs the app against Postgres.
- [ ] `tests/` skeleton with the fixtures from [`python.tests.md`](./python.tests.md).
- [ ] CI green on Python 3.11 and 3.12, both SQLite and Postgres.

## 0.2.0 — "UI foundation"

Mirrors [`docs/tasks.md`](./docs/tasks.md) step 7. UI shell only — no
business logic. Requires the `oee-calculator2.0` source files (per
[`docs/architecture-plan.md`](./docs/architecture-plan.md) §1.2).

- [ ] Vendor `templates/base.html` and `partials/theme_init.html` from
      `oee-calculator2.0`.
- [ ] Vendor `static/css/style.css` (tokens, surfaces, buttons, tables, cards).
- [ ] Topbar, KPI card macro, table macro, filter macro, form-shell macro,
      tabs macro — all as Jinja includes.
- [ ] Light mode default; `data-theme="dark"` only where it follows the OEE
      pattern.
- [ ] Lucide icons via the existing base layout pattern.
- [ ] No emoji; no left sidebar on technician screens.
- [ ] Visual smoke test: a placeholder page that renders every macro looks
      native to oee-calculator2.0.

## 0.3.0 — "Clients & contacts"

Mirrors [`docs/tasks.md`](./docs/tasks.md) steps 8–11 for the `clients` blueprint.

- [ ] `Client`, `Contact`, `Location` models + Alembic migration.
- [ ] CRUD routes, list, detail, edit-modal — all using the 0.2.0 macros.
- [ ] Search across clients/contacts (Postgres `tsvector` + GIN, SQLite FTS5).
- [ ] CSV import for clients.
- [ ] Soft-delete (`is_active = False`) — financial/service history must remain queryable.
- [ ] Tests: relationships, unique constraints, cascade behavior.

## 0.4.0 — "Equipment / installed base"

- [ ] `Equipment` model + migration (FKs to `Client`, `Location`).
- [ ] Equipment list bound to a client; equipment detail page.
- [ ] Constraint: `Equipment.location_id`, when set, must belong to
      `Equipment.client_id`. Service-layer guard + integration test.
- [ ] CSV import for equipment.

## 0.5.0 — "Tickets & interventions"

The core loop: open a ticket, log interventions, close it.
Mirrors [`docs/tasks.md`](./docs/tasks.md) step 12 (workflow tests).

- [ ] `ServiceTicket` + status state machine
      (`open → scheduled → in_progress → awaiting_parts → resolved → closed`,
      with `cancelled` reachable from any pre-closed state).
- [ ] `ServiceIntervention` (technician, start/stop, notes).
- [ ] `ServicePartUsage` per intervention.
- [ ] Tickets list with filters (status, priority, due, technician).
- [ ] Ticket detail with intervention timeline.
- [ ] Audit log entries for every state transition.
- [ ] Tests: state machine ≥ 95% line+branch (via Hypothesis state machine).

## 0.6.0 — "Knowledge: checklists & procedures"

- [ ] `ChecklistTemplate` (items as JSON: `{key, label, kind}`).
- [ ] `ChecklistRun` with frozen template snapshot.
- [ ] `ProcedureDocument` (Markdown body, tags).
- [ ] Attach a checklist run to a ticket / intervention / equipment item.
- [ ] Procedure search.

## 0.7.0 — "Maintenance planning"

- [ ] `MaintenancePlan` model (cadence_days, last_done_at, next_due_at).
- [ ] Background job (APScheduler) to recompute `next_due_at`.
- [ ] "Equipment with due maintenance" surfaced on the dashboard.
- [ ] Generate a ticket from an overdue maintenance plan.

## 0.8.0 — "Operational dashboard"

Mirrors [`docs/service-domain.md`](./docs/service-domain.md) §"Dashboard V1".

- [ ] Active clients, active tickets, interventions today, due maintenance,
      technician capacity, latest interventions — all as compact cards.
- [ ] Modeled on `oee-calculator2.0/templates/admin/dashboard.html`.
- [ ] Technician variant modeled on `templates/operator/dashboard.html`.

## 0.9.0 — "Hardening for 1.0"

Feature freeze. Stabilization, performance, docs.

- [ ] Backup/restore documented and tested end-to-end.
- [ ] Upgrade path documented for every prior 0.x → 1.0.
- [ ] Performance budget defined and met (P95 page < 300 ms on reference dataset).
- [ ] Security review: dependency audit, session fixation, CSRF, RBAC matrix.
- [ ] User guide and operator guide complete.
- [ ] Consistency pass per [`docs/tasks.md`](./docs/tasks.md) §"Consistency Pass".

## 1.0.0 — "Production-ready single-tenant"

DB schema and HTTP routes covered by SemVer guarantees from this point forward.

- Schema migrations are forward-only and tested both ways.
- LTS-style support: critical fixes backported to `1.0.x` for 12 months.

---

## Beyond 1.0 (sketch — order may change)

| Version | Theme                       | Highlights                                                     |
| ------- | --------------------------- | -------------------------------------------------------------- |
| 1.1     | Customer portal             | Self-service ticket status, history download                   |
| 1.2     | Field-tech offline mode     | PWA + local sync queue                                         |
| 1.3     | VMES/OEE integration        | Read-only OEE asset/equipment sync via API; no shared DB       |
| 1.4     | Quoting & invoicing         | Quote → invoice flow, PDF, EU-style VAT                        |
| 1.5     | Reporting & BI              | Saved reports, CSV/Parquet export, Metabase-friendly views     |
| 2.0     | Multi-location single-tenant| Branches under one tenant; *not* multi-tenant SaaS             |

## How items get on the roadmap

1. Open a GitHub issue with the `proposal` label.
2. If it survives a week of discussion, an ADR lands in `docs/adr/`.
3. The ADR's "Decision" section dictates which milestone it gets attached to.

Anything not on this list is **not on the roadmap** — please don't infer
commitments from chat threads or PR comments.
