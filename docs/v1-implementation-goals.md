# Service-CRM — v1.0 Implementation Goals

> Concrete acceptance criteria for shipping `1.0.0`. Read together with
> [`ROADMAP.md`](../ROADMAP.md) (the *when*), [`ARCHITECTURE.md`](../ARCHITECTURE.md)
> (the *how*), and [`docs/architecture-plan.md`](./architecture-plan.md)
> (the *what's pending approval*).
>
> Every line in this document is a measurable bar. If a goal can't be
> ticked off in a binary yes/no, it doesn't belong here — refile as scope.

## 0. Decided scope of v1

Locked decisions that the rest of this document depends on:

- **Single Flask/Jinja codebase**, served from one container. No SPA, no
  React, no Next.js, no native iOS/Android.
- **Mobile = PWA-light.** Responsive Jinja templates + a Web App Manifest +
  a small service worker that caches the shell and static assets. **Online
  required** for writes; technicians need a connection to log a visit.
  *(Full offline write queue → v1.2.)*
- **Push notifications: deferred to v1.1.** Notifications in v1.0 are
  in-app + email only.
- **Hosting target: self-hosted single-server.** One VPS, one Postgres,
  one Docker image. No multi-region, no CDN required, no managed-platform
  recipe in v1.0 — the Dockerfile is portable and that's the whole story.
- **Single-tenant.** One business per deployment.

Anything outside this list is post-1.0 and lives in [`ROADMAP.md`](../ROADMAP.md)
"Beyond 1.0".

## 1. The v1.0 production-ready bar

A release tagged `v1.0.0` ships only when every box is ticked. Each box
has a concrete check.

### 1.1 Functional completeness

- [ ] All P1 user journeys from [`docs/service-domain.md`](./service-domain.md)
      have routes, services, templates, and tests:
      register a client → register equipment → open a ticket → schedule it →
      log an intervention with parts → run a checklist → close the ticket →
      see it in the dashboard and audit log.
- [ ] Maintenance plans surface overdue equipment on the dashboard.
- [ ] Procedures (SOPs) are searchable and viewable from a ticket / equipment.

### 1.2 Reliability

- [ ] CI green on Python 3.11 **and** 3.12, on SQLite **and** Postgres.
- [ ] Total test count ≥ 200; coverage ≥ **85% line + branch** globally,
      ≥ **95%** on every `state.py`.
- [ ] No `xfail` and no `skip` on critical paths in the suite at tag time.
- [ ] `flask db upgrade` and `flask db downgrade -1` round-trip cleanly
      between every adjacent revision; tested in CI.
- [ ] Restoring a backup to a fresh DB and rerunning the e2e smoke suite
      is part of the release checklist (see [`.github/RELEASING.md`](../.github/RELEASING.md)).

### 1.3 Performance budget

Reference dataset: **10k clients, 50k equipment, 100k tickets, 100 techs,
3 years of audit log**. Budget enforced by a `tests/perf/` suite that
seeds the dataset and times key endpoints.

- [ ] Dashboard P95 < **300 ms** server-rendering on 4-vCPU host.
- [ ] Tickets list (paged, filtered) P95 < **250 ms**.
- [ ] Ticket detail with intervention history P95 < **200 ms**.
- [ ] Search across clients/equipment P95 < **400 ms** with FTS warm.
- [ ] N+1 query audit (`pytest --sqla-warn-on-many-queries`) clean on every
      P1 endpoint.
- [ ] All hot foreign-keys and filter columns indexed; verified by an
      `EXPLAIN`-based test.

### 1.4 Security

- [ ] Auth: Argon2id with parameters at the OWASP 2024 baseline, session
      cookies `Secure` + `HttpOnly` + `SameSite=Lax`.
- [ ] CSRF: Flask-WTF on every state-changing form. Tested with a
      cross-origin POST that must be rejected.
- [ ] RBAC: an explicit role matrix (admin / manager / technician / read-only)
      with one test per role × P1-action cell. No "user can do anything if
      logged in" routes.
- [ ] Headers: `Content-Security-Policy`, `X-Content-Type-Options`,
      `Referrer-Policy`, `Strict-Transport-Security`, `X-Frame-Options`.
      Verified by an e2e header-assertion test.
- [ ] Dependency audit (`pip-audit`) clean at tag time; CI fails on a new
      `HIGH`/`CRITICAL` advisory.
- [ ] Secrets via env only. `.env.example` ships; `.env` is in `.gitignore`.
      Pre-commit hook (`detect-secrets`) blocks accidental commits.
- [ ] File uploads (intervention photos) use `secure_filename`, validate
      MIME + magic bytes, and store outside the static path. Image
      thumbnails generated server-side, never on the client's say-so.
- [ ] Audit log is append-only at the DB level (no UPDATE/DELETE grants on
      `audit_event` for the app role).
- [ ] [`SECURITY.md`](../SECURITY.md) ships with disclosure policy + contact.

### 1.5 Observability

- [ ] Structured JSON logs to stdout (one line per request) with
      `request_id`, `user_id`, `route`, `status`, `latency_ms`.
- [ ] `request_id` propagated to every log line emitted during the request,
      via `contextvars` in `service_crm.shared.logging`.
- [ ] `/healthz` (liveness) and `/readyz` (DB reachable + migrations at head)
      endpoints. Readyz failures during boot block container start.
- [ ] `/metrics` Prometheus endpoint behind a config flag; off by default.
- [ ] Sentry-style error tracking integration documented and switchable via
      `SENTRY_DSN`. *(No vendor mandate; we expose the hook.)*
- [ ] Operator runbook ([`docs/operator-runbook.md`](./operator-runbook.md))
      lists the 10 questions a 3 a.m. operator most needs answered: where
      are the logs, how to fail over, how to restore, etc.

### 1.6 Operability

- [ ] One Dockerfile, multi-stage, < **250 MB** final image, runs as
      non-root.
- [ ] `docker compose up` boots app + Postgres + ready-to-use seed data
      in < 60 s on a laptop.
- [ ] Zero-downtime upgrade procedure documented and dry-run'd: stop app,
      `flask db upgrade`, start app. (Online migrations / blue-green are
      a v1.x thing.)
- [ ] Backup script (`scripts/backup.sh`) produces a `pg_dump --format=c`
      file + the `instance/uploads/` tree as a tarball, and restoration
      is tested end-to-end on every release.
- [ ] Configuration is 100% via env. `service_crm.config` is the single
      reader of `os.environ`.

### 1.7 Documentation

- [ ] [`docs/user-guide.md`](./user-guide.md): how to use the app, per
      module, with screenshots (the OEE-derived UI must be recognizable
      from the screenshots).
- [ ] [`docs/operator-runbook.md`](./operator-runbook.md): install,
      upgrade, backup, restore, common failures, log locations.
- [ ] [`docs/api.md`](./api.md): every JSON endpoint that's stable in v1.0,
      with request/response examples and status codes.
- [ ] At least 6 ADRs in `docs/adr/` covering the decisions that shaped v1
      (Flask-vs-FastAPI, single-tenant, OEE-vendored UI, blueprint layout,
      ULID storage, audit-by-mixin).
- [ ] [`CHANGELOG.md`](../CHANGELOG.md) has a complete `## [1.0.0]` section.

### 1.8 Compliance

- [ ] GDPR-minded: per-customer data export endpoint (admin-only) returning
      a JSON dump of every row referencing that customer.
- [ ] GDPR-minded: per-customer "forget" workflow that anonymises personal
      fields while preserving service history. Audit-logged.
- [ ] License (MIT) + `THIRD_PARTY_NOTICES.md` generated by
      `pip-licenses` and shipped.

## 2. The v1.0 phone-ready bar

"Runs on phones" = the same app, same URL, opened in mobile Safari /
mobile Chrome. We are **not** building a separate mobile UI.

### 2.1 PWA install

- [ ] [`service_crm/static/manifest.webmanifest`](../service_crm/static/manifest.webmanifest)
      with: `name`, `short_name`, `start_url`, `scope`, `display: standalone`,
      `theme_color`, `background_color`, `orientation: portrait-primary`,
      and at least three icon sizes (192, 512, maskable).
- [ ] [`service_crm/static/service-worker.js`](../service_crm/static/service-worker.js)
      registered from `base.html`. Caches the app shell, static assets, and
      the most recent dashboard render. **No write-side caching in v1.0.**
- [ ] "Add to Home Screen" works on iOS Safari **and** Android Chrome
      (last 2 stable major versions of each).
- [ ] Installed PWA opens to the dashboard within **2.5 seconds** on a
      mid-range phone (Lighthouse LCP budget; see §2.6).

### 2.2 Touch + responsive layout

- [ ] All tap targets ≥ **44 × 44 pt** (Apple HIG / Material baseline).
      Verified by a Cypress / Playwright touch-target audit on every list
      and form.
- [ ] No hover-only interactions. Every menu, tooltip, or hint is reachable
      via tap or long-press.
- [ ] All P1 screens render correctly at **320 px width** (smallest
      supported), with no horizontal scroll bar.
- [ ] Tables that don't fit transform into stacked card lists at < 640 px
      (`table → .table-stacked` CSS pattern, single source).
- [ ] The technician dashboard (`templates/dashboard/operator.html`,
      modeled on `oee-calculator2.0/templates/operator/dashboard.html`)
      has **no left sidebar**, ever, on any breakpoint.

### 2.3 Mobile-friendly forms

- [ ] Every input declares the right `type` (`email`, `tel`, `url`,
      `number`, `date`, `datetime-local`).
- [ ] `inputmode` set where it improves the on-screen keyboard
      (`numeric`, `decimal`, `tel`).
- [ ] `autocomplete` set on auth + customer fields (`username`,
      `current-password`, `name`, `tel`, `email`, `street-address`).
- [ ] Forms survive backgrounding / autofill / orientation change without
      losing partially-typed data (HTML form-state preservation, no JS
      state we'd have to rebuild).
- [ ] All forms POST under **2 seconds** end-to-end on a 4G connection
      against a warm DB (P95).

### 2.4 Camera + media (technician-friendly)

- [ ] Photo upload on intervention uses
      `<input type="file" accept="image/*" capture="environment">` so the
      phone opens the camera directly.
- [ ] Server-side image compression (Pillow) caps the long edge at **2048 px**
      and re-encodes as `image/webp` quality 85.
- [ ] Multiple photos per intervention; each is shown with a
      same-aspect-ratio thumbnail in the timeline.

### 2.5 Network resilience

- [ ] Every state-changing form submits with an idempotency token
      (UUID generated server-side at form-render time, stored in a hidden
      input). The server dedupes by `(user_id, idempotency_token)` for
      24 h. Tested with a forced retry. Server-side generation matches
      the Flask/Jinja minimal-JS posture and the rule in
      [`.claude/skills/ui-foundation/SKILL.md`](../.claude/skills/ui-foundation/SKILL.md).
- [ ] Long-running operations (CSV import, photo upload) show progress
      and resume-or-fail predictably; never silently double-create.
- [ ] If the user is logged out (or the network drops mid-submit), the
      form re-renders with the user's data preserved, not a blank page.

### 2.6 Lighthouse budget

Lighthouse run against the production build, mobile profile, simulated
slow-4G + mid-tier CPU. Enforced in CI by `lighthouse-ci`.

- [ ] **Performance ≥ 90** on the dashboard, ticket list, ticket detail.
- [ ] **Accessibility ≥ 95** on every P1 page.
- [ ] **Best Practices ≥ 95**.
- [ ] **PWA badge: yes.**
- [ ] LCP ≤ **2.5 s** on a mid-tier phone (Moto G class).
- [ ] CLS ≤ **0.1**.
- [ ] TBT ≤ **200 ms**.

### 2.7 Real-device QA

- [ ] Manual pass on iPhone (latest iOS Safari) and Android (latest
      Chrome). Findings list shipped with the release notes; no P1
      regressions.

## 3. Cross-cutting non-functional goals

These thread through every milestone, not a single one.

### 3.1 Accessibility (WCAG 2.1 AA on critical paths)

- [ ] Every form field has an associated `<label>`.
- [ ] Color contrast ≥ 4.5:1 for body text, 3:1 for large/UI text. Verified
      against the OEE tokens via `axe-core`.
- [ ] Keyboard-only traversal of every P1 flow works without a mouse.
- [ ] `axe-core` audit in CI; zero critical/serious violations on P1 pages.

### 3.2 Internationalisation

- [ ] Flask-Babel in place. Default locale `en`, second locale `ro`
      (Romanian, given the workspace context).
- [ ] All user-facing strings extracted (`pybabel extract`); translation
      catalog committed.
- [ ] Date/number formats follow the active locale.
- [ ] `Accept-Language` honored unless the user has set a preference.

### 3.3 Audit log coverage

- [ ] Every business mutation (POST/PUT/PATCH/DELETE on a model row)
      produces exactly one `AuditEvent` with `before` + `after` JSON.
      Enforced by an integration test that walks every CRUD endpoint.
- [ ] Audit event includes `actor_id`, `request_id`, `route`, `reason`
      (free-text, optional), and a monotonic timestamp.

### 3.4 Code quality gates (per PR)

- [ ] `ruff check` — zero violations (`E`, `F`, `I`, `B`, `UP`, `SIM`,
      `PL`, `RUF` per [`pyproject.toml`](../pyproject.toml)).
- [ ] `ruff format --check` — clean.
- [ ] `mypy service_crm` — strict, zero errors.
- [ ] `pytest -m "not slow"` — green in < 60 s on a developer laptop.
- [ ] Net new public function without a docstring fails review (skill:
      [`/consistency-pass`](../.claude/skills/consistency-pass/SKILL.md)).

## 4. Per-milestone implementation goals

Maps the milestones in [`ROADMAP.md`](../ROADMAP.md) to concrete
deliverables and definitions of done. Mobile/PWA work is **not** a single
milestone — responsive layout starts in 0.2.0 and is enforced at every
slice via [`/consistency-pass`](../.claude/skills/consistency-pass/SKILL.md).

### 0.1.0 — Walking skeleton

**Done when:** the app boots, a user can log in/out, the database is
migrated, and the test pyramid is in place.

- [ ] `service_crm/__init__.py` exposes `create_app(config)`; no
      module-level side effects.
- [ ] Flask-Migrate wired; first migration creates `users`, `roles`,
      `audit_event`.
- [ ] Argon2id login + logout, session cookies hardened, CSRF on by default.
- [ ] `/healthz`, `/readyz` live.
- [ ] Dockerfile builds; `docker compose up` reaches `/healthz` in < 60 s.
- [ ] Test fixtures from [`python.tests.md`](../python.tests.md) §3 in place.
- [ ] CI matrix (3.11/3.12 × SQLite/Postgres) green.
- [ ] **No business logic.** No client/equipment/ticket models yet.

### 0.2.0 — UI foundation (mobile-first from day one)

**Done when:** every macro the rest of the app will reuse exists, looks
native to oee-calculator2.0, and behaves on phones.

- [ ] `templates/base.html` and `partials/theme_init.html` vendored.
- [ ] `static/css/style.css` vendored; service-crm-specific additions in a
      single appended block.
- [ ] `_macros/` (kpi_card, data_table, filter_bar, form_shell, tabs, modal).
- [ ] **PWA manifest** + **service worker** registered. App shell cached.
- [ ] Responsive breakpoints verified at 320 / 768 / 1024 / 1440 px.
- [ ] Touch-target audit clean on the smoke page.
- [ ] Lighthouse mobile run on the smoke page: Performance ≥ 90,
      Accessibility ≥ 95, PWA badge: yes.
- [ ] No business logic; macros take placeholder data.

### 0.3.0 — Clients & contacts

**Done when:** an operator can register a client + contact + location and
edit/soft-delete them, with full audit and tests.

- [ ] CRUD via routes thin enough that no view function exceeds 25 lines.
- [ ] Soft-delete (`is_active`) on Client; hard-delete forbidden.
- [ ] Search across name + contact email/phone, FTS on PG, FTS5 on SQLite.
- [ ] CSV import with row-level error reporting and a transactional
      "all-or-nothing" mode.
- [ ] axe-core audit clean on client list/detail/edit.
- [ ] Mobile checklist (§2) clean on every new screen.

### 0.4.0 — Equipment / installed base

- [ ] CRUD with the cross-blueprint guard tested
      (`Equipment.location_id` belongs to `Equipment.client_id`).
- [ ] Equipment list filters by client, location, status.
- [ ] CSV import with the same idempotency + error-reporting contract as
      clients.
- [ ] First photo-upload screen (intervention-less, sanity check for the
      pipeline that 0.5 will reuse).

### 0.5.0 — Tickets & interventions

**Done when:** the core service loop works on phones for a technician
walking up to a piece of equipment.

- [ ] State machine (`open → scheduled → in_progress → awaiting_parts →
      resolved → closed`, `cancelled` from any pre-`closed` state) with
      ≥ 95% line+branch coverage and a Hypothesis state-machine test.
- [ ] Intervention create/edit form built for one-handed phone use:
      ≥ 44 pt taps, mobile keyboards, photo upload via camera capture.
- [ ] Idempotency token on every state-changing form. Verified by a
      "double-submit" test.
- [ ] Audit log entry for every state transition (assertable by route).
- [ ] Ticket number sequence (`Sequence("ticket_number_seq")`) on PG;
      SQLite fallback in service layer + tested.

### 0.6.0 — Knowledge: checklists & procedures

- [ ] Checklist run snapshot is **frozen** at run time; subsequent template
      edits do not mutate historical runs (test with a property-based
      "edit-after-snapshot" check).
- [ ] Checklist run UI works offline-displayable (data already loaded) but
      writes still require online (per the v1 PWA-light decision).
- [ ] Procedures full-text searchable (PG `tsvector` / SQLite FTS5).

### 0.7.0 — Maintenance planning

- [ ] APScheduler-driven recompute of `next_due_at`, with the schedule
      exposed in `/readyz` for ops.
- [ ] "Equipment with due maintenance" surfaces on the operational
      dashboard.
- [ ] One-click "open a ticket from this overdue plan" with audit trail
      linking ticket ↔ plan.

### 0.8.0 — Operational dashboard

- [ ] Manager view (`templates/dashboard/admin.html` modeled on
      `oee-calculator2.0/templates/admin/dashboard.html`): KPI tiles for
      active clients, active tickets, interventions today, due maintenance,
      tech capacity, latest interventions.
- [ ] Technician view (`templates/dashboard/operator.html` modeled on
      `oee-calculator2.0/templates/operator/dashboard.html`): no left
      sidebar, today's queue, one-tap "start intervention".
- [ ] Both dashboards meet the §1.3 P95 budget on the reference dataset.

### 0.9.0 — Hardening for 1.0

Feature freeze. Spend a milestone making §1 and §2 actually true.

- [ ] §1.1 functional completeness audit by walking the user journeys
      manually with the runbook.
- [ ] §1.3 perf budget — load reference dataset and verify; fix offenders.
- [ ] §1.4 security — pen-test pass on auth + CSRF + RBAC + headers + uploads.
- [ ] §1.5 observability — log review on a 24-h soak.
- [ ] §1.6 operability — backup → restore → smoke a full release dry-run.
- [ ] §1.7 documentation — user guide + operator runbook complete with
      screenshots.
- [ ] §1.8 compliance — GDPR export + forget endpoints implemented and
      tested.
- [ ] §2 — Lighthouse mobile run on every P1 page; fix anything < the
      thresholds in §2.6.
- [ ] §3.1 a11y — `axe-core` clean on every P1 page; manual keyboard pass.
- [ ] §3.2 i18n — `ro` catalog at 100% coverage of user-facing strings.

### 1.0.0 — Production-ready single-tenant

**Done when:** every checkbox in §1, §2, §3, and §4.0.9 is ticked.

- [ ] Tag `v1.0.0`; `release.yml` validates and publishes.
- [ ] Public REST API endpoints documented, schema frozen.
- [ ] DB schema covered by SemVer guarantees; migrations forward-only.
- [ ] LTS support pledge: critical fixes backported to `1.0.x` for 12 months.

## 5. 1.0.0 release exit checklist

A single page the release captain works through. Everything ✅ or no tag.

- [ ] §1.1–§1.8 — production-ready bar, all boxes.
- [ ] §2.1–§2.7 — phone-ready bar, all boxes.
- [ ] §3.1–§3.4 — cross-cutting, all boxes.
- [ ] §4 — every milestone's "Done when" met.
- [ ] [`CHANGELOG.md`](../CHANGELOG.md) `## [1.0.0]` populated, dated.
- [ ] [`VERSION`](../VERSION) reads `1.0.0`.
- [ ] `pip-audit` clean.
- [ ] Backup → restore round-trip on a copy of the prod DB succeeds.
- [ ] Manual real-device pass on iPhone + Android.
- [ ] Lighthouse PWA score ≥ 90 on dashboard, tickets list, ticket detail.
- [ ] [`docs/user-guide.md`](./user-guide.md) and
      [`docs/operator-runbook.md`](./operator-runbook.md) reviewed in the
      last 14 days.

## 6. Risks

- **Lighthouse budget on Postgres-cold dashboard.** First-paint after a
  redeploy can blow the LCP budget if the DB has gone cold. Mitigation:
  warm-up query in `/readyz`, plus a cheap server-rendered placeholder
  for the dashboard while data loads.
- **Service worker shipping a stale shell.** A bad service worker can
  pin users on broken assets. Mitigation: versioned cache key tied to
  `VERSION`; a one-line "skip waiting + reload" path on cache mismatch.
- **iOS PWA quirks.** iOS still has gaps (storage limits, no camera in
  installed PWAs in some configurations). Mitigation: every camera path
  also has a regular file-input fallback; tested on iOS each release.
- **Real-device QA.** No real devices in CI means manual passes per
  release. Acceptable for v1; revisit BrowserStack/Lambdatest in v1.x
  if the manual pass becomes a bottleneck.

## 7. Explicitly out of scope for 1.0

These are deferred — see [`ROADMAP.md`](../ROADMAP.md) "Beyond 1.0":

- Native iOS or Android apps.
- Offline write queue for technicians (1.2).
- Web Push notifications (1.1).
- Customer/portal UI (1.1).
- VMES/OEE integration (1.3).
- Quoting / invoicing / PDF (1.4).
- Multi-tenant SaaS hosting.
- Multi-region / blue-green / autoscaling deploys.
- Reporting / BI / saved reports (1.5).
