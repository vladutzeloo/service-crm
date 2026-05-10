# CNC Service & Maintenance App Blueprint

> **Provenance & status.** Pasted by the user on 2026-05-10 from an
> external source (Perplexity-style citations preserved as `[web:NNN]`).
> Saved verbatim — text-encoding artefacts cleaned, content unchanged.
>
> **This blueprint conflicts with the current `main` in three places** —
> see [`docs/architecture-plan.md`](./architecture-plan.md) and
> [`docs/v1-implementation-goals.md`](./v1-implementation-goals.md). Until
> the user decides on each, treat this file as **input** rather than as
> the agreed plan:
>
> 1. **Stack** — blueprint §5 says FastAPI + Pydantic + Jinja; current
>    `AGENTS.md` and architecture say Flask + Jinja. Hard conflict.
> 2. **Bilingual (RO default, EN secondary) from day one** — not in the
>    current ROADMAP or v1 goals. Strict additive, but a real scope bump.
> 3. **CNC-specific domain detail** — the blueprint adds `EquipmentModel`,
>    `EquipmentControllerType`, `EquipmentWarranty`, `InterventionAction`,
>    `InterventionFinding`, `MaintenanceTask`/`MaintenanceExecution`/`MaintenanceTemplate`,
>    `TechnicianAssignment`/`TechnicianCapacitySlot`/`TechnicianSkill`,
>    and a different ticket lifecycle (`new → qualified → scheduled →
>    in_progress → waiting_parts → monitoring → completed → closed`).
>    The current model in `docs/architecture-plan.md` §4 is generic and
>    smaller.

## 1. Executive Summary

This blueprint defines a production-minded, standalone CNC service and maintenance application that reuses the visual language of `oee-calculator2.0` while remaining independent in repository, database, deployment, and authentication. The app is designed to cover the manager's requested workflow first: CRM light, customer database, open and active tickets, intervention history per machine, replaced parts, internal procedures, commissioning checklists, maintenance, planning, active customers, active tickets, and capacity visibility.[web:171][web:197][web:199]

The application itself should be bilingual from day one, with Romanian and English support built into templates, backend messages, statuses, filters, and reports. For FastAPI and Jinja applications, best practice is to externalize strings, use locale detection, and implement Babel/gettext-compatible translation workflows instead of scattering custom translation dictionaries across the codebase.[web:178][web:180][web:194][web:196]

## 2. Product Vision

Build a practical field service management product for CNC machinery that helps a service manager run operations and helps technicians execute work with minimal friction. The system should be operationally useful before it is analytically sophisticated.

### Product goals
- Cover the manager's required workflow end to end.[web:171][web:199]
- Support service teams in both Romanian and English.[web:178][web:180]
- Preserve a familiar UI by reusing the design language of `oee-calculator2.0`.
- Create a clean domain foundation for future reporting, integrations, and CNC-specific enhancements.
- Keep the first version easy to pilot and easy to adopt in a real service team.[web:171][web:197]

### Out of scope for v1
- Predictive maintenance
- Deep machine telemetry ingestion
- Full ERP coupling
- Full warehouse / spare parts inventory system
- Automatic AI diagnosis
- Route optimization and advanced dispatch automation

## 3. Product Principles

- The app must remain standalone in codebase, runtime, database, and auth.
- The app must reuse the same visual language as `oee-calculator2.0`.
- Light mode is the default interface style.
- The first release must prioritize the manager's required workflow over optional CNC-specific extras.
- The app must be bilingual from the start: Romanian and English.
- Internationalization is a foundation concern, not a later enhancement.[web:178][web:180][web:196]
- Every module should be useful in a pilot, not just architecturally elegant.[web:171][web:199]
- The system should prefer clear workflows and auditable records over clever automation.

## 4. Bilingual App Strategy

The application should support Romanian and English from the first milestone. For FastAPI/Jinja stacks, recommended localization patterns include locale-aware middleware, Babel/gettext extraction and compilation, Jinja template integration, and translation of visible UI strings, validation messages, and date/number formatting.[web:178][web:180][web:194][web:196]

### Supported languages
- `ro` — default locale
- `en` — secondary locale and fallback for untranslated strings where needed

### Locale priority order
1. User profile preference
2. Explicit query or URL parameter for switching language
3. Request headers / browser language
4. Default locale (`ro`)

