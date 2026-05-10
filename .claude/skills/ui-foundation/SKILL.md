---
name: ui-foundation
description: Run when implementing the shared UI shell (base.html, CSS tokens, KPI cards, tables, filters, form-shell, tabs) or extending it. Vendors patterns from oee-calculator2.0. Writes templates and CSS only — no business logic.
---

# UI Foundation

Codifies the "UI Foundation Only" workflow from
[`docs/tasks.md`](../../../docs/tasks.md).

## Inputs (read these first)

1. [`AGENTS.md`](../../../AGENTS.md) — UI rules.
2. [`docs/ui-reference.md`](../../../docs/ui-reference.md) — **the** source
   map. Every file you touch must trace to a row in this document.
3. The relevant `oee-calculator2.0` source files. Either:
   - Local: `../oee-calculator2.0/templates/<file>` and
     `../oee-calculator2.0/static/css/style.css`.
   - Or via `WebFetch` against the GitHub URLs in `docs/ui-reference.md`.

If neither path is available, **stop and ask** — do not invent the patterns.

## What this skill produces

Only the shared UI foundation. Concretely:

- `service_crm/templates/base.html` — vendored from
  `oee-calculator2.0/templates/base.html`, adjusted for the service-crm
  navigation and brand string. Registers the service worker (§"PWA").
- `service_crm/templates/partials/theme_init.html` — vendored verbatim.
- `service_crm/static/css/style.css` — vendored CSS tokens, surfaces,
  buttons, tables, cards, table-scroll behavior. Project-specific
  additions go at the bottom of the file behind a `/* service-crm
  additions */` comment, including the `.table-stacked` responsive
  pattern for < 640 px.
- `service_crm/static/manifest.webmanifest` — Web App Manifest with
  name, short_name, start_url, scope, `display: standalone`,
  theme_color, background_color, three icon sizes (192, 512, maskable).
- `service_crm/static/service-worker.js` — small SW that precaches the
  app shell + static assets. Cache key is tied to the value of
  `VERSION` so a deploy invalidates old caches. **No write-side
  caching in v1.0.**
- `service_crm/static/icons/` — PWA icons (192, 512, maskable variants).
- `service_crm/templates/_macros/` — small Jinja macros for the patterns
  the rest of the app will reuse:
  - `kpi_card.html` — KPI tile (matches `templates/admin/dashboard.html`).
  - `data_table.html` — list table (matches `templates/admin/orders.html`).
    Collapses to stacked cards below 640 px.
  - `filter_bar.html` — filter chips + date range (matches
    `templates/admin/reports.html`).
  - `form_shell.html` — form layout with submit/cancel (matches
    `templates/forecast_orders.html` modal pattern). Includes the
    idempotency-token hidden input every state-changing form will use.
  - `tabs.html` — tab strip for detail pages (matches
    `templates/admin/item_detail.html`).
  - `modal.html` — accessible modal pattern.
- `service_crm/templates/dev/macro_smoke.html` — a single page that
  renders every macro with placeholder data. This is the visual smoke
  test referenced in [`ROADMAP.md`](../../../ROADMAP.md) 0.2.0.

## Procedure

1. **Confirm source access.** Either the sibling repo is on disk at
   `../oee-calculator2.0` or the GitHub URLs are reachable.
2. **For each target file**, fetch the corresponding source and produce a
   side-by-side diff in your scratch notes. Vendor the structure; do not
   rewrite it from memory.
3. **Adapt brand strings and nav links** — replace OEE-specific labels with
   service-crm equivalents (Clients / Equipment / Tickets / Maintenance /
   Knowledge / Dashboard).
4. **Preserve every CSS variable** listed in `docs/ui-reference.md`
   §"Design Tokens To Preserve".
5. **Render the smoke page** (`/dev/macro-smoke`) and compare to the
   relevant OEE screen. The visual checklist in
   `docs/ui-reference.md` §"Design Review Checklist" must pass.
6. **Add tests**: a single e2e test that hits `/dev/macro-smoke` and
   asserts each macro produces its expected anchor element (e.g. an
   `.oee-card` for `kpi_card`, a `<table class="data-table">` for
   `data_table`). No screenshot diffing.

## Hard rules

- **Vendored, not imported.** Copy the template/CSS into this repo. No
  git submodule. No package install.
- **No new design system.** Per [`AGENTS.md`](../../../AGENTS.md):
  - No gradient-heavy, neon, decorative, or marketing-style UI.
  - No emoji icons.
  - No left sidebar in main technician screens.
  - No component library (Bootstrap, Tailwind, Bulma, MUI, etc.).
- **Light mode is the default.** `data-theme="dark"` is supported only
  where the OEE pattern supports it.
- **Lucide icons** via the existing base layout pattern only.
- **No business logic.** Macros take data via parameters; pages pass
  placeholder data. The blueprints (`/module-slice`) are responsible for
  wiring real data later.
- **Reuse the existing classes** (`.btn`, `.btn-sm`, `.btn-primary`,
  `.btn-secondary`, `.btn-danger`, `.btn-ghost`, `.btn-success`,
  `.oee-card`, `.table-scroll`). Adding a new class needs a comment
  explaining why an existing one didn't fit.
- **Mobile-first (PWA-light) from day one** — see
  [`docs/v1-implementation-goals.md`](../../../docs/v1-implementation-goals.md) §2:
  - Every interactive element ≥ **44 × 44 pt**.
  - No hover-only interactions.
  - All P1 macros render correctly at **320 px width** with no horizontal
    scroll.
  - Tables collapse to stacked cards below 640 px (`.table-stacked`).
  - Form fields declare `type` / `inputmode` / `autocomplete` per the
    [v1 phone-ready bar](../../../docs/v1-implementation-goals.md#23-mobile-friendly-forms).
  - `form_shell.html` includes a hidden idempotency-token input (UUID
    generated server-side); no write-side service-worker caching.
- **Service worker rules** — cache key tied to `VERSION`; precache the
  shell + static; no write-side caching in v1; ship a `skip waiting +
  reload` path so a bad SW can't pin users on stale assets.

## Stop conditions

- Source UI files cannot be read.
- A required pattern has no entry in `docs/ui-reference.md`.
- A request asks for a screen layout (e.g. "add a left sidebar to the
  technician dashboard") that the rules forbid.
- The visual review checklist fails on the smoke page.

## Definition of done

- The smoke page renders all macros and looks native to oee-calculator2.0
  on desktop **and** on a 375 px iPhone viewport.
- Light mode is default; topbar, KPI hierarchy, table density, and form
  spacing match the referenced patterns.
- PWA install works on iOS Safari and Android Chrome (manual check).
- Lighthouse mobile run on the smoke page: **Performance ≥ 90,
  Accessibility ≥ 95, PWA badge: yes** (per
  [`docs/v1-implementation-goals.md`](../../../docs/v1-implementation-goals.md) §2.6).
- Touch-target audit (`tests/e2e/test_touch_targets.py`) is green.
- Service worker precache + invalidation is covered by the e2e test in
  [`python.tests.md`](../../../python.tests.md) §13.4.
- `ruff check`, `ruff format --check`, and `pytest -m e2e` pass.
- No `// removed` / dead-code comments. No emoji. No new top-level deps.
