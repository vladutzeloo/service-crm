---
name: consistency-pass
description: Run before merging a feature PR or after a stretch of slicing work. Reviews recent changes against UI reference, naming, layering rules, light-mode default, and oee-calculator2.0 parity. Produces a report; only applies small, mechanical fixes.
---

# Consistency Pass

Codifies the "Consistency Pass" checklist from
[`docs/tasks.md`](../../../docs/tasks.md).

## Inputs (read these first)

1. [`AGENTS.md`](../../../AGENTS.md) — operating rules.
2. [`docs/ui-reference.md`](../../../docs/ui-reference.md) — UI rules and
   forbidden changes.
3. [`docs/tasks.md`](../../../docs/tasks.md) §"Consistency Pass" — the
   canonical checklist.
4. The current `git diff` against `main` (or against the merge base of
   the active PR if the user gives one).

## What this skill produces

- A **report** in the user's response with one section per check below.
- For each finding: severity (`blocker` / `should-fix` / `nit`), file +
  line reference, and a one-line description.
- For mechanical, low-risk findings only (typos, dead imports,
  dead-code comments, obvious classname drift, missing docstrings on
  new public symbols), apply the fix in the same response and note it
  in the report.
- For anything ambiguous or architectural, leave it as a finding and
  ask the user to decide.

## Checklist (each is a section of the report)

1. **UI reference parity.** For every new screen / macro / template,
   trace it back to a row in `docs/ui-reference.md`. Anything without a
   reference is a `should-fix`.
2. **Naming consistency.** Models, routes, templates, factories, and
   tests for the same concept use the same noun (e.g. `ServiceTicket`
   ↔ `tickets/` ↔ `templates/tickets/list.html` ↔ `ServiceTicketFactory`).
3. **Routes are thin.** Grep new `routes.py` files for `db.session`,
   raw SQL, or imports from another blueprint's `models.py` — any of
   these is a `blocker`.
4. **Services own the ORM.** All `db.session.*` calls live under a
   `<bp>/services.py`. Helper modules (`shared/`) may use the session
   only via a passed-in argument.
5. **Tests added.** Every new public service function and every new
   route has at least one test. Constraints (unique, FK, check) have at
   least one failing-case test.
6. **Migrations match models.** Run
   `flask --app service_crm db check` (or autogenerate a no-op revision
   and confirm it's empty). Any drift is a `blocker`.
7. **Light mode default.** Grep templates for `data-theme="dark"` —
   only allowed where it follows the OEE pattern. New top-level
   `data-theme="dark"` on `<html>` is a `blocker`.
8. **No emoji icons.** Grep templates and Python for emoji code points
   in user-facing strings. Any hit is a `should-fix`.
9. **No left sidebar on technician screens.** Templates under
   `templates/dashboard/` or any `operator`-flavored route must not
   include a left sidebar partial.
10. **No new top-level deps without a note.** Compare the new
    `pyproject.toml` against the previous version on `main`. Any added
    runtime dependency must have a one-line justification in the PR
    description; otherwise flag as a `should-fix`.
11. **No `// removed`-style comments.** Per the project rule against
    backwards-compat hacks, dead-code comments are deleted, not kept.
12. **Audit coverage.** Any new model that holds business data inherits
    from `Auditable`. Any new service mutation passes through code that
    triggers the listeners (i.e. uses ORM operations, not raw SQL).
13. **Light coverage gate sanity check.** `pytest --cov` ≥ 85% overall
    and ≥ 95% on any `state.py` files.
14. **Changelog updated.** New user-visible scope has a bullet under
    `## [Unreleased]` in `CHANGELOG.md` under the right heading.
15. **Mobile / PWA bar.** For every new screen / form (per
    [`docs/v1-implementation-goals.md`](../../../docs/v1-implementation-goals.md) §2):
    - All interactive elements ≥ **44 × 44 pt** at 375 px.
    - No hover-only behavior; tap and long-press paths exist.
    - Form fields declare `type` / `inputmode` / `autocomplete`.
    - State-changing forms include the idempotency-token hidden input.
    - Tables that overflow at < 640 px collapse via `.table-stacked`
      (no horizontal scrollbar at 320 px).
    - Camera-capture inputs use
      `<input type="file" accept="image/*" capture="environment">` with
      a regular file-input fallback (iOS quirk).
16. **Service worker hygiene.** If `static/service-worker.js` or the
    cache-key constant changed, the cache key version-bumped (tied to
    `VERSION`); a no-bump on a SW change is a `blocker`.
17. **Lighthouse budget regressions.** If `lighthouse-ci` ran on this PR
    and any metric in §2.6 of v1-implementation-goals dropped below the
    threshold, that's a `blocker`.
18. **Accessibility.** `axe-core` audit (where available) reports zero
    critical/serious violations on new P1 pages.
19. **i18n hygiene** (per
    [`docs/v1-implementation-goals.md`](../../../docs/v1-implementation-goals.md) §3.2):
    - No hardcoded user-facing strings — every visible text node passes
      through `{% trans %}`, `_()`, or `gettext_lazy`.
    - WTForms validators use translatable messages (`gettext_lazy` for
      class-level defaults).
    - DB enums and lookup `code` columns use stable English; UI labels
      are translated.
    - `pybabel update` produces no uncommitted diff — new `_()` calls
      land with re-extracted catalogs.
    - Layout audit at 320 px in **both** `ro` and `en` (no horizontal
      scrollbar).
    - Date / number formatting goes through Babel helpers, not
      `strftime` directly.

## Procedure

1. `git fetch origin && git diff --stat origin/main...HEAD` to scope.
2. For each item in the checklist, run the implied search/grep/test and
   record findings.
3. Apply mechanical fixes in the same pass (typos, dead imports, missing
   changelog bullet for an obvious change). Larger fixes — leave as
   findings.
4. Output the report; end with a `## Verdict` line: `ship-it`,
   `address blockers then ship`, or `pause and discuss`.

## Hard rules

- **Do not refactor.** Per [`AGENTS.md`](../../../AGENTS.md) §"Operating
  Rules": *"Keep changes narrowly targeted. Do not introduce unrelated
  refactors."*
- **Do not modify tests** to make findings disappear. A failing test is
  a finding, not a chore.
- **Do not invent fixes** for ambiguous findings. If two reasonable
  interpretations exist, leave it as a finding and ask.
- **Stop on stack drift.** If the diff introduces FastAPI, React, a
  component library, a SPA framework, or any new top-level package
  beyond the agreed list — that's a `blocker`. Do not try to "fix" it
  by adapting; flag it and stop.

## Stop conditions

- The diff includes a stack change.
- The diff includes a forbidden UI change (gradient/neon/marketing,
  emoji icons, left sidebar on technician screens).
- A `blocker` was found and the user hasn't decided what to do about it.

## Definition of done

- Report covers every checklist item.
- Mechanical fixes applied (and listed in the report).
- Verdict is one of `ship-it`, `address blockers then ship`, or
  `pause and discuss`.
