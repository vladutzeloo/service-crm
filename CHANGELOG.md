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

<!--
Future release sections look like this:

## [0.1.0] - YYYY-MM-DD

### Added
- ...

### Fixed
- ...

[Unreleased]: https://github.com/vladutzeloo/service-crm/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/vladutzeloo/service-crm/releases/tag/v0.1.0
-->

[Unreleased]: https://github.com/vladutzeloo/service-crm/commits/main
