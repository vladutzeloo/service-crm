# Service Domain

## Scope

Build a standalone service-management app for service teams.

## V1 Modules

- Clients.
- Contacts.
- Locations.
- Equipment / installed base.
- Service tickets.
- Interventions.
- Parts used.
- Checklist templates.
- Checklist runs.
- Procedures / SOP.
- Maintenance planning.
- Technician calendar / capacity.

## Dashboard V1

- Active clients.
- Active tickets.
- Interventions today.
- Equipment with due maintenance.
- Technician capacity.
- Latest interventions.

## Core Entities

- `Client`: company or customer account.
- `Contact`: person linked to a client.
- `Location`: client site or service location.
- `Equipment`: installed machine, asset, or unit.
- `ServiceTicket`: request, issue, or planned service case.
- `ServiceIntervention`: technician visit or service action.
- `ServicePartUsage`: parts consumed during an intervention.
- `ChecklistTemplate`: reusable inspection or service checklist.
- `ChecklistRun`: filled checklist for a ticket, intervention, or equipment item.
- `ProcedureDocument`: SOP or service knowledge document.

## Workflow Expectations

- A client can have multiple contacts, locations, and equipment records.
- Equipment belongs to a client and usually to a location.
- Tickets may reference client, location, equipment, priority, status, and due date.
- Interventions belong to tickets and may include technician, time, notes, status, and parts.
- Checklist runs should preserve the executed checklist state.
- Procedures should support knowledge reuse without blocking ticket workflows.
- Maintenance planning should surface due or overdue equipment.

## Integration Rules

- Keep v1 independent from VMES/OEE code and databases.
- Future VMES/OEE integration must use APIs, export/import, or sync jobs.
- Do not share auth, ORM models, or migrations with another app in v1.
