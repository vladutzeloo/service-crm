# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

The release workflow (`.github/workflows/release.yml`) extracts the section
matching the pushed tag (e.g. `v0.1.0` → `## [0.1.0]`) and uses it as the
GitHub Release body. Keep entries terse, user-facing, and grouped under the
standard headings: **Added / Changed / Deprecated / Removed / Fixed / Security**.

## [Unreleased]

## [0.4.0] - 2026-05-12

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

## 0.3.0 - 2026-05-11

### Added
- **Clients blueprint — full CRUD** (`service_crm/clients/`) — ROADMAP 0.3.0.
  - `Client`, `Contact`, `Location`, `ServiceContract` models with `Auditable`
    mixin; ULID PKs; all FKs with `ON DELETE CASCADE`.
  - `ServiceContract` carries a `CHECK (ends_on IS NULL OR ends_on > starts_on)`
    constraint enforced at the DB level and at the service layer.
  - Soft-delete via `Client.is_active`; service history (contacts,
    locations, contracts) remains queryable after deactivation.
  - Service layer (`services.py`): `create/update/deactivate/reactivate_client`,
    `list_clients` (pagination + search), `require_client/contact/location/contract`,
    CRUD for contacts / locations / contracts, `import_clients_csv`.
  - Cross-dialect search: Postgres uses `to_tsvector('simple', …)` / `plainto_tsquery`
    with a GIN index on `(name || email || phone)`; SQLite falls back to
    case-insensitive `LIKE` (adequate for dev/test volumes).
  - Alembic migration `8f3a2c1d4e5b` — client-domain tables + Postgres GIN index.
  - UI: list page with search/filter bar, paginated `data_table`; detail page
    with Contacts / Locations / Contracts tabs, inline add/edit modals;
    edit page; CSV import page — all extending `base.html` and using the
    0.2.0 macros.
  - CSV import: case-insensitive header normalisation; per-row error reporting.
  - Flask-WTF forms with `prefix=` for each sub-entity modal.
  - All form labels, flash messages, and nav strings translated (RO + EN).
  - **100 tests** across `test_models.py`, `test_services.py`, `test_routes.py`:
    cascade deletes, `back_populates` round-trips, date CHECK constraint,
    soft-delete, `__repr__` coverage, search both dialects (monkeypatched),
    all guard-raise paths, CSV import edge cases, every route happy/sad path.
  - Coverage: 100 % line + branch on both SQLite and Postgres CI legs.

### Changed
- `pyproject.toml` — added `[[tool.mypy.overrides]]` for `service_crm.clients.routes`
  to suppress `arg-type` noise from `scoped_session` / `Session` type divergence
  (compatible at runtime; suppressed per-module rather than globally).
- `tests/conftest.py` — `client_logged_in` no longer hard-codes
  `email="admin@example.com"`; uses the factory sequence to avoid
  `UNIQUE` constraint failures across parallel test runs.

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

[Unreleased]: https://github.com/vladutzeloo/service-crm/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/vladutzeloo/service-crm/compare/v0.2.0...v0.4.0
[0.2.0]: https://github.com/vladutzeloo/service-crm/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/vladutzeloo/service-crm/releases/tag/v0.1.0