### Translation rules
- No hardcoded visible text in templates
- No hardcoded backend validation text where user-facing errors are returned
- No string concatenation for translated messages
- Keep translation keys or gettext strings stable over time
- Translate dashboard labels, menus, buttons, forms, statuses, filters, empty states, and reports
- Store stable raw enum values in DB and map them to translated display labels in the UI

### i18n technical structure
- `locale/ro/LC_MESSAGES/messages.po`
- `locale/en/LC_MESSAGES/messages.po`
- `babel.cfg`
- Jinja i18n extension enabled where needed
- locale middleware or dependency setting `request.state.locale`
- topbar language switch on every major page

### i18n QA checklist
- Every visible string translated?
- Romanian default works?
- English switch works on every page?
- Dates, labels, statuses, and form errors localized?
- No overflow or broken layout caused by longer English strings?
- Exports preserve stable values while showing translated labels in UI?[web:178][web:180][web:186]

## 5. Recommended Technology Stack

### Core stack
- FastAPI for routing and APIs
- SQLAlchemy 2 for ORM and persistence patterns
- Alembic for controlled migrations
- Pydantic for request/response contracts
- Jinja templates for server-rendered web UI
- Shared CSS/JS design system adapted from `oee-calculator2.0`

Production-oriented FastAPI guidance consistently treats SQLAlchemy and Alembic as core pieces of a maintainable backend stack, especially when building long-lived internal or operational business systems.[web:195][web:200]

### Supporting stack
- PostgreSQL preferred for production
- SQLite acceptable for local prototyping if migrations and types remain compatible with PostgreSQL later
- Server-side sessions or persisted user preference table for locale and UI preferences
- Structured logging and file-safe attachment storage

## 6. Architecture Overview

### Layered architecture
- `app/core/` — config, security, dependencies, middleware, i18n hooks
- `app/models/` — SQLAlchemy models
- `app/schemas/` — Pydantic schemas / DTOs
- `app/services/` — business logic and orchestration
- `app/routers/` — thin HTTP endpoints
- `app/templates/` — Jinja pages
- `app/static/` — CSS, JS, icons, assets
- `locale/` — translation files
- `alembic/` — migrations
- `tests/` — unit and integration tests

### Architecture rules
- Routers stay thin
- Business rules live in services
- ORM models are not returned directly to templates or APIs without schema mapping
- Template logic stays presentation-focused
- Translation helpers must be available in both templates and backend response generation
- Avoid direct coupling to OEE app logic; integrate later by API or sync job if needed

### Recommended project layout
```text
service-app/
  app/
    core/
    models/
    schemas/
    services/
    routers/
    templates/
    static/
  locale/
    ro/LC_MESSAGES/messages.po
    en/LC_MESSAGES/messages.po
  alembic/
  tests/
  AGENTS.md
  docs/
    blueprint.md
    ui-reference.md
    service-domain.md
    tasks.md
    commands.md
```

## 7. UI and UX Blueprint

The visual system should match `oee-calculator2.0` as closely as possible:
- light mode default
- compact KPI cards
- clean filters and tables
- neutral industrial palette
- minimal visual clutter
- no generic SaaS gradient look
- no left-heavy technician workflow UI unless genuinely needed

### Manager UX goals
- One dashboard that answers: what is active, what is overdue, what is blocked, who is overloaded
- Fast access to open tickets, due maintenance, and technicians with capacity issues
- Strong filtering by customer, machine, status, technician, SLA, and date

### Technician UX goals
- Mobile-friendly ticket detail page
- Immediate access to machine history, checklist, procedure, and parts used
- Minimal clicks to start, update, and complete work
- Clear status changes and required fields

### Bilingual UX requirements
- Persistent language switch in header
- Translated empty states, buttons, labels, filters, and toasts
- Layout robust to both Romanian and English label lengths
- Translated dashboard and planner UI

## 8. Domain Model

### Customer domain
- `Customer`
- `CustomerLocation`
- `CustomerContact`
- `ServiceContract` (lightweight in v1 if needed)

### Equipment domain
- `Equipment`
- `EquipmentModel`
- `EquipmentControllerType`
- `EquipmentWarranty`
- optional equipment category / machine family lookup

