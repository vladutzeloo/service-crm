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

The concrete acceptance criteria for each milestone — the "done when" bar
and the production / phone-readiness checklists — live in
[`docs/v1-implementation-goals.md`](./docs/v1-implementation-goals.md).
This file is the *order*; that file is the *bar*.

Tags are `vX.Y.Z`. Pushing a tag triggers
[`.github/workflows/release.yml`](./.github/workflows/release.yml), which
validates `VERSION` + `CHANGELOG.md`, runs the suite, and publishes a
GitHub Release. See [`.github/RELEASING.md`](./.github/RELEASING.md).

## v1.0 scope (locked)

- Single Flask/Jinja codebase. No SPA, no native mobile.
- **Phones supported via PWA-light** (responsive + manifest + minimal
  service worker). Online required for writes; full offline write queue
  is deferred to v1.2.
- Web Push deferred to v1.1; v1.0 notifications are in-app + email only.
- Self-hosted single-server target (one VPS, one Postgres, one container).
- Single-tenant.
- **Bilingual from day one**: Romanian (default) + English (selectable).
  Flask-Babel + RO/EN catalogs land in 0.1.0; every milestone after has
  translated UI, statuses, and form errors.
- **CNC service domain in full** (per
  [`docs/blueprint.md`](./docs/blueprint.md) §8) — equipment models,
  controller types, warranties, ticket history/comments/attachments,
  intervention actions/findings, parts master, maintenance
  template/plan/task/execution, structured checklists, technician
  capacity slots.
- **Stack: Flask + Jinja + SQLAlchemy + Alembic + pytest** — confirmed
  in [`docs/adr/0001-flask-vs-fastapi.md`](./docs/adr/0001-flask-vs-fastapi.md).

