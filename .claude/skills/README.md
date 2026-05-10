# Project Claude Skills

Project-level [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills)
that codify the workflows in [`docs/tasks.md`](../../docs/tasks.md). Each
skill is invokable as `/<skill-name>` and assumes you've already read
[`AGENTS.md`](../../AGENTS.md).

| Skill | When to invoke | Outputs code? |
| --- | --- | --- |
| [`/architecture-audit`](./architecture-audit/SKILL.md) | New module, large refactor, or before any 0.x → 0.x bump that adds a blueprint. | **No.** Plan only. |
| [`/ui-foundation`](./ui-foundation/SKILL.md) | Implementing the shared UI shell (base.html, css tokens, macros) or extending it. | Yes — templates + CSS only, no business logic. |
| [`/data-model`](./data-model/SKILL.md) | Adding or changing SQLAlchemy models / Alembic migrations. | Yes — models, migrations, model tests. |
| [`/module-slice`](./module-slice/SKILL.md) | Implementing a vertical slice of a single blueprint (e.g. tickets, equipment). Pass the blueprint name as an argument. | Yes — routes, services, templates, tests for that one blueprint. |
| [`/consistency-pass`](./consistency-pass/SKILL.md) | Before merging a feature PR, or after a stretch of slicing work. | No code; review report + small fixes. |

## Why these skills exist

[`AGENTS.md`](../../AGENTS.md) §"Task Split" assigns Claude to architectural
critique, brainstorming, UX critique, and option generation — and assigns
GPT-5/Codex to implementation. The skills above reflect that split:

- `architecture-audit` and `consistency-pass` are pure Claude work.
- `ui-foundation`, `data-model`, and `module-slice` are *implementation*
  skills. They are intended for whoever runs the work (Claude in
  pair-programming mode, or Codex following the same playbook) and they
  enforce the project's UI/architecture rules so that implementer can't
  drift.

## Anchors every skill must respect

Every skill repeats these as guardrails. They come from
[`AGENTS.md`](../../AGENTS.md) and [`docs/ui-reference.md`](../../docs/ui-reference.md):

- Stack is **Flask + Jinja + SQLAlchemy + Alembic + pytest**. No FastAPI,
  no SPA, no React, no component libraries.
- UI is **vendored from `oee-calculator2.0`** per
  [`docs/ui-reference.md`](../../docs/ui-reference.md). Do not invent a new
  design language. Light mode default. No emoji. No left sidebar on
  technician screens.
- The five blueprints are `auth`, `clients`, `equipment`, `tickets`,
  `maintenance`, `knowledge`, plus the cross-cutting `dashboard` and
  `shared`. Anything else needs an architecture-audit first.
- Routes are thin; services own the ORM.
- Soft-delete preferred over hard delete for any entity with history.
- Tests required for new behavior, relationships, and constraints.
- Stop and list assumptions when requirements are ambiguous; never code
  before architecture is agreed.

## Updating skills

When the workflow in [`docs/tasks.md`](../../docs/tasks.md) changes, update
the matching skill. Keep skills short — they are an instruction sheet, not
a tutorial. If a skill grows past ~150 lines, split it.
