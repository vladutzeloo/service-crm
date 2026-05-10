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
- `docs/architecture-plan.md` — synthesized architectural proposal awaiting
  approval (assumptions, model set, file list, open questions).
- `.claude/skills/` — five project-level Claude Code skills mirroring the
  workflows in `docs/tasks.md`: `architecture-audit`, `ui-foundation`,
  `data-model`, `module-slice`, `consistency-pass`.
- `docs/commands.md` — concrete Flask / pytest / Alembic commands
  (PowerShell + bash) replacing the placeholder version.

### Changed
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
