# Service CRM — Roadmap

We follow [Semantic Versioning 2.0.0](https://semver.org/):
`MAJOR.MINOR.PATCH`. Pre-1.0, **MINOR bumps may break things**; from 1.0
onwards, only MAJOR bumps may.

Tags are `vX.Y.Z`. Pushing a tag triggers
[`.github/workflows/release.yml`](.github/workflows/release.yml), which builds
artifacts and publishes a GitHub Release populated from
[`CHANGELOG.md`](./CHANGELOG.md).

## Release cadence

- **Patch (`0.x.Y`)** — as soon as a fix is ready and tested.
- **Minor (`0.Y.0`)** — roughly every 4–6 weeks during 0.x.
- **Major** — only `1.0.0`, then we stabilize.

A release happens when the `## [Unreleased]` section of the changelog has
shipped scope worth cutting, CI is green on `main`, and the migration story
from the previous tag has been verified.

---

## 0.1.0 — "Walking skeleton" (target: M+1)

The smallest thing that can run in a container, log a user in, and persist a
record. Nothing user-visible beyond plumbing.

- [ ] Project scaffold: `pyproject.toml`, ruff, mypy, pytest.
- [ ] FastAPI app factory, settings via Pydantic, healthcheck endpoint.
- [ ] SQLAlchemy + Alembic wired to Postgres and SQLite.
- [ ] First migration: `users` table.
- [ ] Argon2 password hashing, session login/logout.
- [ ] Dockerfile + `docker compose up` runs the app against Postgres.
- [ ] CI: lint, type-check, tests on push.

## 0.2.0 — "Customers & assets"

Operators can put real data in.

- [ ] Customer CRUD (web + API), soft-delete.
- [ ] Asset CRUD bound to a customer.
- [ ] ULID IDs for external surfaces.
- [ ] Search across customers and assets — Postgres `tsvector` + GIN, SQLite
      FTS5 with the same tokenizer config so dev and prod behave the same
      (stemming + ranked results in both).
- [ ] Import: CSV import for customers.

## 0.3.0 — "Work orders"

The core loop: open a ticket, work it, close it.

- [ ] WorkOrder entity + state machine (`draft → … → closed`).
- [ ] WorkLog append-only labor entries; per-tech timer in the UI.
- [ ] Status board view (Kanban-ish, HTMX).
- [ ] Audit log for every state transition.
- [ ] Test coverage on the state machine ≥ 95% (see python.tests.md).

## 0.4.0 — "Inventory & parts"

- [ ] InventoryItem CRUD, stock levels, reorder threshold.
- [ ] PartUsage on a WorkOrder decrements stock atomically.
- [ ] Low-stock report.
- [ ] Stock-take adjustment with reason code.

## 0.5.0 — "Quoting & invoicing"

- [ ] Quote generation from a WorkOrder.
- [ ] Invoice issue (immutable once issued, ULID + sequential human number).
- [ ] PDF rendering (WeasyPrint).
- [ ] Credit note flow for corrections.
- [ ] EU-style VAT lines.

## 0.6.0 — "Payments & A/R"

- [ ] Manual payment recording (cash, card-present, bank transfer).
- [ ] Outstanding-balance report per customer.
- [ ] Aging buckets (0–30, 31–60, 61–90, 90+).

## 0.7.0 — "Scheduling"

- [ ] Calendar view of scheduled work orders.
- [ ] Per-technician day view.
- [ ] iCal feed per technician.

## 0.8.0 — "Notifications"

- [ ] Email on status changes (SMTP).
- [ ] Templated notifications, per-customer opt-out.
- [ ] APScheduler-driven daily digest for owners.

## 0.9.0 — "Hardening for 1.0"

Feature freeze. Only stabilization, performance, and docs.

- [ ] Backup/restore documented and tested end-to-end.
- [ ] Upgrade path documented for every prior 0.x → 1.0.
- [ ] Performance budget defined and met (P95 page load < 300ms on reference dataset).
- [ ] Security review: dependency audit, session fixation test, CSRF, RBAC matrix test.
- [ ] User guide and operator guide complete.

## 1.0.0 — "Production-ready single-tenant"

API and DB schema covered by SemVer guarantees from this point forward.

- Public REST API stabilized and documented.
- Migrations are forward-only and tested both ways.
- LTS-style support: critical fixes backported to `1.0.x` for 12 months.

---

## Beyond 1.0 (sketch — order may change)

| Version | Theme                       | Highlights                                                     |
| ------- | --------------------------- | -------------------------------------------------------------- |
| 1.1     | Customer portal             | Self-service status, invoice download, pay-online stub         |
| 1.2     | Field-tech offline mode     | PWA + local sync queue                                         |
| 1.3     | Payment processor plugins   | Stripe Terminal, SumUp, manual reconciliation                  |
| 1.4     | Integrations                | Webhooks, Zapier-style outbound, accounting export (Xero/QBO)  |
| 1.5     | Reporting & BI              | Saved reports, CSV/Parquet export, Metabase-friendly views     |
| 2.0     | Multi-location single-tenant| Branches under one tenant; *not* multi-tenant SaaS             |

## How items get on the roadmap

1. Open a GitHub issue with the `proposal` label.
2. If it survives a week of discussion, an ADR lands in `docs/adr/`.
3. The ADR's "Decision" section dictates which milestone it gets attached to.

Anything not on this list is **not on the roadmap** — please don't infer
commitments from chat threads or PR comments.
