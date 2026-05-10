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

### Changed
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
