# AGENTS.md

## Assumptions

- This repository is the standalone `service-crm` app.
- The legacy context source is `service-app-context-pack.md`.
- Exact `oee-calculator2.0` source links are still placeholders until filled in.
- Architecture must be approved before app code is written.
- This app may later integrate with VMES/OEE, but v1 must not couple directly to those codebases.

## Project Truth

- Build a standalone Flask/Jinja service-management app.
- Keep standalone code, database, auth, migrations, tests, and deployment path.
- Reuse the UI language from `oee-calculator2.0`.
- Do not import business logic from `oee-calculator2.0`.
- Keep AI memory tooling outside the Flask runtime.
- Default to light mode.
- Build compact, Power BI-like operational dashboards.
- Use Flask, Jinja, SQLAlchemy, Alembic, and pytest.
- Prefer architecture first, code second.

## Required Reading

- UI source of truth: [docs/ui-reference.md](docs/ui-reference.md)
- Service domain and workflows: [docs/service-domain.md](docs/service-domain.md)
- Implementation sequence: [docs/tasks.md](docs/tasks.md)
- Run/test/lint commands: [docs/commands.md](docs/commands.md)
- Optional AI memory layer: [docs/obsidian-brain.md](docs/obsidian-brain.md)

## Operating Rules

- Explore the repo before changing files.
- Use Obsidian Mind only as an external agent-memory vault, not as app code.
- Stop and list assumptions when requirements are ambiguous.
- Do not code before architecture is agreed for new modules or large changes.
- Keep routes thin.
- Put business logic in service-layer modules.
- Keep templates simple and consistent with existing patterns.
- Add or update tests for behavior, relationships, constraints, and regressions.
- Keep changes narrowly targeted to the requested task.
- Do not introduce unrelated refactors.
- Do not replace the chosen stack.
- Do not suggest React, Next.js, SPA conversion, or a new frontend framework.

## Architecture Rules

- Use clear service modules:
  - `clients`
  - `equipment`
  - `tickets`
  - `maintenance`
  - `knowledge`
- Use SQLAlchemy models for persistence.
- Use Alembic for schema migrations.
- Use pytest for tests.
- Use API or sync jobs for future VMES/OEE integrations.
- Do not create direct code or database coupling with VMES/OEE in v1.
- Prefer explicit file ownership for refactors.
- Make migrations reviewable and reversible where practical.

## UI Rules

- Follow `oee-calculator2.0` exactly where referenced in [docs/ui-reference.md](docs/ui-reference.md).
- Do not invent a new design system.
- Do not add arbitrary component libraries.
- Do not use gradient-heavy, neon, decorative, or marketing-style UI.
- Do not use emoji icons.
- Avoid left sidebars in main technician screens.
- Keep dashboards compact, dense, scannable, and operational.
- Use the existing visual vocabulary for:
  - shell and topbar
  - cards and KPI blocks
  - tables
  - forms
  - filters
  - tabs
  - detail pages

## Task Split: GPT-5.5 / Codex vs Claude

### Use GPT-5.5 / Codex For

- Architecture cleanup.
- File-structure planning.
- Refactors with strict file targeting.
- SQLAlchemy models.
- Alembic migrations.
- CRUD routes.
- Forms.
- Tables.
- Filters.
- Test scaffolding.
- Consistency passes.
- `AGENTS.md` and task-file maintenance.

### Use Claude For

- Larger architectural critique.
- Product and feature brainstorming.
- UX critique and workflow thinking.
- Reviewing whether new modules fit the broader VMES/OEE roadmap.
- Generating alternative implementation options before coding.

### Collaboration Rule

- Ask Claude before coding when the product direction, workflow, or VMES/OEE roadmap fit is unclear.
- Use GPT-5.5 / Codex to implement once architecture and scope are clear.
- GPT-5.5 / Codex must not invent UI for design implementation.
- GPT-5.5 / Codex must follow the exact referenced `oee-calculator2.0` files.

## Major Structural Changes From Old Context

- Root context is now short, imperative, and always-loadable.
- UI source links moved to [docs/ui-reference.md](docs/ui-reference.md).
- Business modules and workflows moved to [docs/service-domain.md](docs/service-domain.md).
- Implementation sequencing moved to [docs/tasks.md](docs/tasks.md).
- Run/test/lint commands moved to [docs/commands.md](docs/commands.md).
- Obsidian Mind guidance moved to [docs/obsidian-brain.md](docs/obsidian-brain.md).
- Human-only explanation, citations, and generic skill guidance were removed.
- Delegation rules are now explicit.

## Maintenance Rules

- Update [docs/ui-reference.md](docs/ui-reference.md) when source UI files change.
- Update [docs/commands.md](docs/commands.md) when run/test/lint commands change.
- Update [docs/tasks.md](docs/tasks.md) when implementation order changes.
- Update [docs/service-domain.md](docs/service-domain.md) when service workflows or module scope changes.
- Update [docs/obsidian-brain.md](docs/obsidian-brain.md) when memory-vault setup changes.
- Keep this root file lean.
- Avoid duplicating detailed rules across support docs.

## Recommended Next Prompt

```text
Read AGENTS.md first.
Then read docs/ui-reference.md, docs/service-domain.md, docs/tasks.md, and docs/commands.md.
Do not write app code yet.
Audit the current repo and the referenced oee-calculator2.0 UI files.
List assumptions, propose the standalone architecture, propose the first SQLAlchemy model set, and identify which files should be created or adapted.
Wait for approval before implementation.
```
