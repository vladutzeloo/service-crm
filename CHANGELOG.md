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
- Project planning documents: `ARCHITECTURE.md`, `ROADMAP.md`, `python.tests.md`.
- Release workflow scaffolding under `.github/workflows/`.
- `pyproject.toml` and `VERSION` stubs.

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
