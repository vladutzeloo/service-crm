# UI Reference

## Purpose

Use this file as the source map between `oee-calculator2.0` and `service-crm`.

## Source Repository

- Local repository: `../oee-calculator2.0`
- GitHub repository: `https://github.com/vladutzeloo/oee-calculator2.0`
- Branch/ref: `main`

## Exact Source Files

- Base layout:
  - Local: `../oee-calculator2.0/templates/base.html`
  - GitHub: `https://github.com/vladutzeloo/oee-calculator2.0/blob/main/templates/base.html`
- Theme bootstrap:
  - Local: `../oee-calculator2.0/templates/partials/theme_init.html`
  - GitHub: `https://github.com/vladutzeloo/oee-calculator2.0/blob/main/templates/partials/theme_init.html`
- Global CSS:
  - Local: `../oee-calculator2.0/static/css/style.css`
  - GitHub: `https://github.com/vladutzeloo/oee-calculator2.0/blob/main/static/css/style.css`
- Main compact dashboard:
  - Local: `../oee-calculator2.0/templates/admin/dashboard.html`
  - GitHub: `https://github.com/vladutzeloo/oee-calculator2.0/blob/main/templates/admin/dashboard.html`
- Table/list pattern:
  - Local: `../oee-calculator2.0/templates/admin/orders.html`
  - GitHub: `https://github.com/vladutzeloo/oee-calculator2.0/blob/main/templates/admin/orders.html`
- Master-data list/import pattern:
  - Local: `../oee-calculator2.0/templates/admin/items.html`
  - GitHub: `https://github.com/vladutzeloo/oee-calculator2.0/blob/main/templates/admin/items.html`
- Detail page pattern:
  - Local: `../oee-calculator2.0/templates/admin/item_detail.html`
  - GitHub: `https://github.com/vladutzeloo/oee-calculator2.0/blob/main/templates/admin/item_detail.html`
- Filter/report pattern:
  - Local: `../oee-calculator2.0/templates/admin/reports.html`
  - GitHub: `https://github.com/vladutzeloo/oee-calculator2.0/blob/main/templates/admin/reports.html`
- Planning/filter pattern:
  - Local: `../oee-calculator2.0/templates/admin/planning.html`
  - GitHub: `https://github.com/vladutzeloo/oee-calculator2.0/blob/main/templates/admin/planning.html`
- Form/modal pattern:
  - Local: `../oee-calculator2.0/templates/forecast_orders.html`
  - GitHub: `https://github.com/vladutzeloo/oee-calculator2.0/blob/main/templates/forecast_orders.html`
- Dense operational cockpit pattern:
  - Local: `../oee-calculator2.0/templates/capacity.html`
  - GitHub: `https://github.com/vladutzeloo/oee-calculator2.0/blob/main/templates/capacity.html`
- Technician/operator screen with no main sidebar:
  - Local: `../oee-calculator2.0/templates/operator/dashboard.html`
  - GitHub: `https://github.com/vladutzeloo/oee-calculator2.0/blob/main/templates/operator/dashboard.html`

## Local Pattern Targets

- `templates/base.html`: global shell, topbar, blocks, Lucide icons, light/dark theme handling.
- `templates/partials/theme_init.html`: initial theme behavior.
- `static/css/style.css`: tokens, surfaces, buttons, tables, cards, table scroll behavior.
- `templates/admin/dashboard.html`: compact dashboard, KPI hierarchy, machine cards, recent table.
- `templates/admin/orders.html`: order list, search, action table, edit modal.
- `templates/admin/items.html`: master-data list, import/export controls, collapsible panels.
- `templates/admin/item_detail.html`: breadcrumb, detail header, actions, collapsible edit form, info cards.
- `templates/admin/reports.html`: date filters, KPI cards, filter chips, report tables.
- `templates/admin/planning.html`: dense planning controls, filters, status controls.
- `templates/forecast_orders.html`: Alpine modal form and async search pattern.
- `templates/capacity.html`: dense cockpit, KPI pills, filters, capacity grid, what-if panel.
- `templates/operator/dashboard.html`: technician/operator screen pattern without the admin sidebar.

## Design Tokens To Preserve

- Use CSS variables from `static/css/style.css`:
  - `--bg`
  - `--surface`
  - `--surface-2`
  - `--border`
  - `--text`
  - `--text-muted`
  - `--accent`
  - `--good`
  - `--fair`
  - `--poor`
  - `--font-body`
  - `--font-mono`
- Keep light mode as the default.
- Keep `data-theme="dark"` support only where it follows the OEE pattern.
- Use Lucide icons through the existing base layout pattern.
- Prefer existing `.btn`, `.btn-sm`, `.btn-primary`, `.btn-secondary`, `.btn-danger`, `.btn-ghost`, `.btn-success`, `.oee-card`, and `.table-scroll` styles.

## Required UI Translation

- Reuse layout structure before creating new layout primitives.
- Reuse visual hierarchy from dashboard pages for service dashboards.
- Reuse table/list spacing, headers, filters, empty states, and actions.
- Reuse form density, labels, field grouping, and submit/cancel placement.
- Reuse detail page structure for tickets, equipment, clients, and interventions.

## Forbidden UI Changes

- Do not create a new design language.
- Do not replace the visual system with a component library.
- Do not add gradient-heavy styling, neon accents, or decorative backgrounds.
- Do not use emoji icons.
- Do not add a left sidebar to main technician screens unless explicitly approved.

## Design Review Checklist

- Does the screen look native to `oee-calculator2.0`?
- Is light mode the default?
- Is the dashboard compact and scannable?
- Are tables dense enough for operational work?
- Are actions clear without marketing-style layout?
- Are filters close to the data they affect?
- Are forms efficient for repeated service work?
