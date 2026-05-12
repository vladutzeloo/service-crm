# Ease-of-use audit & remediation plan

> Output of an ease-of-use audit of the shipped 0.4.0 surface
> (auth + clients + equipment + lookups + shell), drafted 2026-05-12
> on branch `claude/audit-app-usability-1s2Rb`.
>
> This is a **plan**, not an implementation. Every section below is a
> branch in the design space; the choices in §5 are the ones we propose
> to build. Open questions in §8 are answered in the PR review thread,
> not here.
>
> Companion to:
> - [`v1-implementation-goals.md`](./v1-implementation-goals.md) §3.5 —
>   the *bar*. This audit grades the *existing* surface against it.
> - [`v0.5-plan.md`](./v0.5-plan.md) §4.2 — the bar applied to the
>   *next* milestone (tickets). This audit covers the milestones that
>   *already shipped* (0.1 – 0.4) and slots remediation into 0.4.1 +
>   0.5 + 0.9.
> - [`ARCHITECTURE.md`](../ARCHITECTURE.md) §2 — persona definitions
>   (front-desk, manager, technician, read-only).
> - [`AGENTS.md`](../AGENTS.md) "UI Rules" — non-negotiables (no
>   sidebars on technician screens, no emoji, no gradients,
>   oee-calculator2.0 vocabulary, light mode default).

## 1. Why now

ROADMAP §0.5.0 is the **first** milestone graded against
[§3.5](./v1-implementation-goals.md#35-ease-of-use-4-dimensions--3-personas-05--09).
That bar is forward-looking: it tells future slices what "good" means.
It does **not** retroactively grade what's already on `main`.

This audit fills the gap. Three reasons it matters now and not after
tickets ship:

1. **The shell, the login page, and the data-entry forms ship into
   every persona's daily workflow.** Bugs here are felt 50× a day per
   user, not once a week.
2. **Tickets (v0.5) inherits everything broken in the shell.** Status
   pill as transition button doesn't help if the user lands on
   `/version` after login. "My queue" topbar link doesn't help if eight
   sibling links are dead.
3. **The bar was adopted on 2026-05-12** — the same day this audit
   was written. The 0.4 surface was built before the bar existed; it
   needs an explicit pass against it before 0.5 layers on top.

## 2. Method

### 2.1 Inputs

- The §3.5 bar (4 dimensions × 3 personas = 12 cells).
- The single-dial test in §3.5: *"Can the target persona finish this
  flow in ≤ N taps without leaving the page, with the right defaults,
  and recover gracefully from a network blip?"* — N = 3 (technician),
  5 (manager), 7 (front-desk).
- The 8 AGENTS.md "UI Rules" non-negotiables.
- The walked surface: 18 templates under
  [`service_crm/templates/`](../service_crm/templates/), 4 blueprints
  with live routes, the seed CLI, the service worker, and the
  manifest.
- Nielsen's 10 heuristics, applied lightly (we don't re-litigate
  decisions the project already made — light mode default,
  no-component-library, no-SPA).

### 2.2 Output shape

Findings are graded **P0 / P1 / P2**:

| Grade | Meaning | Resolution window |
| --- | --- | --- |
| **P0** | Blocks the §3.5 single-dial test for *any* persona, or violates a stated AGENTS.md UI rule, or breaks first-impression UX in < 30 s. | 0.4.1 hotfix (this plan, §6.1). |
| **P1** | Hits a §3.5 cell head-on but doesn't fully break the flow. Should ship before or alongside v0.5 so tickets inherits a clean shell. | 0.5.b / 0.5.c slices (§6.2). |
| **P2** | Real ease-of-use gap, but neither a §3.5 violation nor a stated rule conflict. Acceptable to defer to v0.9 hardening. | 0.9.0 (§6.3). |

Each finding cites a file path + line number so reviewers can verify
without re-walking the codebase.

### 2.3 What's explicitly out of scope

- **Tickets, maintenance, planning, knowledge, dashboards.** Their
  ease-of-use story lives in [`v0.5-plan.md`](./v0.5-plan.md) §4.2 and
  in the future per-milestone plans. This audit covers only what's on
  `main` at 0.4.0.
- **Server-side performance.** P95 budgets are in §1.3 of the goals
  doc; this audit doesn't re-grade them.
- **Visual design changes.** The OEE-calculator2.0 vocabulary is
  fixed (AGENTS.md). We don't propose colour, typography, or layout
  *language* changes — only fixes within the existing vocabulary.
- **i18n parity.** RO/EN catalogues are kept in sync per
  [`testing-cadence.md`](./testing-cadence.md); this audit checks that
  new strings the plan adds are translatable, not that existing
  strings are well translated.
- **Code style / refactors unrelated to UX.** AGENTS.md "Do not
  introduce unrelated refactors" applies.

## 3. Findings — P0 (block §3.5 or violate a stated rule)

### P0-1 — Post-login lands on `/version` (JSON)

