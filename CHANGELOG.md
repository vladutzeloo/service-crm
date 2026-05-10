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
- `docs/v1-implementation-goals.md` — the v1.0 production-ready and
  phone-ready bars. Concrete acceptance criteria per milestone, plus a
  release exit checklist. v1 mobile scope locked at "PWA-light":
  responsive + installable, online required for writes, full offline
  write queue deferred to v1.2.
- `python.tests.md` §13 — mobile / PWA testing strategy: touch-target
  audit (Playwright), Lighthouse-CI budgets, real-device pass per
  release, service-worker cache-invalidation tests.
- ARCHITECTURE.md §5.1 — Mobile / PWA architecture (manifest, service
  worker, responsive macros, idempotency tokens).
- ADR-0007 placeholder: PWA-light in v1, offline writes in v1.2.

### Changed
- ROADMAP.md milestones thread mobile/PWA through 0.2.0 (UI foundation),
  0.5.0 (tickets — phone-first slice), 0.8.0 (dashboards), 0.9.0
  (hardening).
- 0.9.0 hardening checklist replaced with a direct mapping to the bars
  in `docs/v1-implementation-goals.md` §1–§3.
- `.claude/skills/ui-foundation/SKILL.md` and
  `.claude/skills/consistency-pass/SKILL.md` updated with the mobile /
  PWA hard rules and pre-merge checklist items.
- README "Start here" lists v1-implementation-goals as required reading.

### Changed
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
