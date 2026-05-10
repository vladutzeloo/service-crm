---
name: module-slice
description: Run when implementing a vertical slice of a single blueprint (routes + services + templates + tests). Pass the blueprint name as an argument, e.g. /module-slice tickets. Reuses the UI foundation; does not touch base.html or the global CSS.
---

# Module Slice

Codifies the "Tickets Module" workflow from
[`docs/tasks.md`](../../../docs/tasks.md), generalized to any of the v1
blueprints.

## Argument

The blueprint name. One of:

- `auth`
- `clients`
- `equipment`
- `tickets`
- `maintenance`
- `knowledge`
- `dashboard`

If no argument is given, **stop and ask** which blueprint.

## Inputs (read these first)

1. [`AGENTS.md`](../../../AGENTS.md) — operating rules, UI rules, task split.
2. [`docs/ui-reference.md`](../../../docs/ui-reference.md) — pattern map.
3. [`docs/service-domain.md`](../../../docs/service-domain.md) — workflows
   for the chosen blueprint.
4. [`ARCHITECTURE.md`](../../../ARCHITECTURE.md) §4.3 — layering rules
   (routes thin, services own the ORM).
5. [`docs/architecture-plan.md`](../../../docs/architecture-plan.md) §4 —
   the agreed model sketch for this blueprint.
6. The blueprint's existing `models.py` (must already exist — run
   `/data-model` first if not).

## What this skill produces

For the chosen blueprint `<bp>`:

- `service_crm/<bp>/__init__.py` — `bp = Blueprint("<bp>", __name__,
  template_folder="../templates/<bp>", url_prefix="/<bp>")`.
- `service_crm/<bp>/routes.py` — thin views.
- `service_crm/<bp>/services.py` — all DB access for this blueprint.
- `service_crm/<bp>/forms.py` — Flask-WTF forms.
- `service_crm/templates/<bp>/list.html`, `detail.html`, `edit.html` —
  built from the macros in `service_crm/templates/_macros/`.
- `tests/<bp>/test_routes.py` — e2e via `client_logged_in`.
- `tests/<bp>/test_services.py` — integration with `db_session`.
- A registration line in `service_crm/__init__.py`'s
  `register_blueprints(app)`.

## Procedure

1. **Verify prerequisites.**
   - Models exist for this blueprint (else `/data-model` first).
   - The UI foundation is in place (else `/ui-foundation` first).
   - There is a `dashboard` macro for any KPI this blueprint surfaces.
2. **Routes** in `routes.py`. One view per HTTP entry point. Each view:
   - parses the request,
   - calls one or two functions in `services.py`,
   - renders a template **or** returns a redirect.
   - **No SQL.** **No business rules.** **No `db.session.*`.**
3. **Services** in `services.py`. Use type hints. Functions take
   `(session, ...)` as the first arg. Document any guard rules.
4. **Templates** under `service_crm/templates/<bp>/`. Always:
   - extend `base.html`,
   - use macros from `_macros/`,
   - keep dense, scannable, light-mode layout (per
     [`docs/ui-reference.md`](../../../docs/ui-reference.md)),
   - link list → detail → edit using existing `oee-card` and
     `data-table` patterns.
5. **Forms** in `forms.py` with WTForms validators. CSRF token via
   Flask-WTF (`{{ form.csrf_token }}` in the template).
6. **Status workflow** (where relevant — tickets, maintenance):
   - State machine in `<bp>/state.py` as pure functions.
   - Test exhaustively with `pytest.mark.parametrize` and a Hypothesis
     state machine — ≥ 95% line+branch on `state.py`.
7. **Tests**:
   - `test_services.py` (integration, `@pytest.mark.integration`):
     happy path + at least one failing case for each guard rule.
   - `test_routes.py` (e2e, `@pytest.mark.e2e`): list/detail/create/edit
     round-trip via `client_logged_in`. Assert HTTP status, page
     contents (semantic, not classnames), and DB state.
8. **Register** the blueprint in `service_crm/__init__.py`.

## Hard rules

- **Routes are thin.** If a view does anything more interesting than
  calling a service and rendering a template, push the logic down.
- **Services own the ORM.** Cross-blueprint reads go through the other
  blueprint's `services.py`, not through its `models.py` directly.
- **UI is reused, not invented.** Match the relevant pattern from
  [`docs/ui-reference.md`](../../../docs/ui-reference.md). No new design
  language. No left sidebar on technician screens. No emoji.
- **Templates extend `base.html`** and use macros for tables, KPI cards,
  filters, forms, and tabs.
- **No business logic in templates.** Compute in services; pass values.
- **Tests required.** A new behavior, relationship, or constraint without
  a test is a `/consistency-pass` failure waiting to happen.
- **Soft-delete** for entities with history.
- **Stop on ambiguity.** Per [`AGENTS.md`](../../../AGENTS.md): list
  assumptions and pause; do not improvise the workflow.

## Stop conditions

- The blueprint argument is missing or unrecognised.
- A model the slice needs doesn't exist yet.
- A required UI macro doesn't exist yet.
- A workflow detail (status set, allowed transitions, who can perform an
  action) is not specified in `docs/service-domain.md`.
- The slice would require a stack change or a new top-level dep.

## Definition of done

- `pytest tests/<bp>/` passes (unit + integration + e2e).
- `ruff check`, `ruff format --check`, `mypy service_crm` pass.
- The new screens render natively to oee-calculator2.0 (visual check).
- The blueprint is registered and reachable from the topbar nav.
- Audit log records appear for each create/update/delete.
- The slice is ≤ ~600 LoC of app code; if it's bigger, it should have
  been split into multiple slices.