[`auth/routes.py:40`](../service_crm/auth/routes.py) and
[`auth/routes.py:64`](../service_crm/auth/routes.py) redirect to
`url_for("health.version")` for both *already-authenticated* GETs and
successful POST submissions. `/version` is a JSON endpoint
([`health.py:25-27`](../service_crm/health.py)) that returns
`{"version": "0.4.0", "message": "Service version."}`.

**Why P0:** every persona's first interaction after sign-in is a wall
of JSON. The single-dial test fails before it starts — there's no
"flow" to finish; the user has to manually navigate to `/clients/` or
`/equipment/`. Reading the URL bar is not a flow.

### P0-2 — Eight of eleven sidebar links are dead

[`base.html:27`](../service_crm/templates/base.html) `Dashboard`,
[`:32`](../service_crm/templates/base.html) `Tickets`,
[`:33`](../service_crm/templates/base.html) `Maintenance`,
[`:34`](../service_crm/templates/base.html) `Planning`,
[`:39`](../service_crm/templates/base.html) `Knowledge`,
[`:42`](../service_crm/templates/base.html) `Users`,
[`:43`](../service_crm/templates/base.html) `Audit Log`,
[`:44`](../service_crm/templates/base.html) `Settings` all point at
`href="#"`. The Dashboard link additionally carries `.is-active`
unconditionally — it looks selected from `/clients/`, `/equipment/`,
and every detail page.

**Why P0:** the sidebar is the *first thing* a user reads in the app.
Clicking eight of eleven links does nothing. The `.is-active` class
on a dead link is worse than no class at all (Nielsen #1, visibility
of system status). First-impression damage is severe and immediate.

### P0-3 — Sidebar on every authenticated screen contradicts a stated rule

[`AGENTS.md`](../AGENTS.md) "UI Rules" line:
*"Avoid left sidebars in main technician screens."*

[`base.html:23-65`](../service_crm/templates/base.html) ships exactly
that sidebar for every authenticated page (including any future
technician page). It does collapse to a drawer below 900 px
([`app.js`](../service_crm/static/js/app.js) drawer toggle), which
partially mitigates the rule for phones — but desktop technician
screens (which exist whenever a technician triages from a laptop) still
see the sidebar.

**Why P0:** the rule is explicit and the implementation contradicts
it. Either the rule changes (with AGENTS.md updated) or the shell
changes. Both are doable; the question is which. See §5.1.

### P0-4 — Login page does not extend the shell

[`auth/login.html:1-5`](../service_crm/templates/auth/login.html)
comment: *"v0.1.0 placeholder. Does NOT extend base.html — that
template lands in 0.2.0 (see ROADMAP.md). When the OEE-derived shell
arrives this file is rewritten to extend `base.html` …"*

The shell landed in 0.2.0. The placeholder didn't move. Login is now
two milestones overdue for shell extension. It carries its own inline
`<style>` (with hardcoded `#1a73e8` blue), its own RO/EN switch, its
own flash-message renderer.

**Why P0:** first user impression is *visually inconsistent with the
rest of the app*. The brand colour (`--accent`, red `#dc2626` per
manifest) is missing on the login page. The shell's CSS tokens
(`--tap-min` for touch targets) don't apply. Lighthouse-mobile won't
grade the login page against the same a11y bar as the rest of the
app. The §3.5 *Speed-to-action* and *Phone ergonomics* cells silently
fail on the one page every user sees.

### P0-5 — `--tap-min` contract is enforced for the smoke page but not the login page

[`tests/e2e/test_touch_targets.py`](../tests/e2e/test_touch_targets.py)
enforces the 44 pt tap target on `/dev/macro-smoke`. The login page
carries its own inline CSS with no reference to `--tap-min` —
[`auth/login.html:32-42`](../service_crm/templates/auth/login.html) —
so the contract is unenforced on the one form every persona uses.

**Why P0:** the §3.5 *Phone ergonomics* cell for *every* persona
explicitly requires ≥ 44 pt taps. The login page is technically
out-of-scope for the smoke test but in-scope for the bar.
Auto-resolves with P0-4 (extending the shell pulls the tokens in).

## 4. Findings — P1 (hit a §3.5 cell, ship with or before v0.5)

### P1-1 — No search-as-you-type on clients/equipment lists

[`clients/list.html:11-19`](../service_crm/templates/clients/list.html)
ships a full-page-reload search form with an explicit submit button.
The equipment list mirrors it.

§3.5 *Findability / Front-desk* requires:
> *search-as-you-type on every list page; results in ≤ 300 ms P95 on
> the seeded reference dataset (matches §1.3 budget). Server-rendered
> with a tiny vanilla-JS debouncer (no framework).*

[`v0.5-plan.md`](./v0.5-plan.md) §4.2 schedules this for tickets in
0.5.b. Front-desk hits clients and equipment search 50× / day; the
debouncer is a 20-LOC vanilla JS module that backports cheaply.

### P1-2 — No "My queue" or any role-aware topbar entry

[`base.html:80-109`](../service_crm/templates/base.html) topbar
actions are: clock, notifications stub (always shows `0`), help stub,
theme, language. None of them are role-aware. The technician persona
has no shortcut to "the work currently on me", and there's no obvious
home for one without redesigning the sidebar.

