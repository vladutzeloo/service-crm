# ADR-0001: Flask + Jinja over FastAPI + Jinja

- **Status:** Accepted
- **Date:** 2026-05-10
- **Deciders:** project owner
- **Context source:** [`AGENTS.md`](../../AGENTS.md),
  [`docs/blueprint.md`](../blueprint.md),
  [`docs/v1-implementation-goals.md`](../v1-implementation-goals.md)

## Context

Two project documents disagreed on the web framework:

- [`AGENTS.md`](../../AGENTS.md) — *"Use Flask, Jinja, SQLAlchemy, Alembic,
  and pytest."* — has been the agreed stack since the initial planning
  rounds (PRs #1, #2, #3 merged on this basis).
- [`docs/blueprint.md`](../blueprint.md) §5 — pasted by the user from an
  external source on 2026-05-10 — recommends *"FastAPI for routing and
  APIs, SQLAlchemy 2 for ORM, Alembic, Pydantic, Jinja templates."*

Both target the same end product: a single-tenant, server-rendered, OEE-UI
CRM for CNC service teams, with bilingual (RO/EN) UI and a PWA-light
mobile profile. Both choices keep the rest of the stack identical
(SQLAlchemy 2 + Alembic + Jinja + pytest).

The user explicitly delegated the call ("decide which one is better for
our goals") on 2026-05-10.

## Decision

**Flask + Jinja.** AGENTS.md remains authoritative; the blueprint's
FastAPI section is recorded but not adopted.

## Consequences

### Positive

- Forms-driven CRUD (Flask-WTF + WTForms) is the framework's strength.
  This is what 80 %+ of the v1 surface looks like (clients, equipment,
  tickets, interventions, checklist runs, maintenance plans).
- Auth is server-rendered sessions + Argon2 + RBAC. Flask-Login is
  exactly that.
- i18n via Flask-Babel + Jinja `{% trans %}` is mature, well-documented,
  and integrates with WTForms' validation messages cleanly.
- Flask-Migrate ergonomics around Alembic match the small-shop
  operability target.
- The OEE design source is a server-rendered Jinja app; vendoring its
  templates into a sibling Flask app needs no `url_for` rewrites or
  flash-message porting.
- Existing planning docs (ARCHITECTURE.md, ROADMAP.md, python.tests.md,
  pyproject.toml, the five Claude skills) already reflect Flask. Keeping
  Flask costs zero rework; switching to FastAPI would require rewriting
  all five.

### Negative

- No native auto-OpenAPI for the API surface. If we expose JSON
  endpoints (per [`docs/v1-implementation-goals.md`](../v1-implementation-goals.md)
  §1.7's `docs/api.md`), we generate the spec by hand or with
  `apispec`/`flask-smorest`. Acceptable cost.
- Async I/O is opt-in rather than default. Not a problem for the
  single-tenant CRUD profile; a sync request loop with Postgres meets
  the §1.3 P95 budgets comfortably on a 4-vCPU host.
- No Pydantic-shaped request validation by default. We get type-safe
  request bodies via Pydantic + a 30-line `@validate_with(Schema)`
  decorator if/when we need them on the JSON endpoints.

### Reversibility

Most of the codebase is framework-agnostic by design (per the layering
rule in [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §4.3): the domain,
services, and tests live in `service_crm/<bp>/services.py` and don't
import the framework. A future migration to FastAPI would mean swapping
`service_crm/__init__.py` (the app factory), each blueprint's
`routes.py`, and the auth glue — but not models, services, templates'
rendered output, or tests' DB layer.

This is a one-way decision **for v1**, but not a permanent one for the
project.

## Alternatives considered

### FastAPI + Jinja (the blueprint's recommendation)

- **Pros:** Auto-OpenAPI, async-first, Pydantic-validated request
  bodies, more "modern" perception.
- **Cons:** No first-party forms story; CSRF, file uploads,
  flash messages, and HTML form rendering all have to be assembled.
  Auth via session cookies needs more wiring than Flask-Login.
  i18n via `babel` + Starlette middleware is workable but less
  documented than Flask-Babel.
- **Net:** FastAPI's strengths (async + type-safe JSON APIs +
  auto-docs) are not the bottleneck for this product. Adopting FastAPI
  here means paying full FastAPI complexity for half its benefit, and
  rebuilding the parts of the form/auth/i18n stack that Flask gives us
  for free.

### Open an ADR-thread and defer the call

- **Pros:** Lowest-regret if the team gains async-heavy use cases
  (real-time notifications, websockets, third-party webhooks) before
  v1 ships.
- **Cons:** We've already paid the planning cost three times under the
  Flask assumption. Deferring blocks all 0.1.0 implementation work.
- **Net:** The async use cases the blueprint anticipates are explicitly
  out of scope for v1 ([`docs/v1-implementation-goals.md`](../v1-implementation-goals.md) §7).
  If they materialise, ADR-0001 can be superseded by an ADR-N at that
  time.

## Notes

- The blueprint's §5 layout (`app/core`, `app/models`, `app/services`,
  `app/routers`, `app/templates`, `app/schemas`) maps cleanly onto
  Flask: read "Blueprints" for "routers" and the layout matches what's
  already in [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §4.2.
- Pydantic stays in the dependency list as a settings/config tool
  (`pydantic-settings`) and as a request-body validator if/when we add
  JSON endpoints. Adopting Pydantic doesn't require adopting FastAPI.
