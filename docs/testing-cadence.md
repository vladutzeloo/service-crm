# Service-CRM — Testing Cadence

> Status: **planning.** Companion to [`python.tests.md`](../python.tests.md)
> (the *what* and *how*); this doc is the *when* and *on what device*.
> Every cadence item is gated on architecture sign-off per
> [`docs/architecture-plan.md`](./architecture-plan.md), like everything
> else pre-0.1.0.

## TL;DR

- The web app is tested by `pytest` on every PR (already speced in
  [`python.tests.md`](../python.tests.md)). From `0.2.0` onward, every PR
  also runs a Playwright smoke at desktop **and** Pixel-5-emulated mobile
  viewports. From `0.5.0` onward, a nightly job adds Postgres matrix +
  schemathesis fuzz + Lighthouse PWA audit on `main`.
- **The "Android app" is the same Flask app, served as a responsive PWA.**
  A separate native Android codebase is **not on the 0.1 → 1.0 roadmap**
  and would conflict with [`AGENTS.md`](../AGENTS.md) §"Project Truth"
  ("Do not suggest React, Next.js, SPA conversion, or a new frontend
  framework") and [`docs/tasks.md`](./tasks.md) §"Stop Conditions"
  ("Requested change would introduce a new stack"). The path to native,
  if ever needed, is in §6.
- Each `0.Y.0` minor release adds **exactly one** new test capability —
  no big-bang test suite. We land tests with the features they cover.
- Pre-tag, run the smoke checklist in §5. Friday afternoons, run the
  exploratory pass in §7.

## 1. The mobile decision

### 1.1 Why PWA, not native, for v1

| Need (from [`docs/service-domain.md`](./service-domain.md)) | PWA on Android Chrome | Native Android |
| --- | --- | --- |
| Add to home screen, app icon, splash | ✅ via manifest | ✅ |
| Camera (equipment photos) | ✅ `<input type="file" capture>` | ✅ |
| Geolocation (where intervention happened) | ✅ `navigator.geolocation` | ✅ |
| Offline ticket queue (1.2) | ✅ Service Worker + IndexedDB | ✅ |
| Push notifications (new ticket assigned) | ✅ Web Push (Android) | ✅ FCM |
| Single source of truth for forms / validation / auth | ✅ | ❌ duplicates the web |
| One test stack | ✅ pytest + Playwright | ❌ pytest + JUnit + Espresso + emulator CI |
| Background services, NFC, advanced biometrics | ❌ | ✅ |

The last row is the only real tradeoff. None of those features appear in
the v1 service-domain or roadmap. PWA wins until they do.

### 1.2 What this means for testing

- One codebase = one test pyramid. Mobile-specific assertions live in the
  same Playwright suite, parameterized by device profile (`Pixel 5`,
  `iPhone 13` post-1.0).
- "Mobile" coverage = a viewport matrix on the same end-to-end tests, plus
  a Lighthouse PWA audit gate from `0.8.0` onward.
- Real-device passes happen in the Friday exploratory session (§7), not in
  CI. CI runs emulated viewports.

## 2. Layers and tooling (recap)

The columns extend the table in [`python.tests.md`](../python.tests.md) §2.

| Layer | Tooling | Target speed | First lights up |
| --- | --- | --- | --- |
| Lint / type | `ruff`, `mypy` | < 5 s | 0.1.0 |
| Unit | `pytest -m unit` | < 1 s | 0.1.0 |
| Integration (SQLite) | `pytest -m integration` | < 30 s | 0.1.0 |
| Integration (Postgres matrix) | same suite, `DATABASE_URL=postgresql://…` | < 60 s | 0.1.0 (nightly) |
| Server e2e | `pytest -m e2e` (Flask `test_client`) | < 60 s | 0.1.0 |
| Browser e2e (desktop) | Playwright (Python) | 1 – 3 min | 0.2.0 |
| Browser e2e (mobile viewport) | Playwright + `Pixel 5` device profile | 1 – 3 min | 0.2.0 |
| Visual regression | Playwright snapshot diffs | < 1 min | 0.2.0 |
| API contract / fuzz | `schemathesis` against `openapi.yaml` | 1 – 2 min | 0.5.0 (nightly) |
| FTS parity (SQLite ↔ Postgres) | dual-DB integration test | < 30 s | 0.6.0 |
| Scheduler / time | `freezegun` + idempotency runs | < 30 s | 0.7.0 |
| Lighthouse PWA audit | `@lhci/cli` against staging | < 1 min | 0.8.0 (nightly) |
| Load | Locust against seeded reference DB | 5 – 10 min | 0.9.0 (pre-tag) |
| Migration up + down | `pytest-alembic` | < 60 s | 0.9.0 |
| Backup / restore drill | shell script wrapping `pg_dump` / `pg_restore` | 2 – 5 min | 0.9.0 (nightly) |

## 3. Triggers

### On every PR (must finish in ≤ 8 min)

- `ruff` + `mypy`.
- `pytest -m "not slow"` on SQLite (unit + integration + server e2e).
- Playwright smoke (≤ 6 tests) at desktop **and** Pixel-5 viewports —
  light once 0.2.0 lands.
- Visual snapshot diffs — light once 0.2.0 lands.
- Coverage gate (85 % line + branch) — enforced from 0.3.0; advisory
  before that.

### Nightly, on `main`

- Full integration suite against Postgres 15 **and** Postgres 16.
- Full Playwright matrix (Chromium-desktop, Chromium-Pixel-5,
  Firefox-desktop).
- `schemathesis run openapi.yaml` (light from 0.5.0).
- `pytest-alembic up/down/up` round-trip (light from 0.9.0).
- Lighthouse CI PWA audit (light from 0.8.0; gate threshold set at 0.9.0).
- Backup → wipe → restore → row-count assertion (light from 0.9.0).

### Pre-tag (before every `0.Y.0`)

- All nightly suites green on the candidate SHA.
- Locust against the seeded reference dataset (`10k clients, 50k tickets`);
  P95 page < 300 ms (gate from 0.9.0; advisory before that).
- Manual smoke checklist (§5) signed off in the PR description.
- `CHANGELOG.md` + `VERSION` consistency check (already in
  `.github/workflows/release.yml`).

### Weekly (Friday, 30 min)

- Manual exploratory pass on a real Android phone + a desktop browser
  against the staging build. Findings → §7.

## 4. Per-version cadence (0.1 → 1.0)

Each minor adds **exactly one** new capability. The previous capabilities
remain enforced.

### 0.1.0 — walking skeleton

- Land: `pytest` config, the fixtures from
  [`python.tests.md`](../python.tests.md) §3, `factory-boy` skeleton,
  `ruff`, `mypy`, coverage measurement (gate not yet enforced).
- PR gate: lint + types + unit + integration + server e2e on SQLite.
- Nightly: same suite on Postgres 15 + 16.
- No browser tests yet — there are no UI macros to assert on.

### 0.2.0 — UI foundation

- Land: Playwright (Python) installed; one mocked-data showcase route
  that renders every macro. Smoke test asserts topbar, KPI card, table,
  filter, form-shell, tabs all paint and pass basic a11y checks
  (`axe-core` integration).
- Mobile viewport (`Pixel 5`) included from day one — same showcase,
  asserts no horizontal scroll, tap targets ≥ 44 px.
- Visual snapshots committed for the showcase page; diffs reviewed in PRs.

### 0.3.0 — Clients & contacts

- Land: `ClientFactory`, `ContactFactory`, `LocationFactory`. CSV import
  covered by integration tests with golden fixture files. Soft-delete
  invariant verified by a Hypothesis stateful test
  (`is_active=False ⇒ list_active() excludes; get_for_history() includes`).
- **85 % coverage gate switches from advisory to enforced.**
- Mobile-viewport smoke covers `/clients` and `/clients/<id>`.

### 0.4.0 — Equipment / installed base

- Land: cross-FK constraint test —
  `Equipment.location_id`, when set, must belong to `Equipment.client_id`.
  Asserted at the SQLAlchemy event-listener layer **and** via service-layer
  integration tests (defense in depth catches the bug whichever side
  regresses).
- CSV golden fixtures for equipment.

### 0.5.0 — Tickets & interventions

- Land: Hypothesis state-machine test for the ticket status FSM.
  **≥ 95 % line + branch on `service_crm/tickets/state.py`** (already a
  ROADMAP gate).
- Land: Playwright e2e for `open → schedule → intervention → resolve →
  close`, run at desktop **and** Pixel-5 viewports.
- Light up the **schemathesis nightly** against `openapi.yaml` (the
  ticket blueprint exposes the first JSON endpoints).

### 0.6.0 — Knowledge: checklists & procedures

- Land: snapshot test for `ChecklistRun` frozen template (golden JSON):
  editing the template after the fact must not mutate any historical run.
- Land: FTS parity test — the same query against SQLite FTS5 and Postgres
  `tsvector` must return the **same result set** for a fixture query, and
  the expected record must appear in the **top N** (N=3) on both engines.
  Ordering within that set is **not** asserted: the engines use different
  scoring algorithms (BM25 vs. `ts_rank`), so byte-for-byte rank parity
  would be flaky. Catches the "works in dev, surprises in prod" class of
  search bugs without chasing scoring noise.

### 0.7.0 — Maintenance planning

- Land: APScheduler tests with the `frozen_clock` fixture. Idempotency
  test: running the `recompute_next_due` job twice yields identical DB
  state.
- Land: Hypothesis invariants over `cadence_days` arithmetic
  (`next_due_at >= last_done_at + cadence_days` always; cadence change
  re-bases correctly).

### 0.8.0 — Operational dashboard

- Land: contract tests for the dashboard JSON endpoint (if exposed) +
  Playwright visual snapshots of the admin and technician dashboards at
  desktop and Pixel-5 viewports.
- **Lighthouse CI PWA audit becomes a nightly job** (gate threshold to be
  set with the first run; provisionally PWA ≥ 80).

### 0.9.0 — Hardening for 1.0

- Land: Locust load test against a seeded reference dataset
  (10 k clients, 50 k tickets, 200 k interventions).
  **P95 page < 300 ms gate** matches the ROADMAP commitment.
- Migrations tested forward **and** backward via `pytest-alembic`
  (`up → down → up` round-trip on a representative DB).
- Backup / restore drill scripted and run nightly.
- `pip-audit` on every PR; high-severity advisories block merge.
- **Lighthouse PWA gate raised to ≥ 90** on the audited routes
  (`/`, `/dashboard`, `/tickets`).

### 1.0.0 — Production-ready

- Land: HTTP route surface and DB schema treated as public.
  A `tests/contracts/snapshot_v1.{openapi.yaml,schema.sql}` fixture is
  committed; any PR that mutates either fails CI unless the diff is
  acknowledged in `CHANGELOG.md` under a `### Schema/API` heading.
- **Migration policy from 1.0.0 onward:**
  - `downgrade()` implementations remain **required for dev/test** so
    `pytest-alembic` (landed at 0.9.0) can run the `up → down → up`
    round-trip. They exist for local resets and for the schema test
    matrix, not for production.
  - **Production rollback is roll-forward only.** Reverting a deployed
    change means writing a *new* migration that undoes it (with whatever
    data-preservation logic the situation needs) — never running
    `downgrade()` against a production database.
  - **Shipped migrations are immutable.** Once a migration file appears
    under `service_crm/migrations/versions/` in a tagged release, its
    body is frozen. Bug fixes go in a *new* migration that supersedes
    the old one.
  - **CI enforcement** (automatable, not heuristic): a `migration-immutability`
    job runs `git diff <previous-tag>..HEAD -- service_crm/migrations/versions/`
    and fails if any already-shipped file is modified or deleted. This
    catches the real failure mode (silently editing a migration that has
    already run against a real database) without trying to classify
    `downgrade()` bodies as "destructive" — many legitimate downgrades
    drop columns or constraints, and that classification is not worth
    automating.

## 5. Pre-tag smoke checklist

Short and human-runnable. Re-run before every `0.Y.0` tag. Paste the
list into the release PR description and tick each item.

- [ ] `flask reset-db && flask seed` against a clean Postgres → app boots.
- [ ] Login as admin, technician, owner — RBAC matrix observed in topbar
      (admin sees everything, technician sees the queue, owner sees the
      dashboard).
- [ ] Create client → register equipment → open ticket → schedule →
      log intervention → close. Audit log shows all transitions.
- [ ] Repeat the same flow on Android Chrome at the 360 × 800 viewport.
- [ ] "Add to Home Screen" on Android: icon appears, splash works,
      offline cached pages resolve (from 1.2.0; advisory until then).
- [ ] Backup → wipe → restore → spot-check 5 random tickets match
      pre-backup state.
- [ ] `CHANGELOG.md` `## [Unreleased]` is empty; new entries are under
      the new tag.

## 6. If we ever go native (out of scope for 0.1 → 1.0)

A native Android app would conflict with [`AGENTS.md`](../AGENTS.md) and
[`docs/tasks.md`](./tasks.md) "Stop Conditions". If the trigger is real,
this is the path:

1. **ADR under `docs/adr/`** documenting the trigger — a feature PWA
   demonstrably cannot deliver (e.g., Android-only background service,
   deep NFC, exotic biometrics). "We'd prefer a native feel" is **not** a
   trigger; the PWA must be measurably insufficient.
2. **Roadmap entry post-1.0**, not earlier. The web product must stand on
   its own first.
3. **Recommended stack if it happens:**
   - Kotlin + Jetpack Compose (single-language, modern test story).
   - Talks to a versioned `/api/v1/*` blueprint over JSON — never the HTML
     routes.
   - API client generated from `openapi.yaml`; the spec stays the single
     source of truth.
4. **Recommended test stack:**
   - JUnit 5 + Kotest for unit tests (JVM, no instrumentation, < 5 s).
   - Compose UI tests for screen-level testing — fast, no emulator needed.
   - One Espresso instrumented test per release for the golden flow on a
     real Android emulator (Firebase Test Lab matrix, 3 devices).
   - Contract testing: Pact (or hand-written contract tests) against the
     same `openapi.yaml` schemathesis already fuzzes server-side. Drift
     fails CI on either side.
   - CI: PR runs unit + Compose. Nightly runs the emulator matrix.
     Emulator job is allowed to be slow — never on the PR critical path.
5. **What crosses the boundary:** only `openapi.yaml` and a small set of
   validation rules (regex, length limits) — generated from one source,
   never hand-mirrored.

Writing this section now keeps the option **cheap**, not committed.

## 7. Manual exploratory testing

- 30-minute timebox, every Friday afternoon.
- Scope rotates weekly: clients, tickets, dashboards, mobile viewport,
  technician role, owner role, edge data (empty states, very long names,
  Unicode, RTL).
- Tools: BugMagnet bookmarklet, Chrome DevTools network-throttling
  ("Slow 3G"), real Android phone for one in-four sessions.
- Every reproducible bug becomes a **failing test before it is fixed**.
  This is non-negotiable — exploratory findings that don't become
  regression tests will recur.
- Log session findings as one bullet each in `docs/test-journal.md`
  (one file per quarter, append-only). The journal is *not* a bug
  tracker; it's a memory aid for the rotating tester.

## 8. Open questions

- Lighthouse PWA score threshold: provisionally ≥ 80 from 0.8.0, ≥ 90
  from 0.9.0. Calibrate against the first audit run; do not tune in
  advance.
- Visual snapshot tolerance: per-pixel vs. perceptual diff. Decide at
  0.2.0 with the first showcase page.
- FTS parity granularity (0.6.0): resolved — assert set equality + the
  expected record's presence in the top N, never within-set ordering. See
  §4 "0.6.0".
- `docs/test-journal.md` retention: append-only quarterly file vs. yearly
  rollup. Decide after the first quarter has data.
