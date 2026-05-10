# service-crm

Standalone, self-hostable **Flask** CRM for **CNC service teams** —
clients, equipment (machines + controllers + warranties), tickets,
interventions, parts, checklists, procedures, maintenance planning,
technician capacity, and operational dashboards. UI design language is
reused verbatim from
[`vladutzeloo/oee-calculator2.0`](https://github.com/vladutzeloo/oee-calculator2.0).

Runs on **desktop and on phones** (PWA-light: responsive + installable;
see [`docs/v1-implementation-goals.md` §2](./docs/v1-implementation-goals.md#2-the-v10-phone-ready-bar)).
Bilingual from day one — **Romanian (default) + English**.

> **Status: planning.** No application code has shipped yet. The first
> runnable version is `0.1.0` on the [roadmap](./ROADMAP.md). All
> architectural decisions go through
> [`docs/architecture-plan.md`](./docs/architecture-plan.md) before any
> code lands.

## Start here

1. [`AGENTS.md`](./AGENTS.md) — always-loadable agent context. Read first.
2. [`docs/architecture-plan.md`](./docs/architecture-plan.md) — current
   architectural proposal awaiting approval.
3. [`docs/v1-implementation-goals.md`](./docs/v1-implementation-goals.md) —
   the v1.0 production-ready and phone-ready bars. Concrete acceptance
   criteria per milestone.
4. [`docs/service-domain.md`](./docs/service-domain.md) — entities,
   workflows, modules.
5. [`docs/ui-reference.md`](./docs/ui-reference.md) — pattern map between
   `oee-calculator2.0` and this app.
6. [`docs/tasks.md`](./docs/tasks.md) — implementation sequence and prompt
   templates.
7. [`docs/commands.md`](./docs/commands.md) — install, run, test, migrate.

## Reference docs

- [`docs/blueprint.md`](./docs/blueprint.md) — long-form CNC product blueprint.
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — stack, layout, layering rules,
  cross-cutting decisions.
- [`ROADMAP.md`](./ROADMAP.md) — versioned milestones, `0.1.0 → 1.0.0`.
- [`python.tests.md`](./python.tests.md) — testing strategy: layers,
  fixtures, coverage gate, property-based tests, mobile + i18n tests.
- [`CHANGELOG.md`](./CHANGELOG.md) — Keep-a-Changelog log of every release.
- [`docs/adr/`](./docs/adr/) — Architecture Decision Records (ADR-0001
  pinned the Flask choice).
- [`docs/obsidian-brain.md`](./docs/obsidian-brain.md) — optional external
  AI memory vault (not part of the app).
- [`.github/RELEASING.md`](./.github/RELEASING.md) — how to cut a release.

## Claude Code skills

Project-level skills under [`.claude/skills/`](./.claude/skills/) codify
the workflows in [`docs/tasks.md`](./docs/tasks.md):

| Skill | What it does |
| --- | --- |
| [`/architecture-audit`](./.claude/skills/architecture-audit/SKILL.md) | Plan-only audit of a new module or refactor. |
| [`/ui-foundation`](./.claude/skills/ui-foundation/SKILL.md) | Vendor / extend the shared UI shell from oee-calculator2.0. |
| [`/data-model`](./.claude/skills/data-model/SKILL.md) | SQLAlchemy models + Alembic migration + tests. |
| [`/module-slice`](./.claude/skills/module-slice/SKILL.md) | One blueprint's vertical slice (routes + services + templates + tests). |
| [`/consistency-pass`](./.claude/skills/consistency-pass/SKILL.md) | Pre-merge review against UI / layering / coverage rules. |

See [`.claude/skills/README.md`](./.claude/skills/README.md) for invocation
notes and the Claude / Codex split from [`AGENTS.md`](./AGENTS.md).

## Stack at a glance

Python 3.11+ · Flask · Jinja2 · SQLAlchemy + Flask-SQLAlchemy ·
Alembic via Flask-Migrate · Flask-Login + Argon2 · Flask-WTF · PostgreSQL
(SQLite for dev/test) · pytest. See [`ARCHITECTURE.md` §3](./ARCHITECTURE.md#3-stack)
for the rationale.

## Releases

Tagging `vX.Y.Z` triggers `.github/workflows/release.yml`, which validates
that `VERSION` and `CHANGELOG.md` agree with the tag, runs the suite,
builds the artifacts, and publishes a GitHub Release. Pre-1.0 tags are
marked as pre-releases automatically.

## License

MIT (see `pyproject.toml`).
