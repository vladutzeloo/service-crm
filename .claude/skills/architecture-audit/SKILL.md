---
name: architecture-audit
description: Run when the user asks to plan a new module, audit the architecture, propose a structural change, or invokes /architecture-audit. Produces a written plan; writes NO application code.
---

# Architecture Audit

Codifies the "Architecture Only" workflow from
[`docs/tasks.md`](../../../docs/tasks.md).

## Inputs (read these first, in order)

1. [`AGENTS.md`](../../../AGENTS.md) — project truth, operating rules,
   architecture rules, task split.
2. [`docs/ui-reference.md`](../../../docs/ui-reference.md) — what the UI
   must look like.
3. [`docs/service-domain.md`](../../../docs/service-domain.md) — entities
   and workflow expectations.
4. [`ARCHITECTURE.md`](../../../ARCHITECTURE.md) — current architecture.
5. [`ROADMAP.md`](../../../ROADMAP.md) — what the next milestone is.
6. [`docs/architecture-plan.md`](../../../docs/architecture-plan.md) — the
   pending architectural proposal and its open questions.

If the user passed an argument (e.g. `/architecture-audit tickets`), focus
the audit on that module/area.

## Procedure

1. **Explore.** Use `Explore` (or `Grep`/`Read`) to find every existing
   reference to the area being audited. Do not skim — list the files
   touched.
2. **Map to the domain.** State which entities (per `docs/service-domain.md`)
   and which blueprint (per `AGENTS.md` §"Architecture Rules") this
   belongs to.
3. **List assumptions.** Numbered, each one falsifiable in a sentence.
4. **Propose options.** Generate **at least two** alternatives, with
   trade-offs. Per [`AGENTS.md`](../../../AGENTS.md) §"Use Claude For", this
   is the core of the deliverable.
5. **Recommend one.** State which option you'd pick and why, in two
   sentences max.
6. **Identify files to create vs. adapt.** Bullet list, no code.
7. **Open questions.** End with a numbered list of questions the user must
   answer before implementation can start.

## Output format

Write the audit as a Markdown document in the user's response (do not save
to a file unless the user asks). Use these section headings exactly so the
result composes with [`docs/architecture-plan.md`](../../../docs/architecture-plan.md):

```
## 1. Audit summary
## 2. Assumptions
## 3. Options considered
## 4. Recommendation
## 5. Files to create vs. adapt
## 6. Open questions
```

## Hard rules

- **Do not write app code.** Not even a stub. If asked to "just sketch a
  model," refuse and link the user to [`/data-model`](../data-model/SKILL.md)
  instead.
- **Do not invent UI patterns.** All UI references must trace to a file in
  [`docs/ui-reference.md`](../../../docs/ui-reference.md). If a screen has
  no matching pattern, flag it as an open question rather than improvising.
- **Do not propose stack changes.** No FastAPI, no React, no component
  libraries. If the right answer requires a stack change, surface it as a
  ❓ open question and stop.
- **Do not couple to VMES/OEE.** Future integrations are API/sync only.
- **Stop on ambiguity.** Per [`AGENTS.md`](../../../AGENTS.md) §"Operating
  Rules": *"Stop and list assumptions when requirements are ambiguous."*

## Stop conditions

Halt and ask the user when any of these are true:

- The proposed change would break standalone-app boundaries.
- The UI for the change has no matching reference in `docs/ui-reference.md`.
- The change requires a new top-level dependency.
- A model relationship is unclear or ambiguous.
- A migration would be destructive on production data.
- VMES/OEE roadmap fit is unclear.
