# Service Domain

## Scope

Build a standalone service-management app for **CNC service teams**.
Long-form product blueprint: [`docs/blueprint.md`](./blueprint.md).

## V1 Modules

Per [`AGENTS.md`](../AGENTS.md) §"Architecture Rules", grouped as Flask
blueprints:

- `auth` — users, roles, sessions.
- `clients` — clients, contacts, locations, optional service contracts.
- `equipment` — equipment / installed base, models, controller types,
  warranties.
- `tickets` — service tickets, status history, comments, attachments,
  priorities, types, interventions, intervention actions / findings,
  parts usage, parts master.
- `maintenance` — maintenance plans, maintenance tasks, maintenance
  executions, maintenance templates.
- `knowledge` — checklist templates / items, checklist runs / items,
  procedure documents, procedure tags.
- `planning` — technicians, technician assignments, technician capacity
  slots, technician skills (skills lookup is v2).
- `dashboard` — operational dashboards (manager + technician views).

## Dashboard V1

Per [`docs/blueprint.md`](./blueprint.md) §13 ("answer operational
questions, not raw counts"):

- Active clients.
- Open tickets.
- Overdue tickets.
- Due maintenance this week.
- Tickets waiting parts.
- Technician utilization.
- Tickets by status (panel).
- Upcoming maintenance list (panel).
- Recent interventions (panel).
- High-risk machines / recurring issues (panel).
- Technician load by week (panel).

## Core Entities

Adopted in full from [`docs/blueprint.md`](./blueprint.md) §8.

### Client domain

- `Client` — company or customer account.
- `Contact` — person linked to a client.
- `Location` — client site or service location.
- `ServiceContract` — lightweight, optional in v1.

### Equipment domain

- `Equipment` — installed CNC machine, asset, or unit.
- `EquipmentModel` — manufacturer + model (lookup).
- `EquipmentControllerType` — controller (Fanuc, Siemens, Heidenhain,
  Haas, …) (lookup).
- `EquipmentWarranty` — warranty record per equipment.
- *optional:* equipment category / machine family lookup.

### Ticket domain

- `ServiceTicket` — request, issue, planned service case, or commissioning.
- `TicketStatusHistory` — append-only state-transition record.
- `TicketComment` — chronological comments.
- `TicketAttachment` — files/photos attached to a ticket or intervention.
- `TicketPriority` — lookup.
- `TicketType` — lookup (incident / preventive / commissioning / warranty / …).

### Intervention domain

- `ServiceIntervention` — technician visit or service action.
- `InterventionAction` — what was done.
- `InterventionFinding` — what was diagnosed / observed.
- *optional:* `DowntimeLink` — alignment with later OEE reporting.

### Parts domain

- `PartMaster` — lightweight catalog (code, description).
- `ServicePartUsage` — parts consumed during an intervention.

### Maintenance domain

- `MaintenancePlan` — cadence per equipment / family.
- `MaintenanceTask` — generated due-task instance.
- `MaintenanceExecution` — completed task with findings + parts.
- `MaintenanceTemplate` — reusable recipe attached to a plan.

### Knowledge domain

- `ChecklistTemplate` — reusable inspection / commissioning checklist.
- `ChecklistTemplateItem` — single line in a template.
- `ChecklistRun` — filled checklist for a ticket / intervention / equipment.
- `ChecklistRunItem` — single answered line in a run.
- `ProcedureDocument` — SOP or service knowledge document.
- `ProcedureTag` — tag lookup for procedures.

### Planning domain

- `Technician` — person who performs interventions.
- `TechnicianAssignment` — ticket / intervention assigned to a technician.
- `TechnicianCapacitySlot` — declared capacity per day / shift.
- *optional:* `TechnicianSkill` — skill catalog (v2).

## Ticket Lifecycle

Adopted from [`docs/blueprint.md`](./blueprint.md) §10. Stored DB values
are stable English identifiers; display labels are translated (RO/EN)
per [`docs/v1-implementation-goals.md`](./v1-implementation-goals.md) §3.2.

```
new → qualified → scheduled → in_progress → waiting_parts → monitoring → completed → closed
                                       ↘                ↗
                                        (cancelled, reachable from any pre-completed state)
```

State-transition rules:

- `new` is the only entry state. A ticket created via API or form starts here.
- A manager `qualifies` a ticket (sets type, priority, SLA, assigns).
- `scheduled` requires a technician + a planned date.
- `in_progress` is set when an intervention begins.
- `waiting_parts` is reachable from `in_progress`; resumes to `in_progress`.
- `monitoring` = work done but customer is observing for recurrence; resolves
  to `completed`.
- `completed` is set once the service is finished and signed off.
- `closed` is the terminal accounting state (post-billing, post-SLA-window).
- `cancelled` reachable from any state before `completed`.

Every transition appends a `TicketStatusHistory` row and an
`AuditEvent` row.

## Workflow Expectations

- A client can have multiple contacts, locations, equipment, and contracts.
- Equipment belongs to a client and usually to a location.
- Tickets reference client, location, equipment, type, priority, status,
  due date.
- Interventions belong to tickets and may include technician, time,
  notes, status, actions, findings, parts.
- Checklist runs preserve the executed checklist state via a frozen
  template snapshot — subsequent template edits never mutate historical runs.
- Procedures support knowledge reuse without blocking ticket workflows.
- Maintenance planning surfaces due / overdue equipment.
- Commissioning is a ticket type that bundles a checklist run and an
  equipment-history record.

## Integration Rules

- Keep v1 independent from VMES/OEE code and databases.
- Future VMES/OEE integration must use APIs, export/import, or sync jobs.
- Do not share auth, ORM models, or migrations with another app in v1.