Full rationale and acceptance criteria:
[`docs/v1-implementation-goals.md` §0](./docs/v1-implementation-goals.md#0-decided-scope-of-v1).

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

- [x] `service_crm/__init__.py` — `create_app()` factory.
- [x] `service_crm/extensions.py` — `db`, `migrate`, `login_manager`,
      `csrf`, `babel`.
- [x] `service_crm/config.py` — Dev / Test / Prod config classes.
- [x] `service_crm/cli.py` — `flask reset-db`, `flask seed`,
      `flask babel-extract` / `babel-update` / `babel-compile`.
- [x] Alembic wired against Postgres and SQLite (`render_as_batch=True`).
- [x] `auth/` blueprint: `User`, `Role`, login/logout, Argon2 hashing.
- [x] First migration (`users`, `roles`).
- [x] **Flask-Babel scaffold**: `babel.cfg`, `service_crm/locale/ro/`,
      `service_crm/locale/en/`. Locale selector function (user pref →
      query → header → default `ro`). 0.1.0 ships the language switch
      inline on the bare login page; topbar widget arrives with the
      shell in 0.2.0.
- [x] Healthcheck route + version endpoint, both translated.
- [x] Dockerfile + `docker compose up` runs the app against Postgres.
- [x] `tests/` skeleton with the fixtures from [`python.tests.md`](./python.tests.md).
- [x] i18n smoke test: `/healthz?lang=ro` returns RO text, `?lang=en` returns EN.
- [x] CI green on Python 3.11 and 3.12, both SQLite and Postgres.

## 0.2.0 — "UI foundation (mobile-first from day one)"

Mirrors [`docs/tasks.md`](./docs/tasks.md) step 7. UI shell only — no
business logic. Requires the `oee-calculator2.0` source files (per
[`docs/architecture-plan.md`](./docs/architecture-plan.md) §1.2).

- [ ] Vendor `templates/base.html` and `partials/theme_init.html` from
      `oee-calculator2.0`.
- [ ] Vendor `static/css/style.css` (tokens, surfaces, buttons, tables, cards).
- [ ] Topbar, KPI card macro, table macro, filter macro, form-shell macro,
      tabs macro, modal macro — all as Jinja includes.
- [ ] **PWA manifest** (`static/manifest.webmanifest`) with name, icons
      (192/512/maskable), `display: standalone`, `start_url`.
- [ ] **Service worker** (`static/service-worker.js`) registered from
      `base.html`. Caches app shell + static assets only — no write-side
      caching in v1.
- [ ] Responsive breakpoints verified at 320 / 768 / 1024 / 1440 px.
      Tables stack as cards below 640 px (`.table-stacked` pattern).
- [ ] Touch targets ≥ 44 × 44 pt on every interactive element in the
      smoke page.
- [ ] Light mode default; `data-theme="dark"` only where it follows the OEE
      pattern.
- [ ] Lucide icons via the existing base layout pattern.
- [ ] No emoji; no left sidebar on technician screens.
- [ ] Visual smoke test: a placeholder page that renders every macro looks
      native to oee-calculator2.0 on desktop **and** on phone.
- [ ] Lighthouse mobile run on the smoke page: Performance ≥ 90,
      Accessibility ≥ 95, PWA badge: yes.
- [ ] Macro labels and tooltips wrapped in `_()` / `{% trans %}`. RO and
      EN translations of every shipped macro.

## 0.3.0 — "Clients, contacts, locations, contracts"

Mirrors [`docs/tasks.md`](./docs/tasks.md) steps 8–11 for the `clients` blueprint.

- [ ] `Client`, `Contact`, `Location`, `ServiceContract` models + Alembic
      migration.
- [ ] CRUD routes, list, detail, edit-modal — all using the 0.2.0 macros.
- [ ] Search across clients/contacts (Postgres `tsvector` + GIN, SQLite FTS5).
- [ ] CSV import for clients.
- [ ] Soft-delete (`is_active = False`) — service history must remain queryable.
- [ ] Tests: relationships, unique constraints, cascade behavior.
- [ ] All form labels, validators, and flash messages translated (RO + EN).

## 0.4.0 — "Equipment / installed base"

- [ ] `Equipment`, `EquipmentModel`, `EquipmentControllerType`,
      `EquipmentWarranty` models + migration (FKs to `Client`, `Location`).
- [ ] Equipment list bound to a client; equipment detail page (with
      warranties + tickets + maintenance plans tab).
- [ ] Constraint: `Equipment.location_id`, when set, must belong to
      `Equipment.client_id`. Service-layer guard + integration test.
- [ ] Constraint: `EquipmentWarranty.ends_on > starts_on`. CHECK + test.
- [ ] CSV import for equipment + bulk-load of `EquipmentModel` / 
      `EquipmentControllerType` lookups.
- [ ] All UI strings translated.

## 0.5.0 — "Tickets — header, history, comments, attachments"

Core ticket workflow. Splits the ticket domain across two milestones so
0.5 stays reviewable; interventions land in 0.6.

- [x] `ServiceTicket` + state machine
      (`new → qualified → scheduled → in_progress → waiting_parts →
      monitoring → completed → closed`, `cancelled` from any pre-completed
      state) — pure-Python `tickets/state.py`.
- [x] `TicketStatusHistory` (append-only); `before_flush` hook writes a
      row on every status change.
- [x] `TicketComment`, `TicketAttachment`.
- [x] `TicketType`, `TicketPriority` lookup tables seeded with default
      RO/EN-translated labels.
- [x] Tickets list with filters (status, priority, type, due, technician,
      client) and translated filter chips.
- [x] Ticket detail page with status-history timeline.
- [x] Idempotency token on every state-changing form (server-rendered
      UUID, `(user_id, token)` dedupe for 24 h). Tested by forced retry.
- [x] Tests: state machine ≥ 95 % line+branch (Hypothesis state machine);
      integration tests assert no history-less status transitions.

## 0.6.0 — "Interventions, parts, knowledge"

Phone-first slice: the technician must be able to do their whole job
from a phone in the field.

- [x] `ServiceIntervention`, `InterventionAction`, `InterventionFinding`.
- [x] `PartMaster` lookup, `ServicePartUsage` per intervention.
- [x] `ChecklistTemplate`, `ChecklistTemplateItem`, `ChecklistRun`,
      `ChecklistRunItem` — frozen snapshot pattern; property-based test
      that historical runs survive template edits.
- [x] `ProcedureDocument`, `ProcedureTag`.
- [x] Intervention create/edit form built for one-handed phone use:
      ≥ 44 pt taps, mobile keyboards (`type`/`inputmode`/`autocomplete`),
      camera capture
      (`<input type="file" accept="image/*" capture="environment">`).
- [x] Server-side photo compression (Pillow): long edge ≤ 2048 px, WebP q85.
- [x] Procedure search (PG `tsvector` / SQLite FTS5).
- [x] All form labels, status labels, intervention-action templates
      translated.

## 0.7.0 — "Maintenance + planning"

- [ ] `MaintenanceTemplate`, `MaintenancePlan`, `MaintenanceTask`,
      `MaintenanceExecution` models + migration.
- [ ] APScheduler job: recompute `MaintenancePlan.next_due_at` and
      generate `MaintenanceTask` rows for the upcoming window.
- [ ] One-click "open a ticket from this overdue plan" — links the
      ticket back to the plan via `MaintenanceTask.ticket_id`.
- [ ] `Technician`, `TechnicianAssignment`, `TechnicianCapacitySlot`
      models + migration.
- [ ] Technician capacity view (per-day load) modeled on
      `oee-calculator2.0/templates/capacity.html`.
- [ ] All planning labels translated.

## 0.8.0 — "Operational dashboard + reporting"

Mirrors [`docs/service-domain.md`](./docs/service-domain.md) §"Dashboard V1"
and [`docs/blueprint.md`](./docs/blueprint.md) §13–§14.

- [ ] Manager view (`templates/dashboard/admin.html`) — KPI tiles for
      active clients, open tickets, overdue tickets, due maintenance
      this week, tickets waiting parts, technician utilization.
      Secondary panels: tickets by status, upcoming maintenance, recent
      interventions, high-risk machines, technician load by week.
      Modeled on `oee-calculator2.0/templates/admin/dashboard.html`.
- [ ] Technician view (`templates/dashboard/operator.html`) — no left
      sidebar, today's queue, one-tap "start intervention". Modeled on
      `oee-calculator2.0/templates/operator/dashboard.html`.
- [ ] Core reports (per [`docs/blueprint.md`](./docs/blueprint.md) §14):
      tickets by status & period, interventions by machine, parts used,
      due-vs-completed maintenance, technician workload, repeat-issue
      report. Translated labels; stable internal codes; locale-aware
      dates and numbers; CSV export.
- [ ] Both views meet the P95 budget on the reference dataset
      (see [`docs/v1-implementation-goals.md`](./docs/v1-implementation-goals.md) §1.3).
- [ ] Lighthouse mobile run on both dashboards: Performance ≥ 90,
      Accessibility ≥ 95.

## 0.9.0 — "Hardening for 1.0"

Feature freeze. Spend a milestone making the bars in
[`docs/v1-implementation-goals.md`](./docs/v1-implementation-goals.md) §1
and §2 actually true.

- [ ] §1.1 functional completeness — manual walkthrough of every P1
      journey passes.
- [ ] §1.3 perf budget — load reference dataset (10 k clients, 100 k
      tickets), verify P95 budgets, fix offenders.
- [ ] §1.4 security — pen-test pass on auth + CSRF + RBAC matrix +
      headers + uploads. `pip-audit` clean.
- [ ] §1.5 observability — JSON logs, `/healthz` + `/readyz`, optional
      `/metrics`, 24-h soak review.
- [ ] §1.6 operability — backup → restore round-trip dry-run on the
      release candidate.
- [ ] §1.7 documentation — user guide, operator runbook, ADRs (≥ 6),
      `CHANGELOG.md` populated for `1.0.0`.
- [ ] §1.8 compliance — GDPR export + forget endpoints implemented and
      tested.
- [ ] §2 phone-readiness — Lighthouse mobile run on every P1 page meets
      the §2.6 thresholds. Real-device pass on iPhone + Android.
- [ ] §3.1 a11y — `axe-core` clean on every P1 page. Manual keyboard pass.
- [ ] §3.2 i18n — `ro` catalog at 100 % coverage of user-facing strings.
- [ ] Consistency pass per [`docs/tasks.md`](./docs/tasks.md) §"Consistency Pass".

## 1.0.0 — "Production-ready single-tenant"

DB schema and HTTP routes covered by SemVer guarantees from this point
forward. Tag only when the §5 release exit checklist in
[`docs/v1-implementation-goals.md`](./docs/v1-implementation-goals.md) is
fully ticked.

- Schema migrations are forward-only and tested both ways.
- LTS-style support: critical fixes backported to `1.0.x` for 12 months.
- Public REST API endpoints documented and stable.

---

## Beyond 1.0 (sketch — order may change)

| Version | Theme                       | Highlights                                                     |
| ------- | --------------------------- | -------------------------------------------------------------- |
| 1.1     | Customer portal + Web Push  | Self-service ticket status, history download, opt-in Web Push  |
| 1.2     | Field-tech offline writes   | IndexedDB queue + replay-on-reconnect for interventions        |
| 1.3     | CNC depth                   | Controller alarm knowledge base, runtime-based maintenance triggers, `TechnicianSkill` matching (per [`docs/blueprint.md`](./docs/blueprint.md) §21 Phase 5) |
| 1.4     | VMES/OEE integration        | Read-only OEE asset/equipment sync via API; no shared DB       |
| 1.5     | Quoting & invoicing         | Quote → invoice flow, PDF, EU-style VAT                        |
| 1.6     | Reporting & BI              | Saved reports, CSV/Parquet export, Metabase-friendly views     |
| 2.0     | Multi-location single-tenant| Branches under one tenant; *not* multi-tenant SaaS             |

## How items get on the roadmap

1. Open a GitHub issue with the `proposal` label.
2. If it survives a week of discussion, an ADR lands in `docs/adr/`.
3. The ADR's "Decision" section dictates which milestone it gets attached to.

Anything not on this list is **not on the roadmap** — please don't infer
commitments from chat threads or PR comments.
