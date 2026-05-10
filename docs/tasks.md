# Tasks

## Implementation Sequence

1. Audit existing repo structure.
2. Audit referenced `oee-calculator2.0` UI files.
3. Propose standalone architecture.
4. Define module boundaries.
5. Define SQLAlchemy model set.
6. Review architecture with user.
7. Implement shared UI foundation.
8. Implement models and Alembic migrations.
9. Add model and relationship tests.
10. Implement module CRUD in small slices.
11. Add filters, tables, and detail pages.
12. Add workflow/status tests.
13. Run consistency pass against UI reference.

## Prompt Templates

### Architecture Only

```text
Read AGENTS.md first.
Read docs/ui-reference.md and docs/service-domain.md.
Do not code.
Audit the current repo and referenced oee-calculator2.0 UI files.
Propose the standalone repo architecture, module boundaries, SQLAlchemy model set, and migration plan.
List assumptions and wait for approval.
```

### UI Foundation Only

```text
Read AGENTS.md and docs/ui-reference.md.
Use the referenced oee-calculator2.0 files as the UI source of truth.
Implement only shared UI foundation: base layout, CSS, topbar, KPI cards, tables, filters, form shell, and tabs shell.
Do not add business logic beyond placeholders.
Do not invent a new design system.
```

### Data Model

```text
Read AGENTS.md and docs/service-domain.md.
Implement SQLAlchemy models and Alembic migration for the approved v1 domain.
Keep routes and templates untouched.
Add tests for relationships and core constraints.
```

### Tickets Module

```text
Read AGENTS.md, docs/ui-reference.md, and docs/service-domain.md.
Implement the tickets module using the approved shared UI foundation.
Create routes, templates, filters, status workflow, and detail page.
Match the referenced oee-calculator2.0 UI language exactly.
```

## Stop Conditions

- Requirements conflict with standalone app boundaries.
- UI implementation lacks exact `oee-calculator2.0` references.
- Model relationships are unclear.
- Migration would be destructive.
- Requested change would introduce a new stack.
- Product direction or VMES/OEE roadmap fit is unclear.

## Consistency Pass

- Compare new screens to `docs/ui-reference.md`.
- Check naming consistency across models, routes, templates, and tests.
- Check route logic remains thin.
- Check service-layer logic has tests.
- Check migrations match models.
- Check dashboard density and light-mode defaults.