### Ticket domain
- `ServiceTicket`
- `TicketStatusHistory`
- `TicketComment`
- `TicketAttachment`
- `TicketPriority`
- `TicketType`

### Intervention domain
- `ServiceIntervention`
- `InterventionAction`
- `InterventionFinding`
- optional `DowntimeLink` to align with later OEE reporting

### Parts domain
- `PartMaster` (lightweight)
- `ServicePartUsage`

### Maintenance domain
- `MaintenancePlan`
- `MaintenanceTask`
- `MaintenanceExecution`
- `MaintenanceTemplate`

### Knowledge domain
- `ProcedureDocument`
- `ProcedureTag`
- `ChecklistTemplate`
- `ChecklistTemplateItem`
- `ChecklistRun`
- `ChecklistRunItem`

### Planning domain
- `Technician`
- `TechnicianAssignment`
- `TechnicianCapacitySlot`
- `TechnicianSkill` (optional v2)

## 9. Core Business Workflows

### Workflow 1: Create ticket
1. Select customer
2. Select customer location
3. Select equipment
4. Set ticket type, priority, symptom, requester, SLA if applicable
5. Save ticket as `new`
6. Manager qualifies and schedules

### Workflow 2: Execute intervention
1. Technician opens assigned ticket
2. Reviews machine history, procedures, previous interventions, and checklist
3. Starts intervention
4. Adds actions, findings, root cause, and parts used
5. Completes checklist
6. Sets outcome to completed, monitoring, or waiting parts

### Workflow 3: Commissioning workflow
1. Open commissioning ticket
2. Attach required checklist template
3. Fill commissioning values and sign-off items
4. Generate permanent equipment history record

### Workflow 4: Preventive maintenance planning
1. Define plan per machine or machine family
2. Generate due tasks
3. Assign technician and date
4. Execute task and store maintenance history

### Workflow 5: Manager review
1. Open dashboard
2. View active tickets, overdue maintenance, blocked jobs, capacity load
3. Drill into risky customers or machines
4. Reassign, reschedule, or escalate

## 10. Ticket Lifecycle

Recommended status model:
- `new`
- `qualified`
- `scheduled`
- `in_progress`
- `waiting_parts`
- `monitoring`
- `completed`
- `closed`

Display labels for these statuses must be translated in both Romanian and English. The stored DB values should remain stable and language-neutral.[web:178][web:180]

## 11. User Roles and Permissions

### Roles
- Admin
- Service Manager
- Technician
- Optional Sales / CRM user later

### Permission rules
- Admin: global settings, users, permissions, lookups, localization defaults, templates
- Service Manager: ticket lifecycle, planning, dashboard, procedures, checklist templates, reports
- Technician: own tickets, own interventions, machine history relevant to assigned work, checklist execution, parts usage entry
- Sales / CRM: leads and quotes only, if enabled later

Granular permissions should exist at module level and later action level. This keeps the app consistent with a professional operational system and avoids role confusion in mixed service/admin teams.

## 12. Main Screens

### Manager-facing
- Service Dashboard
- Customers List
- Customer Detail
- Equipment List
- Equipment Detail
- Tickets List
- Ticket Detail
- Maintenance Planner
- Procedures Library
- Checklist Templates
- Reports / KPI pages
- Settings / Lookups / Localization

### Technician-facing
- My Work / Today view
- Ticket Detail
- Intervention Form
- Checklist Runner
- Machine History
- Procedures Viewer

## 13. Dashboard Blueprint

The dashboard should answer operational questions first, not just display raw counts. Field service implementation guidance emphasizes planning the desired operational value and KPIs before expanding features.[web:197][web:199]

### Primary KPI cards
- Active customers
- Open tickets
- Overdue tickets
- Due maintenance this week
- Tickets waiting parts
- Technician utilization

### Secondary panels
- Tickets by status
- Upcoming maintenance list
- Recent interventions
- High-risk machines / recurring issues
- Technician load by week

### Filters
- Customer
- Machine
- Status
- Ticket type
- Technician
- Date range
- Language should not affect filter logic, only display labels

## 14. Reporting and Analytics

### Core reports for v1
- Tickets by status and period
- Interventions by machine
- Parts used by period and machine
- Due vs completed maintenance
- Technician workload and completion counts
- Repeat issue report by machine / customer

