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
- **First application code lands.** Walking-skeleton foundation for v0.1.0:
  - `service_crm/` package: `create_app()` factory (`__init__.py`),
    extensions (`extensions.py`), Flask config classes (`config.py`),
    Flask CLI commands (`cli.py`), JSON error handlers (`errors.py`),
    `/healthz` and `/version` blueprint (`health.py`).
  - `service_crm/shared/`: mockable `clock.now()`, ULID type that stores
    as native UUID on Postgres and `BLOB(16)` on SQLite, `Auditable`
    mixin and `AuditEvent` model wired through a `before_flush` listener.
  - Alembic scaffolding (`migrations/env.py`, `script.py.mako`,
    `alembic.ini`) with `render_as_batch=True` on SQLite. No revisions
    yet — first revision lands with the auth data-model PR.
  - `tests/conftest.py` with `app`, `client`, and `frozen_clock`
    fixtures; unit tests covering the factory, CLI, healthcheck, error
    handlers, clock, ULID encode/decode and time-prefix ordering, and
    the `Auditable`/`AuditEvent` shape.
  - `Dockerfile` (`python:3.12-slim` + `libpq5` + `gunicorn`),
    `docker-compose.yml` (Postgres 15 + app + auto-`db upgrade`),
    `.dockerignore`.
  - `.pre-commit-config.yaml` running `ruff check --fix`,
    `ruff format`, and `pytest -m unit`.
- `docs/architecture-plan.md` — synthesized architectural proposal awaiting
  approval (assumptions, model set, file list, open questions).
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
- Dropped `pydantic` and `pydantic-settings` from `pyproject.toml` —
  config is plain Flask classes per the approved architecture plan §3.1.
- `docs/architecture-plan.md` — **approved 2026-05-10**. Status header,
  open-questions section, and downstream pointers in `README.md`,
  `ROADMAP.md`, and `ARCHITECTURE.md` updated to reflect sign-off.
  Implementation of the 0.1.0 walking skeleton begins from this baseline.
- Stack realigned to **Flask + Jinja + SQLAlchemy + Alembic + pytest**
  (was FastAPI + HTMX in the prior planning round). Drives matching
  rewrites of `ARCHITECTURE.md`, `ROADMAP.md`, `python.tests.md`, and
  `pyproject.toml`.
- Domain model realigned to the entities in `docs/service-domain.md`
  (`Client`, `Contact`, `Location`, `Equipment`, `ServiceTicket`,
  `ServiceIntervention`, `ServicePartUsage`, `ChecklistTemplate`,
  `ChecklistRun`, `ProcedureDocument`) grouped under the five blueprints
  in `AGENTS.md`.
- `ROADMAP.md` milestones reordered around the five blueprints and the
  sequence in `docs/tasks.md`.
- User-supplied support docs moved from repo root into `docs/` to match
  the links in `AGENTS.md`.
- `README.md` rewritten as a "Start here" index pointing at `AGENTS.md`,
  the docs/, and the project skills.

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
