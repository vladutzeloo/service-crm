# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

The release workflow (`.github/workflows/release.yml`) extracts the section
matching the pushed tag (e.g. `v0.1.0` → `## [0.1.0]`) and uses it as the
GitHub Release body. Keep entries terse, user-facing, and grouped under the
standard headings: **Added / Changed / Deprecated / Removed / Fixed / Security**.

## [Unreleased]

### Added

- `docs/v0.9-plan.md` — `/architecture-audit` output for ROADMAP §0.9.0
  ("Hardening for 1.0"). Doc-only; no application code. Maps the §1 /
  §2 / §3 bars in `docs/v1-implementation-goals.md` onto eight
  workstreams (W0 minimum dashboard slice through W8 phone / a11y /
  i18n polish), addresses the 0.8 dashboard gap head-on (recommends
  absorbing a minimum dashboard slice into 0.9 as W0 — catch-up
  release pattern from PR #21), and sequences the workstreams as a
  series of small PRs against this branch rather than one mega-PR.

## [0.7.0] - 2026-05-13

### Added

- **Maintenance + planning** — ROADMAP 0.7.0.
  - New `service_crm/maintenance/` blueprint with
    `MaintenanceTemplate`, `MaintenancePlan`, `MaintenanceTask`,
    `MaintenanceExecution`. `next_due_on` is a derived field — the
    service layer is the only writer; routes never set it directly.
  - New `service_crm/planning/` blueprint with `Technician` (1:1 with
    `User`), `TechnicianAssignment` (with a DB-level CHECK so a row
    must reference a ticket or intervention), and
    `TechnicianCapacitySlot` (per-day declared minutes).
  - **APScheduler** bootstrap in `service_crm/shared/scheduler.py`.
    In-process `BackgroundScheduler` gated by `SCHEDULER_ENABLED`
    (off in tests + dev, on in prod). Two recurring jobs:
    `maintenance_tick` (recomputes every active plan's `next_due_on`
    and generates the next pending task inside a 14-day horizon) and
    `idempotency_sweep` (formerly cron-only).
  - **One-click escalation** — `POST /maintenance/tasks/<hex>/escalate`
    creates a `ServiceTicket` (`preventive` / `normal`) seeded from
    the plan + template; the resulting `MaintenanceTask.ticket_id`
    points back so the link is bidirectional. Idempotency-token
    guarded.
  - **Technician capacity view** modeled on
    `oee-calculator2.0/templates/capacity.html` —
    per-(technician, day) grid coloured by ratio of scheduled
    assignments to declared capacity. Defaults to today + 13 days;
    `?start=` / `?end=` override.
  - Alembic migration
    `20260513_1800_e6f1a2b3c4d5_maintenance_planning.py` creates
    every new table with the indexes and CHECK constraints called
    out in the architecture plan §4.
  - Routes (all `@login_required`):
    `/maintenance/templates[/...]`,
    `/maintenance/plans[/..., new, <hex>, <hex>/edit, <hex>/generate-tasks]`,
    `/maintenance/tasks[/..., <hex>, <hex>/assign, <hex>/complete,
    <hex>/escalate]`, `/planning/technicians[/..., new, <hex>,
    <hex>/edit, <hex>/slots, <hex>/slots/<sid>/delete]`,
    `/planning/capacity`.
  - **CLI**: new `flask run-maintenance-tick` exposes the scheduler
    entrypoint for cron / dev triggering.
  - Sidebar `Maintenance` and `Planning` placeholder links are now
    wired up to the new blueprints.
  - **172 new tests** across `tests/maintenance/`, `tests/planning/`,
    and `tests/shared/test_scheduler.py`: models (constraints,
    cascades, CHECK), services (CRUD, scheduler tick idempotency,
    one-task-per-plan rule, escalation flow), routes (every endpoint,
    idempotent retries, validation flashes, query-string filters),
    scheduler (init_app gating, idempotent restart, job execution
    inside an app context).
  - Test factories: `MaintenanceTemplateFactory`,
    `MaintenancePlanFactory`, `MaintenanceTaskFactory`,
    `MaintenanceExecutionFactory`, `TechnicianFactory`,
    `TechnicianAssignmentFactory`, `TechnicianCapacitySlotFactory`.
  - **RO + EN translations** for every new label, status, button
    caption, and flash message; catalogs compiled into the wheel.

### Changed

- `service_crm/__init__.py` registers the two new blueprints and
  calls `shared.scheduler.init_app`.
- `service_crm/config.py` adds `SCHEDULER_ENABLED`,
  `SCHEDULER_MAINTENANCE_INTERVAL_MIN`, and
  `SCHEDULER_IDEMPOTENCY_INTERVAL_H` — defaults are off / 60 min /
  6 h respectively.
- `service_crm/cli.py` adds `run-maintenance-tick`. The
  `sweep-idempotency` docstring now points at the scheduler instead
  of a "v0.7 will…" placeholder.
- `service_crm/templates/base.html` sidebar `Maintenance` and
  `Planning` entries now link to the new blueprint indices.
- `pyproject.toml` mypy override extends the `arg-type` suppression
  list to `maintenance.routes`, `maintenance.services`,
  `planning.routes`, and `shared.scheduler` — same rationale as the
  v0.5 / v0.6 entries (`scoped_session` vs. `Session`).

## [0.6.0] - 2026-05-13

### Added

- **Interventions, parts, knowledge** — ROADMAP 0.6.0.
  - `service_crm/tickets/intervention_models.py` adds
    `ServiceIntervention`, `InterventionAction`,
    `InterventionFinding`, `PartMaster`, `ServicePartUsage` to the
    tickets blueprint. The v0.5 placeholder column
    `TicketAttachment.intervention_id` is wired up (nullable FK with
    `ON DELETE SET NULL`).
  - `service_crm/knowledge/` blueprint with `ChecklistTemplate` +
    `ChecklistTemplateItem`, `ChecklistRun` + `ChecklistRunItem`
    (frozen-snapshot pattern — editing a template never mutates
    historical runs; property test asserts this), and
    `ProcedureDocument` + `ProcedureTag` (M2M).
  - Alembic migration
    `20260513_0900_d5e9f1a2b3c4_interventions_parts_knowledge.py`
    creates every new table, the `TicketAttachment.intervention_id`
    column, and Postgres GIN expression-indices on
    `procedure_document(title + summary + body)` and
    `part_master(code + description)`.
  - Routes:
    `/tickets/<hex>/interventions/{new, <hex>, <hex>/edit,
    <hex>/stop, <hex>/actions[…], <hex>/findings[…], <hex>/parts[…],
    <hex>/photos[…]}`, plus the parts catalog under
    `/tickets/parts[…]` and the full knowledge surface under
    `/knowledge/{procedures[…], tags[…], templates[…]}`.
  - **Phone-first intervention form** (`templates/tickets/
    intervention_edit.html` + `intervention_detail.html`):
    ≥ 44 pt tap targets via the v0.2 token contract, mobile
    keyboards (`type="datetime-local"`, `inputmode="numeric"`),
    camera capture (`<input type="file" accept="image/*"
    capture="environment">`). Photo uploads route through
    `service_crm.shared.uploads.store_upload` and re-encode to WebP
    q85 with long-edge ≤ 2048 px.
  - **Procedure search**: dialect-aware FTS (Postgres `tsvector` /
    SQLite `LIKE`) on title + summary + body, with tag filter.
  - **Markdown rendering** (`service_crm/knowledge/markdown.py`) —
    tiny hand-rolled renderer supporting headings, paragraphs,
    ordered + unordered lists, fenced code, inline code,
    `**bold**` / `*italic*`, and `[link](url)` with an allowlist of
    schemes (`http`, `https`, `mailto`); raw HTML is escaped, and
    `javascript:` / protocol-relative URLs are rejected.
  - Idempotency tokens cover every state-changing intervention,
    parts, tag, template, item, and procedure form via the existing
    `service_crm.shared.idempotency` window.
  - Sidebar gains `Knowledge` and `Parts` links; tickets detail
    grows an `Interventions` tab and "Start intervention" entry
    point.
  - **226 new tests** across `tests/tickets/test_intervention_*.py`
    and `tests/knowledge/`: models (constraints, cascades, SET NULL,
    frozen snapshots), services (CRUD, search, dialect branches via
    monkeypatched `_dialect`, run completion gate, choice-options
    validation), routes (every endpoint, idempotent retries,
    validation re-renders, cross-blueprint 404s, photo upload +
    auth-gated download), and the Markdown renderer (every
    supported feature + the link-scheme allowlist).
  - Test factories: `ServiceInterventionFactory`,
    `InterventionActionFactory`, `InterventionFindingFactory`,
    `PartMasterFactory`, `ServicePartUsageFactory`,
    `ChecklistTemplateFactory`, `ChecklistTemplateItemFactory`,
    `ChecklistRunFactory`, `ChecklistRunItemFactory`,
    `ProcedureTagFactory`, `ProcedureDocumentFactory`.
  - **RO + EN translations** for every new label, button caption,
    flash message, and form hint; catalogs compiled into the wheel.

### Fixed

- Part / procedure search on Postgres: ``plainto_tsquery`` keeps a
  hyphenated input (``part-a``) as a compound lexeme but the indexed
  ``to_tsvector`` carries the individual tokens too — the conjunction
  would never match for codes like ``X-12``. The query is now
  normalised by replacing non-word characters with spaces before
  being handed to ``plainto_tsquery`` so it tokenises the same way as
  the indexed vector. Applies to both ``part_master`` and
  ``procedure_document`` search; SQLite ``LIKE`` was already
  hyphen-safe.

### Changed

- `service_crm/__init__.py` registers the `knowledge` blueprint.
- `service_crm/tickets/__init__.py` mounts the intervention routes
  and re-exports the new models for external imports.
- `service_crm/shared/uploads.py` is now reused by intervention
  photos (scope ``interventions``), unchanged behaviour.
- `service_crm/templates/tickets/detail.html` lights up the
  `Interventions` tab (replaces the v0.5 placeholder).
- `service_crm/templates/base.html` — sidebar `Knowledge` link now
  points at `/knowledge/`; new `Parts` link added.
- `pyproject.toml` mypy override extends `arg-type` suppression to
  `tickets.intervention_routes` and `knowledge.routes`, same
  rationale as the v0.5 entry (scoped_session vs. Session).

## [0.5.0] - 2026-05-12

### Added

- **Tickets — header, history, comments, attachments** — ROADMAP 0.5.0.
  - `service_crm/tickets/` blueprint with `ServiceTicket`,
    `TicketStatusHistory` (append-only), `TicketComment`,
    `TicketAttachment`, and the `TicketType` / `TicketPriority` lookups
    seeded with the v1 codes (`incident`, `preventive`,
    `commissioning`, `warranty`, `installation`, `audit` for type;
    `low`, `normal`, `high`, `urgent` for priority). Alembic migration
    `20260512_1200_c3a4d7e8f1b9_tickets_spine.py`.
  - `service_crm/tickets/state.py` — pure-Python FSM. Lifecycle:
    `new → qualified → scheduled → in_progress → waiting_parts →
    monitoring → completed → closed`; `cancelled` from any
    pre-`completed` state. Role-based: admin and manager can drive
    every move, technician is limited to the in-progress section.
    Hypothesis state-machine test plus exhaustive property test —
    100 % line + branch on the FSM.
  - `service_crm/shared/audit.py` extended: a `before_flush` listener
    writes a `TicketStatusHistory` row on every status change, even
    when code bypasses `services.transition_ticket` and assigns
    `ticket.status` directly. The initial `from_state = NULL` row is
    written on ticket creation. Transition reason / reason_code
    metadata is stashed on the instance and consumed once per flush.
  - Routes (all `@login_required`):
    `/tickets/`, `/tickets/new`, `/tickets/<hex>`,
    `/tickets/<hex>/edit`, `/tickets/<hex>/transition`,
    `/tickets/<hex>/comments`, `/tickets/<hex>/attachments`,
    `/tickets/<hex>/attachments/<aid>` (auth-gated download),
    `/tickets/<hex>/attachments/<aid>/delete`, plus lookup admin at
    `/tickets/types[/...]` and `/tickets/priorities[/...]` (rename +
    deactivate only — new codes require a migration).
  - **Tickets list** with filters (status, type, priority, client,
    equipment, assignee, full-text search), "My queue" link in the
    toolbar, translated status / type / priority chips, pagination,
    open-vs-all view toggle, count-per-status badges. Single-column
    stacked-card layout on phones via the 0.2.0 `data_table` macro.
  - **Detail page**: header card, status pill, **transition bar**
    showing only the legal next states for the current role/state
    pair, dropdown of common cancel reasons + free-text, status
    history timeline tab, comments tab (sticky compose box,
    8 KB cap), attachments tab.
  - **Comments**: plain text only, 8 KB cap enforced at both form and
    service layer (UTF-8 byte length, so emoji-heavy bodies are caught
    correctly), soft-delete via `is_active`.
  - **Attachments**: shared upload pipeline at
    `service_crm/shared/uploads.py` — extension + magic-byte
    validation, Pillow image re-encode (WebP q85, long-edge ≤ 2048 px),
    25 MB single-file cap, stored under
    `instance/uploads/tickets/<ticket_hex>/<attachment_ulid><ext>`.
    Streamed back through an auth-gated route; never linked from
    `static/`. Soft-delete with required reason. 0.6 interventions
    will reuse the same pipeline.
  - **Idempotency**: server-side `idempotency_key` table with
    `(user_id, token)` unique constraint and 24 h window. The hidden
    `idempotency_token` field already wired into `form_shell` (from
    0.2.0) is now deduplicated server-side; double-submits return a
    "this request was already submitted" flash instead of writing
    twice. `flask sweep-idempotency` CLI command deletes expired
    rows; APScheduler integration lands in v0.7.
  - **Ticket numbering**: `ServiceTicket.number` is monotonic.
    Postgres path uses a `ticket_number_seq` sequence created on
    first use; SQLite path computes `MAX(number) + 1` inside the
    same transaction.
- **Templates**: `tickets/list.html`, `tickets/detail.html`,
  `tickets/edit.html`, `tickets/types_list.html`,
  `tickets/priorities_list.html`, `tickets/lookup_edit.html`. All
  use the 0.2.0 macros (`data_table`, `tabs`, `filter_bar`, `modal`).
- **Tickets tab on equipment detail** now shows the list of tickets
  for that machine (replaces the v0.5 placeholder), with a "New
  ticket" button that pre-populates client + equipment.
- **Sidebar Tickets link** wired up (was a `#` placeholder).
- **160+ new tests** (`tests/tickets/`): state machine (Hypothesis +
  property), models (constraints, cascades, history listener),
  services (CRUD, FSM-driven transitions, search, comments,
  attachments, lookup admin), routes (full e2e including idempotent
  retries and the auth-gated download), shared upload pipeline,
  idempotency, translations registry. 100 % line + branch coverage
  on `service_crm/`. 369 → 541 tests.
- **RO + EN translations** for every new label, status, type,
  priority, button, and flash message; catalogs compiled into the
  wheel.
- Test factories: `TicketTypeFactory`, `TicketPriorityFactory`,
  `ServiceTicketFactory`, `TicketCommentFactory`,
  `TicketAttachmentFactory`.

### Changed
- `service_crm/__init__.py` registers the tickets blueprint.
- `service_crm/cli.py` adds `flask sweep-idempotency`.
- `pyproject.toml` mypy override adds `tickets.routes` and `cli` to
  the same `arg-type` suppression as `clients.routes` and
  `equipment.routes` (db.session is `scoped_session[Session]` but
  services take `Session` — runtime compatible, statically divergent).
- `tests/test_cli.py::test_reset_db_with_yes_runs_migrations` now
  patches `db.drop_all` as well as `flask_migrate.upgrade` so it
  doesn't wipe the session-scoped in-memory schema and leave later
  tests with `no such table` errors. The bug was latent on `main`
  because no test ran against the schema after `test_cli.py`; with
  `tests/tickets/` ordered alphabetically *after* `test_cli.py`, the
  ordering broke and is now fixed.

## [0.4.0] - 2026-05-11

### Added

- **Equipment / installed-base slice** — ROADMAP 0.4.0.
  - `service_crm/equipment/` blueprint with `Equipment`,
    `EquipmentModel`, `EquipmentControllerType`, `EquipmentWarranty`
    models + Alembic migration (`20260511_1500_b9c8d2e7a4f6`).
  - Routes (all `@login_required`):
    `/equipment/`, `/equipment/new`, `/equipment/<hex>`,
    `/equipment/<hex>/edit`, `/equipment/<hex>/deactivate`,
    `/equipment/<hex>/reactivate`, warranty add/edit/delete on
    `/equipment/<hex>/warranties[/...]`,
    controller-type lookup at `/equipment/controllers[...]`,
    equipment-model lookup at `/equipment/models[...]`, and CSV imports
    at `/equipment/import`, `/equipment/controllers/import`,
    `/equipment/models/import`.
  - Constraint: `Equipment.location_id`, when set, must belong to the
    same client as `Equipment.client_id` — service-layer guard
    (`services._validate_location_belongs_to_client`), enforced on
    create and update with integration tests.
  - Constraint: `EquipmentWarranty.ends_on > starts_on` — DB CHECK
    plus service-layer guard.
  - CSV imports resolve clients / locations / models / controllers by
    human-friendly fields (no ULID hex required); each import runs
    inside a SAVEPOINT so a complete failure leaves the request session
    clean.
  - Detail page tabs: warranties (functional) plus tickets / maintenance
    placeholders, ready for 0.5 and 0.7.
  - Postgres GIN expression-index on `serial_number + asset_tag` for
    full-text search, mirroring the clients pattern.
- Test factories: `ControllerTypeFactory`, `EquipmentModelFactory`,
  `EquipmentFactory`, `EquipmentWarrantyFactory`.
- **125 new tests** (`tests/equipment/`): models (cascade / SET NULL /
  unique / CHECK / labels), services (CRUD, search, location-belongs-
  to-client guard, CSV imports), routes (full e2e).
- Sidebar now links to `/equipment/` (previously a placeholder `#`).
- RO + EN translations for every new label and flash message.

## [0.2.0] - 2026-05-11

### Added
- **UI foundation (mobile-first, light-default)** — ROADMAP 0.2.0 step 7.
  - `service_crm/templates/base.html` shell: left sidebar grouped by
    section (Overview / Operations / Catalogue / Admin), topbar with
    breadcrumb + page title, clock, notifications, theme toggle, RO/EN
    switch. Collapses to a slide-over drawer below 900 px.
  - `service_crm/templates/partials/theme_init.html` — pre-paint theme
    bootstrap (localStorage → `prefers-color-scheme` → `light`).
  - `service_crm/static/css/style.css` — tokens (`--bg`, `--surface`,
    `--surface-2`, `--border`, `--text`, `--text-muted`, `--accent`,
    `--good`, `--fair`, `--poor`, `--first-off`, `--font-body`,
    `--font-mono`, `--tap-min`), component classes (`.btn`,
    `.oee-card`, `.data-table`, `.table-scroll`, `.table-stacked`,
    `.filter-bar`, `.chip`, `.form-shell`, `.tabs`, `.modal-*`,
    `.status-pill`, `.live-pill`, `.alert-first-off`). Every
    interactive class declares ≥ 44 pt tap targets via `--tap-min`.
  - Jinja macros under `service_crm/templates/macros/`: `kpi_card`,
    `data_table` (with stacked-card fallback below 640 px), `filter_bar`,
    `form_shell` (carries the idempotency-token hidden input),
    `tabs`, `modal`, plus an inline Lucide `icon()` macro. The
    directory is *not* underscore-prefixed because Babel skips
    `_*` directories at extract time.
  - `service_crm/static/js/app.js` — tiny shell behaviours (clock,
    theme toggle, mobile nav drawer, service-worker registration with
    skip-waiting + reload path).
- **PWA-light scaffolding** — ROADMAP 0.2.0:
  - `service_crm/static/manifest.webmanifest` — `name`, `short_name`,
    `start_url`, `scope`, `display: standalone`, `orientation`,
    `theme_color` `#dc2626`, `background_color` `#f5f5f4`, three icons
    (192, 512, maskable-512).
  - `service_crm/static/service-worker.js` — versioned cache key tied
    to `VERSION`, app-shell precache, cache-first for `/static/`,
    network-first for navigations with offline-shell fallback, **no
    write-side caching** (writes pass straight through). Skip-waiting
    message handler so a bad SW can't pin users on stale assets.
  - `service_crm/static/icons/` — placeholder SVG + 192/512/maskable
    PNGs (replace before tagging `v1.0.0`).
- **Dev-only `/dev/macro-smoke` page** — renders every macro with
  placeholder data so consistency passes and visual reviews have a
  single anchor. Blueprint mounts only under `DEBUG` or `TESTING`.
- **Tests** — 23 new e2e tests:
  - `tests/e2e/test_macro_smoke.py` — base shell, PWA links, each
    macro's anchor element, manifest + service-worker + icons served.
  - `tests/e2e/test_touch_targets.py` — static CSS audit of the
    `--tap-min` token contract on every interactive class.
  - `tests/e2e/test_dev_blueprint.py` — dev blueprint mounted under
    `DEBUG`/`TESTING`, skipped otherwise.

### Changed
- `service_crm/__init__.py` registers the dev blueprint conditionally.
- `docs/ui-reference.md` records that the 0.2.0 foundation is a
  reconstruction from the design tokens, OLSTRAL guidelines, and a
  screenshot — not a verbatim vendor copy. The OEE source repository
  was not reachable from CI / the sandboxed session at implementation
  time; if it becomes reachable, a follow-up pass should diff the
  vendored shell against the current files and reconcile.

## [0.1.0] - 2026-05-11

### Added
- **Auth slice — login / logout** (`service_crm/auth/routes.py`,
  `forms.py`, `templates/auth/login.html`). Flask-WTF ``LoginForm`` with
  email + password, Argon2id verify, ``last_login_at`` stamped on
  success, audit event for that update carries the actor. Logout via
  ``GET /auth/logout`` is ``@login_required``. The login page is a
  bare standalone template with inline CSS and an inline RO/EN
  language switch — placeholder for v0.1.0; rewritten to extend
  ``base.html`` in v0.2.0 once the OEE shell is vendored.
- **Flask-Babel + RO/EN i18n** wired end-to-end:
  ``service_crm/i18n.py`` selects locale by user pref → ``?lang=`` →
  ``Accept-Language`` → ``BABEL_DEFAULT_LOCALE`` (default ``ro``).
  Catalogs at ``service_crm/locale/{ro,en}/LC_MESSAGES/messages.po``,
  bundled into the wheel via ``hatch.artifacts``. ``babel.cfg`` at the
  repo root. ``/healthz`` and ``/version`` return a translated
  ``message`` field that differs per locale; ``?lang=ro`` and
  ``?lang=en`` smoke-tested.
- **CLI**: ``flask babel-extract`` / ``babel-update`` / ``babel-compile``
  thin wrappers around ``pybabel`` so contributors don't memorise the
  long invocations.
- **Audit-context middleware**: ``auth.before_app_request`` stashes a
  per-request id (``uuid4().hex[:12]``) and the acting user's id
  into the ``ACTOR_CTX`` / ``REQUEST_ID_CTX`` context vars, so every
  audit event from this point forward carries them. After login the
  route explicitly refreshes ``ACTOR_CTX`` so the ``last_login_at``
  write is attributed correctly.
- **Flask-Login wiring**: ``user_loader`` accepts a hex-encoded ULID
  and looks up the user; ``UserMixin`` mixed in on ``User`` so
  ``current_user`` works end-to-end.
- **Tests**: 32 new tests cover the locale selector, login GET/POST
  happy + sad paths (wrong password, unknown email, inactive user,
  empty form, ``?next=``), logout, the ``user_loader`` (valid hex,
  unknown id, malformed input), the audit-context middleware, the
  translated ``/healthz``+``/version`` payloads, and the new Babel
  CLI commands. Suite size: 78 → 110.

### Changed
- ``service_crm/extensions.py`` gains ``babel = Babel()`` and a locale
  selector callback.
- ``service_crm/config.py`` adds ``BABEL_DEFAULT_LOCALE``,
  ``BABEL_DEFAULT_TIMEZONE``, ``BABEL_TRANSLATION_DIRECTORIES``.
- ``pyproject.toml`` adds ``email-validator>=2.0`` (required by
  ``wtforms.validators.Email``).
- ``tests/conftest.py``: the session-scoped ``app`` fixture no longer
  keeps an outer ``app_context`` open — Flask binds ``g`` to the app
  context, so a session-long context shared ``g`` across every
  ``client.get()`` and silently locked Flask-Babel's per-request
  locale resolution. ``db_session`` now pushes its own context.


- **`auth` blueprint — model layer.** `User` (`user_account` table) and
  `Role` (`role` table), both inheriting `Auditable`. `User` has ULID PK,
  case-insensitive unique email (functional index on `lower(email)`,
  works on Postgres and SQLite), Argon2 password hash column, FK to
  `Role` with `ON DELETE RESTRICT`, optional `preferred_language`
  (RO/EN — wired in the auth-slice PR), optional `last_login_at`.
- **First Alembic revision** (`40b50949771c`) — creates `user_account`,
  `role`, `audit_event`, plus the three seeded roles (`admin`,
  `manager`, `technician`). Round-trips cleanly on SQLite.
- **`service_crm/auth/services.py`** — pure helpers: Argon2id
  `hash_password` / `verify_password` and `normalize_email`. Routes,
  forms and login template land with `/module-slice auth`.
- **DB-aware test fixtures** in `tests/conftest.py`: `db_engine`,
  `db_session` (SAVEPOINT-and-rollback, rebinds the global
  `db.session` so factory writes share the transaction),
  `client_logged_in` (seeds an admin row; full login wiring lands with
  the slice). SQLite connections auto-enable `PRAGMA foreign_keys = ON`
  so `ON DELETE RESTRICT` actually fires in tests.
- **`tests/factories.py`** — `UserFactory` (defaults to the seeded
  `technician` role, hashes a default `"test-pass"` password) and
  `RoleFactory`. Email normalised on construction.
- **End-to-end audit-listener tests** now that real models exist:
  create / update / delete events recorded, before/after captured from
  `state.get_history`, actor + request id read from `contextvars` when
  set.

### Changed
- `migrations/env.py` — drop the `render_as_batch=` duplicate kwarg
  (Flask-Migrate already injects it via `init_app`), and switch the
  `get_engine()` helper to the `.engine` attribute that Flask-SQLAlchemy
  3.x prefers (the legacy method is removed in 3.2).

- `docs/blueprint.md` — user-pasted CNC Service & Maintenance App
  blueprint, saved verbatim as the long-form product source-of-truth.
- `docs/adr/0001-flask-vs-fastapi.md` — accepted: Flask wins for v1.
  Reasoning around forms, auth, i18n, and the OEE-vendored UI.
- `docs/v1-implementation-goals.md` — the v1.0 production-ready and
  phone-ready bars. Concrete acceptance criteria per milestone, plus a
  release exit checklist. v1 mobile scope locked at "PWA-light":
  responsive + installable, online required for writes, full offline
  write queue deferred to v1.2.
- `python.tests.md` §13 — mobile / PWA testing strategy: touch-target
  audit (Playwright), Lighthouse-CI budgets, real-device pass per
  release, service-worker cache-invalidation tests.
- `python.tests.md` §14 — i18n testing strategy: locale-selector tests,
  no-hardcoded-strings template walk, catalog freshness CI gate, layout
  audit at 320 px in both languages.
- ARCHITECTURE.md §5.1 — Mobile / PWA architecture (manifest, service
  worker, responsive macros, idempotency tokens).
- ARCHITECTURE.md cross-cutting i18n entry; ADR-0007 (PWA-light) and
  ADR-0008 (RO/EN day-one) placeholders.
- **First application code lands.** Walking-skeleton foundation for v0.1.0:
  - `service_crm/` package: `create_app()` factory (`__init__.py`),
    extensions (`extensions.py`), Flask config classes (`config.py`),
    Flask CLI commands (`cli.py`), JSON error handlers (`errors.py`),
    `/healthz` and `/version` blueprint (`health.py`).
  - `service_crm/shared/`: mockable `clock.now()`, ULID type that stores
    as native UUID on Postgres and `BLOB(16)` on SQLite, `Auditable`
    mixin and `AuditEvent` model wired through a `before_flush` listener.
  - Alembic scaffolding (`migrations/env.py`, `script.py.mako`,
    `alembic.ini`) with `render_as_batch=True` on SQLite.
  - `tests/conftest.py` with `app`, `client`, and `frozen_clock`
    fixtures; 58 unit tests covering the foundation surface exhaustively.
  - `Dockerfile`, `docker-compose.yml`, `.dockerignore`,
    `.pre-commit-config.yaml`.
- `.claude/skills/` — five project-level Claude Code skills mirroring the
  workflows in `docs/tasks.md`: `architecture-audit`, `ui-foundation`,
  `data-model`, `module-slice`, `consistency-pass`.
- `docs/commands.md` — concrete Flask / pytest / Alembic commands
  (PowerShell + bash) replacing the placeholder version.

### Changed
- CI matrix extended to `db: [sqlite, postgres]`; the Postgres leg uses a
  `postgres:15` service container and runs the same suite via
  `DATABASE_URL`. Mypy strict and the full pytest run are now
  unconditional (the planning-phase "skip if no service_crm/" stub is
  removed).
- Coverage gate raised from 85% to **100%** (line + branch). 58 tests
  cover the foundation surface exhaustively, including the
  `_read_version_file` fallback, the `service-crm-cli` console-script
  entry, every config helper branch, the JSON 500 and HTTPException
  handlers, the audit listener's non-Auditable / NO_VALUE / skip-keys
  paths, and the ULID dialect impls.
- Dropped `pydantic` and `pydantic-settings` from `pyproject.toml` —
  config is plain Flask classes per the approved architecture plan §3.1.
- `docs/architecture-plan.md` — **approved 2026-05-10**. Status header,
  open-questions section, and downstream pointers in `README.md`,
  `ROADMAP.md`, and `ARCHITECTURE.md` updated to reflect sign-off.
  Implementation of the 0.1.0 walking skeleton begins from this baseline.
- Stack realigned to **Flask + Jinja + SQLAlchemy + Alembic + pytest**
  (was FastAPI + HTMX in the prior planning round). Drives matching
  rewrites of `ARCHITECTURE.md`, `ROADMAP.md`, `python.tests.md`, and
  `pyproject.toml`. Confirmed in `docs/adr/0001-flask-vs-fastapi.md`.
- Domain model **adopted in full from `docs/blueprint.md` §8** — adds
  `EquipmentModel`, `EquipmentControllerType`, `EquipmentWarranty`,
  `ServiceContract`, `TicketStatusHistory`, `TicketComment`,
  `TicketAttachment`, `TicketType`, `TicketPriority`,
  `InterventionAction`, `InterventionFinding`, `PartMaster`,
  `MaintenanceTemplate`, `MaintenanceTask`, `MaintenanceExecution`,
  `ChecklistTemplateItem`, `ChecklistRunItem`, `ProcedureTag`,
  `Technician`, `TechnicianAssignment`, `TechnicianCapacitySlot` to
  the prior generic set.
- Ticket lifecycle replaced: `new → qualified → scheduled → in_progress
  → waiting_parts → monitoring → completed → closed`, `cancelled` from
  any pre-`completed` state. Was `open → … → resolved → closed`.
- Two new blueprints — `planning` (technicians + capacity) and
  `dashboard` (manager + technician views).
- `ROADMAP.md` milestones reordered around the eight blueprints and the
  sequence in `docs/tasks.md`. 0.5 split into 0.5 (ticket header /
  history / comments / attachments) and 0.6 (interventions / parts /
  knowledge). 0.7 now bundles maintenance + planning. Beyond-1.0 sketch
  promotes the CNC-specific enhancements to v1.3.
- 0.9.0 hardening checklist replaced with a direct mapping to the bars
  in `docs/v1-implementation-goals.md` §1–§3.
- `docs/service-domain.md` adopted the full CNC entity list, the new
  ticket lifecycle, and the eight-blueprint module map.
- User-supplied support docs moved from repo root into `docs/` to match
  the links in `AGENTS.md`.
- `pyproject.toml` adds Flask-Babel + Babel + APScheduler + Pillow.
- `docs/commands.md` gains a "Translations" section with `pybabel`
  flow.
- `README.md` rewritten as a "Start here" index pointing at `AGENTS.md`,
  the docs/, and the project skills; subsequently expanded to list
  `v1-implementation-goals` as required reading.
- `.claude/skills/ui-foundation/SKILL.md`,
  `.claude/skills/consistency-pass/SKILL.md`, and
  `.claude/skills/data-model/SKILL.md` updated with the mobile / PWA,
  i18n, lookup-table, and CNC-domain rules.

### Decisions
- 2026-05-10: Flask wins over FastAPI for v1
  (`docs/adr/0001-flask-vs-fastapi.md`).
- 2026-05-10: bilingual RO+EN from day one, RO default; Flask-Babel
  scaffold lands in 0.1.0 walking skeleton.
- 2026-05-10: adopt the blueprint's CNC domain in full.

[Unreleased]: https://github.com/vladutzeloo/service-crm/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/vladutzeloo/service-crm/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/vladutzeloo/service-crm/compare/v0.2.0...v0.5.0
[0.2.0]: https://github.com/vladutzeloo/service-crm/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/vladutzeloo/service-crm/releases/tag/v0.1.0

[//]: # (v0.3.0 [clients] and v0.4.0 [equipment] were merged to ``main`` but)
[//]: # (never tagged; their work is rolled into the v0.5.0 release range.)