### Reporting principles
- Labels translated in UI
- Internal raw codes remain stable
- Locale-aware dates and numbers
- Export-friendly structure from day one

## 15. FSM Implementation Best Practices Applied to This App

Field service implementation best practices consistently recommend reviewing the current landscape, collecting field-team input, piloting early, enabling easy integration, supporting customization, prioritizing mobile usability, and ground-testing the workflows before wider rollout.[web:171][web:199][web:202]

Applied here, that means:
- map the current spreadsheet/process landscape before coding too much
- collect technician and manager feedback on statuses, forms, and checklists
- run a 2–4 week pilot with real tickets
- make mobile ticket execution easy
- keep customization possible through lookup tables, templates, and configurable labels
- avoid building advanced automation before basic workflow adoption is stable

## 16. Non-Functional Requirements

### Reliability
- Every ticket state change logged
- Every intervention auditable
- Attachment handling secure and traceable
- Migration-based DB evolution only

### Performance
- Fast list filtering on tickets and equipment
- Pagination on large lists
- Indexes on ticket status, customer_id, equipment_id, technician_id, due_date

### Security
- Role-based access control
- Safe file upload validation
- Protection of customer contact data
- Secure auth and password storage

### Maintainability
- Basic tests per module
- Service-layer tests for ticket lifecycle and checklist execution
- Translation extraction and compilation documented
- Stable AGENTS.md and docs-driven implementation workflow

## 17. Testing Strategy

### Backend tests
- Model integrity tests
- Service-layer tests for ticket transitions
- Checklist execution tests
- Maintenance generation tests
- Locale middleware / language switch tests

### UI tests / QA
- Dashboard in Romanian
- Dashboard in English
- Ticket create/edit in both languages
- Checklist execution in both languages
- Responsive behavior on technician screens

### i18n release checks
- run extraction
- update `.po` catalogs
- compile translations
- restart app if required by the chosen i18n implementation flow.[web:186][web:194]

## 18. Deployment and Operations

### Recommended environments
- local dev
- staging / pilot
- production

### Deployment expectations
- migration step required on deploy
- backup strategy for attachments and DB
- environment-based config
- language assets shipped with release

## 19. Documentation Set

Recommended supporting documents:
- `blueprint.md` — this file
- `ui-reference.md` — exact source-of-truth UI files from `oee-calculator2.0`
- `service-domain.md` — domain workflows, statuses, and business rules
- `tasks.md` — phased implementation tasks
- `commands.md` — run, test, migration, and translation commands
- `AGENTS.md` — compact root instructions for Claude / GPT-5.5

## 20. AI Development Workflow

### Recommended task split
- Claude: architecture critique, workflow design, product reasoning, prompt strategy
- GPT-5.5 / Codex: precise implementation, models, migrations, CRUD, forms, lists, tests, context-file maintenance
- Gemini or design-focused models: UI explorations and visual alternatives if needed

### Rules for AI implementation
- architecture first, code second
- every major module starts from a short spec
- no redesign away from `oee-calculator2.0`
- no stack changes without explicit decision
- no i18n shortcuts that create long-term hardcoded debt

## 21. Phased Roadmap

### Phase 1 — Foundation
- project scaffold
- PostgreSQL-ready setup
- SQLAlchemy + Alembic
- locale infrastructure (`ro`, `en`)
- shared UI shell
- auth and roles skeleton

### Phase 2 — Core service
- customers
- locations
- contacts
- equipment
- ticket create/list/detail/update
- translated statuses and forms

### Phase 3 — Execution layer
- interventions
- parts usage
- checklist templates
- checklist runs
- procedures library

### Phase 4 — Planning and reporting
- maintenance plans
- maintenance task generation
- technician planner
- manager dashboard
- reports

### Phase 5 — Optional CNC-specific enhancements
- controller alarm knowledge base
- runtime-based maintenance triggers
- deeper OEE/tooling integration
- reliability analytics

## 22. Success Criteria

The app is successful when:
- a manager can run daily service operations without external spreadsheets
- a technician can execute assigned work with full machine context
- Romanian and English both work cleanly across the application
- intervention history becomes structured and searchable
- maintenance is planned instead of remembered manually
- the app is pilot-ready and production-minded without becoming overbuilt too early.[web:171][web:197][web:199]