§3.5 *Findability / Technician* requires the link explicitly. v0.5.b
adds the link in `base.html`. P1 here means: **don't wait for v0.5 to
have a structural slot for it** — wire the topbar to accept
role-aware entries now, so 0.5.b is a one-line addition.

### P1-3 — Notifications icon and Help icon are placebos

[`base.html:82-89`](../service_crm/templates/base.html). The bell
icon always shows `0`. The help icon does nothing.

Why P1: violates Nielsen #1 (visibility of system status) and #10
(help). Better to hide both than ship them with no behaviour. Help
in particular is a documentation-discovery moment that every persona
uses in the first hour and never again — it pays for itself once.

### P1-4 — Required-field state is invisible until submit

Every form in the app uses the same pattern:
[`clients/edit.html`](../service_crm/templates/clients/edit.html),
[`equipment/edit.html`](../service_crm/templates/equipment/edit.html),
[`clients/detail.html:101`](../service_crm/templates/clients/detail.html)
modal forms. Labels render with no asterisk or "required" pip; users
discover required-ness only by submitting an empty form and reading
the `.field-error` text.

§3.5 *Forgiving workflow* implies recovering from input errors
without re-typing. Today, the user types four fields, hits Save,
sees one error, and is unsure if the others passed. The fix is a
*single* shared pattern in
[`macros/form_shell.html`](../service_crm/templates/macros/form_shell.html)
and one CSS rule: when a field's `<label>` is for a `required` input,
append a translatable hint (`{{ _("required") }}`) or render the
`*` glyph with `aria-label="required"`.

### P1-5 — Destructive actions use raw `confirm()` with no reason

[`clients/detail.html:84,150,183,250`](../service_crm/templates/clients/detail.html),
[`equipment/detail.html:48,94`](../service_crm/templates/equipment/detail.html).
Every destructive action is gated by an `onclick="return confirm(…)"`
prompt. There's no captured reason and no per-action wording.

§3.5 *Forgiving workflow / Manager* requires:
> *every destructive action (`cancel`, `close`, delete attachment /
> comment) requires a reason, stored on the audit / history row
> (`reason_code` + free-text `reason`). The audit row is the undo
> trail.*

[`v0.5-plan.md`](./v0.5-plan.md) §4.2 ships this for tickets.
Generalising the modal-with-reason pattern in 0.5.b and applying it
to client / equipment / contact / location / contract / warranty
deletes is the same change.

### P1-6 — No per-user saved filters anywhere

§3.5 *Findability / Manager* requires saved filters on every list
with ≥ 2 selectable rows. Today: clients and equipment lists carry
exactly one filter dimension each (`show=active|all` and the
equipment client filter), and they're query-string only.

Why P1: 0.5.b introduces `user_<entity>_filter` table for tickets;
the same pattern should land on clients + equipment in the same
slice. Otherwise we ship three months of "tickets is the only place
filters stick" — and managers won't know which list saves and which
doesn't.

### P1-7 — Modals duplicate forms per row (page weight scales linearly)

[`clients/detail.html:117-228`](../service_crm/templates/clients/detail.html)
renders one *new*-modal + *N* *edit*-modals per record per tab. For a
client with 50 contacts + 50 locations + 50 contracts, the page emits
~150 hidden `<form>` blocks. Memory and DOM size grow O(N); the
shell parses, lays out, and audits a11y for every one.

Why P1: it's a pattern the rest of the app will adopt (tickets'
detail tabs will hit this), so the fix is a *single* shared affordance
— a single edit modal that fetches/renders per click — applied
before tickets cements the per-row pattern.

### P1-8 — No "create one" CTA in empty states

[`clients/list.html:67`](../service_crm/templates/clients/list.html)
passes `empty=_("No clients found.")` to the `data_table` macro.
[`equipment/detail.html:146,150`](../service_crm/templates/equipment/detail.html)
empty states say "Tickets land in v0.5" / "Maintenance plans land in
v0.7" without any forward action.

Why P1: §3.5 *Speed-to-action* asks for the create button to be one
click. The empty state is the highest-information moment to surface
the primary action; right now the user has to scroll back up to the
"New client" button.

### P1-9 — The `is-active` sidebar marker is hardcoded to Dashboard

[`base.html:27`](../service_crm/templates/base.html) — `class="nav-link
is-active"` regardless of `request.endpoint`. Users on `/clients/`
see Dashboard highlighted.

Nielsen #1 (visibility of system status) failure. Trivial fix: a
template macro `nav_link(endpoint, label, icon)` that adds
`is-active` only when `request.endpoint.startswith(prefix)`. Lands
in 0.4.1 alongside P0 fixes.

### P1-10 — Lookup tables hidden under `/equipment/...`

[`equipment/controllers_list.html`](../service_crm/templates/equipment/controllers_list.html)
and
[`equipment/models_list.html`](../service_crm/templates/equipment/models_list.html)
exist but the sidebar has no link to them. The user mental model is
"Settings → Lookups". Today they're reachable only by direct URL or
by clicking through the equipment form (no affordance to open them
from an empty dropdown either).

Why P1: AGENTS.md "Catalogue" section already exists in the sidebar;
adding "Equipment models" / "Controller types" as sub-items is a
non-destructive addition, but doing it now (before tickets ships its
own type/priority lookups under `/tickets/...`) avoids a worse
discoverability cliff in v0.5.

## 5. Findings — P2 (real gaps, defer to v0.9 hardening)

### P2-1 — No first-run admin bootstrap

Users are seeded by `flask seed` (CLI). For a self-hostable single-
tenant app, this is steep onboarding. A first-run "create the first
admin" form would mirror the OEE Calculator pattern.

Defer to v0.9 — §1.6 *Operability* covers it ("`docker compose up`
< 60 s"; doesn't currently say "to a usable app"). Worth a follow-up
note in the v0.9 plan.

### P2-2 — No password reset / change password

Basic auth hygiene, not currently in v1 scope. ROADMAP doesn't list
it. Adding to §1.4 *Security* would be the home.

### P2-3 — No CSV preview before import

[`clients/import.html`](../service_crm/templates/clients/import.html)
posts the file blind. Row-level errors come back as flash messages,
which is the §0.3.0 acceptance criterion — adequate but not "great".
A two-step (upload → preview → confirm) flow would be friendlier;
defer until the upload pipeline is touched by 0.5.c anyway.

### P2-4 — Pagination shows page number but not total count

[`clients/list.html:69-81`](../service_crm/templates/clients/list.html)
shows "Page %(p)s" with no total. Users can't tell "am I on the
last page?" except by trying to click "Next".

Cheap fix: pass `total` to the template (already computed for the
`total > 50` guard) and render "Page %(p)s of %(total_pages)s
(%(total)s results)". Could ship anytime; logical home is 0.5.b
when bulk-select and saved filters land.

### P2-5 — No keyboard shortcuts

Power-user feature. `Ctrl+K` for global entity search, `n` for new
on a list page. Defer to v0.9.

### P2-6 — No CSV export from list pages

Operators sometimes want to email a list of clients to a customer.
Defer to v0.8 (dashboard ships CSV export per the goals doc).

### P2-7 — No "recently viewed" memory

Useful for high-frequency operators but defer-able. A 5-item
`session["recent"]` ring buffer is the trivial implementation.

### P2-8 — No theme indication beyond icons in the topbar

[`base.html:90-94`](../service_crm/templates/base.html) — sun/moon
icons. Accessible label is set; visual hint that "you can toggle
this" is fine. Acceptable; defer indefinitely.

### P2-9 — "Operator" role label is hardcoded

[`base.html:62`](../service_crm/templates/base.html) — every user
sees "Operator" under their email. The user model has a role
relationship; this should read from it. Tiny fix; ship in 0.4.1 as
an opportunistic addition.

### P2-10 — No global entity search

A "find anything" search across clients + equipment (+ tickets in
0.5+) is high-leverage. Defer to v0.8 dashboard work.

## 6. Plan

### 6.1 0.4.1 — Ease-of-use hotfix slice

**Goal:** every P0 fixed, plus the P1 fixes that don't require new
data models or new routes. Ships *before* 0.5.a opens so the ticket
work starts on a clean shell. **Size:** ~600 LOC including tests
(~250 app, ~350 tests). One PR; one alembic migration **not** needed.

#### 6.1.1 Scope

| Finding | Change | Files touched |
| --- | --- | --- |
| P0-1 | Post-login lands at `/clients/`. `/version` stays as the machine endpoint, but `/` (new) is added for humans: redirect to `/clients/` if authenticated, else to `/login`. `auth.login` after-login fallback (line 64) changes to `clients.list_clients`. | [`auth/routes.py`](../service_crm/auth/routes.py), new `service_crm/landing.py` (≤ 30 LOC blueprint), `templates/landing/index.html` not needed — pure redirect |
| P0-2 | Stub nav links are visibly *disabled* (cursor: not-allowed, muted text, `aria-disabled="true"`, no `href`), with a translatable "Coming in v0.X" tooltip via `title=` and `aria-describedby`. The `.is-active` class moves off `Dashboard` (which doesn't exist yet — re-styled as a "no link" header until 0.8). | [`templates/base.html`](../service_crm/templates/base.html), `templates/macros/nav_link.html` (new), `static/css/style.css` (+~20 LOC) |
| P0-3 | **Sidebar stays** (with rationale captured in [`docs/ui-reference.md`](./ui-reference.md) — see §5.1 of this audit and Open Question §8.1 for the proposed AGENTS.md amendment). What changes: technician screens get a bottom-fixed action bar from 0.6 onwards (per §3.5); on phones the sidebar already collapses to a drawer. AGENTS.md gets a one-line amendment: *"Sidebar is allowed; it must collapse to a drawer below 900 px and a bottom-fixed action bar must be present on technician-primary screens (intervention, ticket detail)."* | [`AGENTS.md`](../AGENTS.md), [`docs/ui-reference.md`](./ui-reference.md) |
| P0-4 | `auth/login.html` rewritten to extend `base.html` with a `{% block content %}` that uses `form_shell`. The inline `<style>` block is deleted. The inline RO/EN switch is deleted (topbar already carries it; on `auth.login` it's preserved because the topbar's hidden inputs already round-trip `?next=`). The shell hides the sidebar on unauthenticated pages via `data-shell="anon"`. | [`auth/login.html`](../service_crm/templates/auth/login.html), [`base.html`](../service_crm/templates/base.html) |
| P0-5 | Auto-resolves with P0-4 (shell extension pulls `--tap-min`). E2E touch-target test extended to walk `/login` as well. | [`tests/e2e/test_touch_targets.py`](../tests/e2e/test_touch_targets.py) |
| P1-3 | Bell + help icons are hidden behind feature flags (`config.NOTIFICATIONS_ENABLED`, `config.HELP_PORTAL_URL`). Default off. When help URL is configured, the icon opens it in a new tab. | [`base.html`](../service_crm/templates/base.html), [`config.py`](../service_crm/config.py) |
| P1-4 | `form_shell` macro renders a `<span class="required-pip" aria-label="{{ _('required') }}">*</span>` after labels when the bound field has the `required` flag. Single change, ~10 LOC, applies to every form already using the macro. | [`templates/macros/form_shell.html`](../service_crm/templates/macros/form_shell.html), `style.css` (one new rule) |
| P1-8 | `data_table` macro accepts an optional `empty_action={"href": ..., "label": ..., "icon": ...}` parameter. When supplied, the empty state renders a centred primary button. | [`templates/macros/data_table.html`](../service_crm/templates/macros/data_table.html), call sites in `clients/list.html`, `equipment/list.html`, `equipment/detail.html`, `clients/detail.html` |
| P1-9 | New `nav_link(endpoint, label, icon)` macro: adds `is-active` when `request.endpoint == endpoint` or starts with the endpoint's blueprint prefix. Used by every sidebar link. | [`templates/macros/nav_link.html`](../service_crm/templates/macros/nav_link.html) (new), `base.html` |
| P1-10 | Sidebar gains a "Settings → Lookups → Equipment models / Controller types" section, gated to admin role. (Other "Admin" sub-items stay disabled per P0-2.) | `base.html`, `templates/macros/nav_link.html` |
| P2-9 | `base.html:62` reads `current_user.role.code` instead of the hardcoded "Operator" string. Role label translated via `_("role.admin")` / `_("role.manager")` / `_("role.technician")` / `_("role.readonly")` lookup. | `base.html`, new `service_crm/shared/role_labels.py` (≤ 20 LOC) |

#### 6.1.2 Tests

- `tests/auth/test_routes.py`: assert post-login lands at
  `/clients/`, not `/version`. Assert `/` redirects appropriately
  based on auth state.
- `tests/templates/test_base_shell.py` (new): assert disabled nav
  links carry `aria-disabled="true"` and no `href`. Assert
  `is-active` follows `request.endpoint`.
- `tests/auth/test_login_page.py` (new): assert the login page
  extends `base.html` (presence of `<aside class="sidebar">` is
  *absent* on unauthenticated pages — assert the body has
  `data-shell="anon"`). Touch-target audit extended.
- `tests/templates/test_form_shell.py` (new): assert `required-pip`
  renders for required fields and not for optional ones; assert
  `aria-label` is set.
- All flow under the existing `pytest -m "not slow"` < 60 s gate.

#### 6.1.3 Definition of done

- [ ] Every P0 in §3 ticked.
- [ ] Every P1-3, P1-4, P1-8, P1-9, P1-10 in §4 ticked.
- [ ] `pytest` + `mypy --strict` + `ruff check` + `ruff format --check`
      clean.
- [ ] axe-core audit clean on `/login`, `/clients/`, `/equipment/`,
      `/clients/<hex>`, `/equipment/<hex>`.
- [ ] Lighthouse mobile on `/login` Performance ≥ 90,
      Accessibility ≥ 95 (parity with the smoke page).
- [ ] AGENTS.md amendment landed in the same PR.
- [ ] [`CHANGELOG.md`](../CHANGELOG.md) entry under `## [Unreleased]`
      named "Ease-of-use hotfix".

### 6.2 0.5 — Bar-aligned remediation alongside tickets

Folded into the existing v0.5 slices. **No new milestone** — these
items extend slices in [`v0.5-plan.md`](./v0.5-plan.md) by ~150 LOC
each.

| Finding | Lands in slice | Change |
| --- | --- | --- |
| P1-1 | 0.5.b (where the search-as-you-type module is *first* written) | The vanilla-JS debouncer module is written generically (data attribute `data-search-form="<endpoint>"`); applied to clients + equipment in the same PR. ~30 LOC JS shared, ~5 LOC HTML per list. |
| P1-2 | 0.5.b | When the "My queue" link lands in `base.html`, the topbar gains a `topbar_role_links` slot (template block) so future role-aware entries (technician's queue, manager's overdue tickets) plug in without sub-classing. Empty for non-technicians today. |
| P1-5 | 0.5.b/c (where the destructive-action modal is *first* written) | The reason-required modal generalises: `confirm_modal(action, reason_required=True/False, reason_codes=[...])` macro. Applied to clients / equipment / contacts / locations / contracts / warranties deletes in 0.5.c after tickets validates the pattern. The audit row gains `reason_code` + `reason` columns. |
| P1-6 | 0.5.b | The `user_<entity>_filter` table is introduced as a single polymorphic table (`user_filter` with an `entity` discriminator column) rather than per-entity tables, so clients + equipment + tickets all save filters through the same model. ~80 LOC delta vs. ticket-only design. |
| P1-7 | 0.5.b | The per-row modal duplication pattern is replaced *across the app* in 0.5.b. New shared macro: `inline_edit_modal(row_id, fetch_url)` — emits one modal stub per page; the form HTML is fetched on demand. (No JS framework; vanilla `fetch` + `replaceChildren` + the existing `data-modal-open` toggle.) Removes ~200 LOC of duplicated template per detail page. |
| P2-4 | 0.5.b | `data_table` macro accepts a `pagination=` dict and renders "Page N of M (T results)". Backport to clients + equipment + tickets in the same PR. |

### 6.3 0.9 — Pre-1.0 hardening

P2-1 (first-run admin), P2-2 (password reset), P2-5 (keyboard
shortcuts), P2-7 (recently viewed). Each is < 200 LOC and orthogonal;
together they round out the §3.5 *Forgiving workflow* + *Phone
ergonomics* cells for the technician persona.

| Finding | Change |
| --- | --- |
| P2-1 | New `/setup` route, gated by `User.query.count() == 0`. Once a user exists, the route 404s. Single form: email + password + confirm. Creates the user with `admin` role. |
| P2-2 | `Auth.request_password_reset` route + token table (one-time, 1 h TTL). Email sending behind a no-op driver in dev; SMTP driver for prod (covered by §1.6). |
| P2-5 | Single ≤ 60 LOC vanilla JS module: `Ctrl+K` opens a quick-jump modal listing client + equipment + ticket entry points; `n` on a list page navigates to `<entity>/new`; `g` then `c` jumps to clients (Vim-style). Documented in the help page. |
| P2-7 | A 5-item `session["recent"]` ring buffer updated in a `before_request` hook on `clients.detail` / `equipment.detail` / `tickets.detail`. Rendered in the topbar as a small "Recent" dropdown (collapsed by default; behind a feature flag for the first release). |

P2-3 (CSV preview), P2-6 (CSV export), P2-10 (global search), P2-8
(theme), P2-9 (already in 0.4.1).

### 6.4 What does *not* change

A short list, because boundaries matter:

- **Light mode default.** AGENTS.md mandates it. Dark mode toggle
  stays as the personal-preference affordance.
- **No SPA, no React, no Next.** AGENTS.md mandates it. All "fetch
  on demand" mentioned above is vanilla `fetch` + DOM swap.
- **No new icon set.** Lucide icons continue.
- **No new colour tokens.** All visual changes use existing
  CSS custom properties from
  [`style.css`](../service_crm/static/css/style.css).
- **No removal of the sidebar.** §5.1 below records the rationale.

## 5. Options considered

### 5.1 Sidebar vs. no sidebar (P0-3)

The AGENTS.md rule says "Avoid left sidebars in main technician
screens." The shell ships one. Three options:

| Option | Shape | Pros | Cons |
| --- | --- | --- | --- |
| **A — Keep sidebar; amend AGENTS.md to allow it conditionally** (recommended) | Sidebar stays for all auth pages; collapses to drawer < 900 px; **bottom-fixed action bar** required on technician-primary screens (intervention, ticket detail). | Matches what's shipped; matches OEE Calculator's actual vocabulary (which has a sidebar at desktop widths); minimises 0.4.1 scope; the bottom-action-bar contract is enforceable in CI. | AGENTS.md amendment needs sign-off. |
| B — Remove sidebar; replace with topbar nav | Closer to literal reading of the rule. | Wholesale redesign of the shell; every macro that assumed sidebar width breaks; 6+ list/detail templates relayout. ~1.5 k LOC churn. Conflicts with OEE Calculator vocabulary unless we discover OEE Calculator also has no sidebar (we don't — `oee-calculator2.0` ships one). |
| C — Hide sidebar on a `data-shell="technician"` flag set per route | Surgical. | Adds a per-route flag; managers and front-desk still see it; technicians toggle between two shell modes; cognitive load on the dev side, not the user side. |

**Recommendation: A.** Document the bottom-action-bar contract in
[`docs/ui-reference.md`](./ui-reference.md). Enforce in CI from v0.6
(when the first technician-primary screen ships) via a Playwright
test that walks the intervention create page on a 360 px viewport
and asserts a bottom-fixed action bar is present.

### 5.2 Post-login landing target (P0-1)

| Option | Target | Pros | Cons |
| --- | --- | --- | --- |
| **A — `/clients/` for everyone in 0.4.1; `/tickets/?assigned_to=me` for technicians in 0.5.b; `/dashboard` for everyone in 0.8.0** (recommended) | Phased | Each milestone moves the landing target one step closer to the persona's ideal; no thrash; the 0.4.1 change is one line. | Three changes over three milestones (acceptable; documented). |
| B — `/` always renders a stub dashboard immediately | One target | The stub is dead code by 0.8 and re-engineered then; a stub dashboard with `0`s in every tile is *worse* than `/clients/`. |
| C — Show "where do you want to go?" picker after login | One target | A speed bump on every sign-in; fails the §3.5 single-dial test (every persona pays a tap they don't need). |

**Recommendation: A.**

### 5.3 Stub-nav-link presentation (P0-2)

| Option | Shape | Pros | Cons |
| --- | --- | --- | --- |
| **A — Visibly disabled with `aria-disabled` + tooltip "Coming in v0.X"** (recommended) | Roadmap is visible | Honest with the user; doesn't break sidebar layout; matches OEE Calculator's "future feature" treatment. | Eight tooltips need translation. |
| B — Removed entirely until each milestone ships | Cleaner | The sidebar shrinks and grows over six months — feels jarring; users learn the sidebar shape and we keep changing it. |
| C — Greyed out with no tooltip | Cheaper | Users probe-click; we silently fail Nielsen #1. |

**Recommendation: A.** The eight strings are extracted once; future
milestones flip the disabled flag and remove the tooltip when the
real route lands.

### 5.4 Required-field indicator presentation (P1-4)

| Option | Shape | Pros | Cons |
| --- | --- | --- | --- |
| **A — Asterisk after the label, `aria-label="required"`, CSS `color: var(--accent)`** (recommended) | Visible + a11y | Standard pattern; one CSS rule + one macro change. | Asterisk-as-meaning relies on the legend "required fields are marked with *"; we ship the legend at the top of every form via the form_shell macro. |
| B — "(required)" suffix on every label | Most explicit | Doubles label width on small phones. |
| C — Border colour change only | Cleanest | Fails colour-blindness contrast; fails screen-reader. |

**Recommendation: A** + a translatable legend at the top of every
form-shell ("Fields marked with * are required").

### 5.5 Where the bar's enforcement skill lives

§3.5 names `/ease-pass` as the per-PR skill. It doesn't exist yet.

| Option | Where | Pros | Cons |
| --- | --- | --- | --- |
| **A — New `.claude/skills/ease-pass/SKILL.md`** mirroring `consistency-pass`, mechanical fixes only | Project | Matches the existing pattern; reviewers know how to use it. | Net-new skill (≤ 250 LOC of markdown). |
| B — Fold into `consistency-pass` | Single skill | One review pass per PR. | The check matrix doubles; reviewers lose the "which dial moved?" signal. |
| C — Skip; bar is enforced by reviewer eyeballing | None | Cheapest. | Drifts; was the exact failure mode §3.5 was created to avoid. |

**Recommendation: A.** Out of scope for *this* audit's
implementation, but listed in §6.4 of
[`v0.5-plan.md`](./v0.5-plan.md) "project-level follow-ups". This
audit's 0.4.1 slice writes the skill and uses it on its own PR.

## 7. Files to create vs. adapt (0.4.1 only)

### 7.1 Create

- `service_crm/landing.py` — `/` blueprint, 1 route, ~30 LOC.
  Redirects authenticated users to `/clients/`, anonymous to
  `/auth/login`.
- `service_crm/templates/macros/nav_link.html` — `nav_link(endpoint,
  label, icon, disabled=False, tooltip=None)` macro. ~25 LOC.
- `service_crm/shared/role_labels.py` — `label_for(role) → str`,
  Babel-extractable. ~20 LOC.
- `tests/templates/test_base_shell.py` — sidebar shape, `is-active`
  follows endpoint, disabled-link ARIA.
- `tests/auth/test_login_page.py` — login extends base, touch
  targets, language switch round-trips `?next=`.
- `tests/templates/test_form_shell.py` — required-pip rendering.
- `.claude/skills/ease-pass/SKILL.md` — per-PR ease-of-use review.
- `.claude/skills/ease-pass/CHECKLIST.md` — the 12-cell §3.5 grid
  rendered as a copy-pasteable checklist.

### 7.2 Adapt

- `service_crm/__init__.py` — register the new `landing` blueprint
  (one line).
- `service_crm/auth/routes.py` — replace both
  `url_for("health.version")` with `url_for("clients.list_clients")`;
  the safe-redirect logic stays.
- `service_crm/templates/base.html` — extract sidebar links into the
  new `nav_link` macro; add `data-shell="anon"` on unauthenticated
  pages; move the role label off the hardcoded string; gate the
  notifications + help icons on feature flags; add the
  `{% block topbar_role_links %}{% endblock %}` slot.
- `service_crm/templates/auth/login.html` — rewrite to extend base;
  delete inline `<style>`; delete inline RO/EN.
- `service_crm/templates/macros/form_shell.html` — render the
  `required-pip`.
- `service_crm/templates/macros/data_table.html` — accept
  `empty_action`.
- `service_crm/templates/clients/list.html`,
  `service_crm/templates/equipment/list.html`,
  `service_crm/templates/equipment/detail.html`,
  `service_crm/templates/clients/detail.html` — pass `empty_action`
  to `data_table` invocations.
- `service_crm/static/css/style.css` — `.required-pip`,
  `.nav-link[aria-disabled="true"]`, `.data-table .empty-action`
  rules. Net ~40 LOC.
- `service_crm/config.py` — add `NOTIFICATIONS_ENABLED` (default
  `False`) and `HELP_PORTAL_URL` (default `None`).
- `AGENTS.md` — sidebar amendment (one line, with rationale in
  parens).
- `docs/ui-reference.md` — bottom-action-bar contract added to the
  technician-screens section.
- `service_crm/locale/{ro,en}/LC_MESSAGES/messages.po` +
  `messages.pot` — re-extracted (8 new disabled-nav strings, role
  labels, "required" legend, empty-state action labels).
- `CHANGELOG.md` `## [Unreleased]` — one entry: "Ease-of-use hotfix".
- `tests/e2e/test_touch_targets.py` — walks `/login`.

### 7.3 Out of scope (defer to 0.5.b/c per §6.2)

- Search-as-you-type (P1-1)
- "My queue" topbar link (P1-2 — slot only in 0.4.1; entry in 0.5.b)
- Reason-required destructive modals (P1-5)
- Per-user saved filters (P1-6)
- Inline-edit modal generalisation (P1-7)
- Pagination total counts (P2-4)

### 7.4 Project-level follow-ups (after 0.4.1)

- `ROADMAP.md` — add a "0.4.1 — Ease-of-use hotfix" line under the
  0.4.0 row; reference this doc.
- `docs/testing-cadence.md` §3 ("On every PR") — add `/ease-pass`
  alongside `/consistency-pass`.
- `.claude/skills/README.md` — list `/ease-pass`.
- `.claude/skills/consistency-pass/SKILL.md` — cross-link to
  `/ease-pass`.

## 8. Open questions

These need answers before 0.4.1 opens.

1. **Is the sidebar amendment acceptable?** §5.1 recommends A. The
   AGENTS.md rule is one of the few stated UI rules and was added
   with intent; we should not amend it without a sign-off in this
   PR's review thread.
   *Default if unanswered:* keep the sidebar; ship the amendment as
   proposed.

2. **Post-login target.** §5.2 recommends `/clients/` in 0.4.1. The
   alternative — `/tickets/?assigned_to=me` for technicians — is
   *also* defensible since v0.5 is the next milestone. But there's
   no `/tickets/` until 0.5.b lands, and the role-aware landing
   logic is itself a P1 (P1-2). Hold the landing logic for 0.5.b?
   *Default if unanswered:* `/clients/` in 0.4.1; role-aware in
   0.5.b (one-line change in `auth.login`).

3. **Disabled-link wording.** "Coming in v0.5", "Coming soon",
   "Not available yet"?
   *Default if unanswered:* "Coming in v0.X" with the actual target
   milestone (auto-generated from a per-link `since=` argument to
   the `nav_link` macro). Translatable. Users learn the cadence.

4. **Notifications icon.** Hide entirely or keep with a fixed `0`
   until the real wiring lands in v1.1?
   *Default if unanswered:* hide behind `config.NOTIFICATIONS_ENABLED`
   (default `False`). When the real feature ships in v1.1, flip the
   default.

5. **Help portal URL.** Do we have a help portal URL today, or is
   this purely "configurable for self-hosters"?
   *Default if unanswered:* configurable, default `None` (icon
   hidden). We don't ship a help portal in v1.

6. **Role label translations.** Should `role.technician` translate
   to `Technician` (English) and `Tehnician` (Romanian), or to a
   user-facing variant ("Service technician" / "Tehnician service")?
   *Default if unanswered:* short form. The role's *code* is the
   stable English value (`technician`); the label is the
   translation of that code.

7. **Required-pip glyph.** Asterisk vs. another glyph (e.g., a small
   dot)?
   *Default if unanswered:* asterisk. Widely understood; a11y tools
   handle it well.

8. **Should the audit doc itself live in `docs/` or in
   `.claude/skills/ease-pass/`?**
   *Default if unanswered:* in `docs/` — the audit informs
   architecture; the skill ships *next* and references this doc.

9. **Does AGENTS.md's "Recommended Next Prompt" need updating after
   0.4.1?** The current text refers to the initial walking-skeleton
   prompt; by 0.4.1 it's three months stale.
   *Default if unanswered:* leave it; it's labelled as a starter
   prompt for new agents. AGENTS.md "Major Structural Changes" can
   gain a "2026-05-12 — ease-of-use hotfix" entry.

10. **Lookup admin section.** §6.1 P1-10 adds a "Lookups" sidebar
    section gated to admin role. Today the lookup pages aren't
    role-gated (they're behind `@login_required` only). Add the
    role gate in the same hotfix?
    *Default if unanswered:* yes — add the gate; the UI hint
    without the server-side guard is the worse of the two halves.
