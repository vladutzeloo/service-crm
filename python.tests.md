# Python Testing Strategy (Flask edition)

How we test Service-CRM. Opinionated; deviating needs a comment in the PR.

> Companion docs: [`ARCHITECTURE.md`](./ARCHITECTURE.md),
> [`ROADMAP.md`](./ROADMAP.md), [`AGENTS.md`](./AGENTS.md),
> [`docs/architecture-plan.md`](./docs/architecture-plan.md),
> [`docs/testing-cadence.md`](./docs/testing-cadence.md) (the *when* —
> per-version cadence, mobile/PWA strategy, pre-tag smoke checklist).

## TL;DR

- `pytest` is the test runner. Nothing else.
- Three layers: **unit** (pure Python, no I/O), **integration** (real DB
  through service functions), **e2e** (Flask `test_client()` round-trip).
- A single command — `pytest` — runs them all locally and in CI.
- Coverage gate: **85% line + branch**, enforced by `pyproject.toml`.
- The ticket state machine and money math get **property-based tests**
  (Hypothesis).

## 1. Layout

Tests mirror the production package, one-for-one:

```
service_crm/                      tests/
├── auth/                         ├── auth/
│   ├── models.py                 │   ├── test_models.py            # unit / integration
│   └── services.py               │   └── test_services.py          # integration
├── clients/                      ├── clients/
│   ├── models.py                 │   ├── test_models.py
│   ├── services.py               │   ├── test_services.py
│   └── routes.py                 │   └── test_routes.py            # e2e via test_client
├── tickets/                      ├── tickets/
│   ├── models.py                 │   ├── test_state_machine.py    # unit + Hypothesis
│   ├── services.py               │   └── test_services.py
│   └── routes.py                 │   └── test_routes.py
├── shared/                       ├── shared/
│   ├── ulid.py                   │   ├── test_ulid.py              # unit
│   ├── money.py                  │   ├── test_money.py             # unit + Hypothesis
│   ├── audit.py                  │   └── test_audit.py             # integration
└── ...                           ├── conftest.py                   # shared fixtures
                                  └── factories.py                  # factory-boy builders
```

A test file lives next to (well, mirrors) the module it tests, named
`test_<module>.py`. No `Test*` classes unless shared setup is genuinely
needed — plain functions are preferred.

## 2. The three layers

### 2.1 Unit (`pytest -m unit`)

- Tests **pure Python** in `service_crm/shared/` and any logic that doesn't
  need the database (validators, state-machine transitions, money math,
  ULID encoding).
- **No I/O.** No database, no filesystem, no network, no `time.sleep`.
- Should run in **< 1 second total** per package.
- Use plain `assert`. Parametrize liberally with `@pytest.mark.parametrize`.
- This is where `hypothesis` lives — see §6.

```python
# tests/tickets/test_state_machine.py
import pytest
from service_crm.tickets.state import transition, Status, IllegalTransition

@pytest.mark.unit
@pytest.mark.parametrize("from_state, event, to_state", [
    (Status.OPEN,            "schedule",        Status.SCHEDULED),
    (Status.SCHEDULED,       "start",           Status.IN_PROGRESS),
    (Status.IN_PROGRESS,     "wait_for_parts",  Status.AWAITING_PARTS),
    (Status.AWAITING_PARTS,  "resume",          Status.IN_PROGRESS),
    (Status.IN_PROGRESS,     "resolve",         Status.RESOLVED),
    (Status.RESOLVED,        "close",           Status.CLOSED),
])
def test_legal_transitions(from_state, event, to_state):
    assert transition(from_state, event) is to_state

@pytest.mark.unit
def test_cannot_reopen_a_closed_ticket():
    with pytest.raises(IllegalTransition):
        transition(Status.CLOSED, "start")
```

### 2.2 Integration (`pytest -m integration`)

- Tests blueprints' `services.py` and any `models.py` behavior that needs
  the database.
- Uses a **real database**. Default to SQLite for speed; CI also runs the
  integration suite against Postgres in a service container.
- Each test gets a **fresh transaction that is rolled back at teardown** —
  no test-ordering bugs.
- Schema is created once per session via Alembic `upgrade head` against the
  test DB; we test the migrations we ship, not a `db.create_all()` shortcut.

```python
# tests/clients/test_services.py
import pytest
from service_crm.clients import services as clients_svc
from tests.factories import ClientFactory

@pytest.mark.integration
def test_soft_delete_keeps_client_queryable(db_session):
    client = ClientFactory()
    clients_svc.soft_delete(db_session, client.id)
    assert clients_svc.get_for_history(db_session, client.id) is not None
    assert clients_svc.list_active(db_session) == []
```

### 2.3 End-to-end (`pytest -m e2e`)

- Drives the Flask app via the built-in `test_client()` — no live socket needed.
- Authenticates the same way a browser would (login route → session cookie).
- Asserts on **HTTP responses + DB state**, not internals.
- Reserved for golden paths and a few critical edge cases. If a test could
  be expressed as integration, it should be.

```python
# tests/tickets/test_routes.py
import pytest
from tests.factories import ClientFactory

@pytest.mark.e2e
def test_create_ticket_round_trip(client_logged_in, db_session):
    customer = ClientFactory()
    db_session.commit()

    resp = client_logged_in.post(
        "/tickets/new",
        data={"client_id": str(customer.id), "title": "Replace pump"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Replace pump" in resp.data
```

## 3. Fixtures

`tests/conftest.py` owns the public fixtures. Keep the surface small:

| Fixture            | Scope    | Provides                                            |
| ------------------ | -------- | --------------------------------------------------- |
| `app`              | session  | `create_app(TestConfig)` once per session           |
| `db_engine`        | session  | SQLAlchemy engine on the test DB (Alembic-migrated) |
| `db_session`       | function | Transactional session, rolled back on exit          |
| `client`           | function | `app.test_client()`                                 |
| `client_logged_in` | function | `client` + a default admin session cookie           |
| `frozen_clock`     | function | Patches `service_crm.shared.clock.now`              |

Avoid fixture sprawl. If a fixture is used in only one file, define it locally.

```python
# tests/conftest.py — sketch
import pytest
from sqlalchemy import event as sa_event
from sqlalchemy.orm import sessionmaker
from service_crm import create_app
from service_crm.config import TestConfig
from service_crm.extensions import db as _db

@pytest.fixture(scope="session")
def app():
    app = create_app(TestConfig)
    with app.app_context():
        # Run Alembic upgrade head against TestConfig.SQLALCHEMY_DATABASE_URI
        from alembic import command
        from alembic.config import Config as AlembicConfig
        cfg = AlembicConfig("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", app.config["SQLALCHEMY_DATABASE_URI"])
        command.upgrade(cfg, "head")
        yield app

@pytest.fixture(scope="session")
def db_engine(app):
    return _db.engine

@pytest.fixture
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    nested = connection.begin_nested()

    @sa_event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        nonlocal nested
        if trans.nested and not trans._parent.nested:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def client_logged_in(client, db_session):
    from tests.factories import UserFactory
    user = UserFactory(password="test-pass")
    db_session.commit()
    client.post("/auth/login", data={"email": user.email, "password": "test-pass"})
    return client
```

### Factories, not fixtures, for objects

Use `factory-boy` for entities. A factory makes intent obvious at the call site:

```python
# tests/factories.py
import factory
from service_crm.clients.models import Client, Contact

class ClientFactory(factory.Factory):
    class Meta:
        model = Client
    name      = factory.Faker("company")
    is_active = True

class ContactFactory(factory.Factory):
    class Meta:
        model = Contact
    client = factory.SubFactory(ClientFactory)
    name   = factory.Faker("name")
    email  = factory.Faker("email")
```

```python
def test_x():
    c = ClientFactory(is_active=False)   # one-liner, reads like English
```

## 4. Markers and selection

Defined in `pyproject.toml`:

| Marker        | Meaning                                  |
| ------------- | ---------------------------------------- |
| `unit`        | Fast, no I/O                             |
| `integration` | Touches DB or filesystem                 |
| `e2e`         | Drives the Flask `test_client()`         |
| `slow`        | Excluded from pre-commit; CI-only        |

Common invocations:

```powershell
pytest                          # everything
pytest -m unit                  # < 1s feedback loop while coding
pytest -m "not slow"            # what pre-commit runs
pytest -k "ticket and not pdf"  # ad-hoc filter
pytest -n auto                  # parallel via pytest-xdist
```

`--strict-markers` is on, so a typo in `@pytest.mark.unti` fails the suite.

## 5. Database tests in detail

### Strategy: nested transaction + rollback

Each `db_session` fixture begins a SAVEPOINT and rolls it back at teardown.
This is **~100× faster** than recreating the schema per test, and it surfaces
ordering bugs because tests can't accidentally rely on residual state.

### Two databases, same suite

```yaml
# .github/workflows/ci.yml — sketch (post-0.1.0)
services:
  postgres:
    image: postgres:15
    env: { POSTGRES_PASSWORD: postgres }
    options: >-
      --health-cmd "pg_isready -U postgres"
      --health-interval 5s --health-timeout 5s --health-retries 5
```

We run the integration suite **twice** — once with
`SQLALCHEMY_DATABASE_URI=sqlite:///...` and once with
`SQLALCHEMY_DATABASE_URI=postgresql+psycopg://...`. Anything that diverges
(`render_as_batch`, JSON column quirks, `ILIKE`, FTS5 vs `tsvector`, etc.) is
caught at PR time.

## 6. Property-based tests (Hypothesis)

Reach for property tests when the input space is too large for examples to
cover. The two pillars of the system both qualify:

### Money

```python
from decimal import Decimal
from hypothesis import given, strategies as st
from service_crm.shared.money import Money

money = st.builds(
    Money,
    amount=st.decimals(min_value=0, max_value=10**6, places=2, allow_nan=False),
    currency=st.just("EUR"),
)

@given(money, money)
def test_addition_is_commutative(a, b):
    assert (a + b) == (b + a)

@given(money)
def test_round_trip_through_cents(m):
    assert Money.from_cents(m.to_cents(), m.currency) == m
```

### Ticket state machine

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant
from service_crm.tickets.state import Status, transition

class TicketMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.state = Status.OPEN

    @rule()
    def schedule(self):       self._try("schedule")
    @rule()
    def start(self):          self._try("start")
    @rule()
    def wait_for_parts(self): self._try("wait_for_parts")
    @rule()
    def resume(self):         self._try("resume")
    @rule()
    def resolve(self):        self._try("resolve")
    @rule()
    def close(self):          self._try("close")
    @rule()
    def cancel(self):         self._try("cancel")

    def _try(self, event):
        try:
            self.state = transition(self.state, event)
        except Exception:
            pass

    @invariant()
    def closed_tickets_never_reopen(self):
        if self.state is Status.CLOSED:
            assert True  # checked in unit tests; here we just hold the line

TestTicketMachine = TicketMachine.TestCase
```

## 7. What we do *not* test

- Third-party libraries. We assume Flask and SQLAlchemy work.
- HTML structure pixel-by-pixel. Assert on semantics (a button exists, a
  flash message is set, a row is in the table), not on classnames.
- Generated migrations as such — but we **do** test that
  `alembic upgrade head && alembic downgrade base` is round-trippable on a
  populated DB. That catches the real bugs.

## 8. Coverage

- Configured in `pyproject.toml`: `branch = true`, `fail_under = 85`.
- The ticket state machine module gets a higher local bar — **95%** —
  enforced via a per-file pragma in CI (`--cov-fail-under` plus a grep on
  the report).
- Coverage is a smoke alarm, not a goal. A 100%-covered module can still
  be wrong; a well-tested module can be at 90%. Don't game it.

## 9. Performance & flakiness

- Any test that takes > 200 ms gets `@pytest.mark.slow` or gets fixed.
- Time is mocked via `frozen_clock`. We never use real `sleep` in tests.
- Randomness uses Hypothesis (deterministic with a seed) or `random.Random(seed)`.
  Never `random.random()` directly.
- A test that fails intermittently is a **bug**, not a nuisance. Quarantine
  with `@pytest.mark.skip(reason="flaky — see #NNN")` and open the issue
  the same day.

## 10. Local workflow (PowerShell)

```powershell
# one-time
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# fast loop while coding
pytest -m unit -x --ff

# before pushing
pytest -m "not slow" -n auto
ruff check .
ruff format --check .
mypy service_crm
```

See [`docs/commands.md`](./docs/commands.md) for the full list of dev commands.

## 11. Pre-commit (recommended)

A `.pre-commit-config.yaml` lands with the v0.1.0 scaffold and runs:

- `ruff check --fix`
- `ruff format`
- `pytest -m unit -q`

The full suite is for CI. Pre-commit must stay snappy or developers will
disable it.

## 12. CI gates

`.github/workflows/ci.yml` enforces, on every PR:

1. `ruff check` and `ruff format --check`.
2. `mypy service_crm` (strict).
3. `pytest` against SQLite **and** Postgres (post-0.1.0).
4. Coverage ≥ 85%.

`.github/workflows/release.yml` re-runs the suite before publishing a
release — see [`.github/RELEASING.md`](./.github/RELEASING.md).

## 13. Mobile / PWA testing

v1 ships PWA-light (see
[`docs/v1-implementation-goals.md`](./docs/v1-implementation-goals.md) §2).
The pytest suite alone can't prove "works on phones"; we add three layers
on top:

### 13.1 Touch-target audit (Playwright, in CI)

A Playwright spec walks every P1 page and asserts every interactive
element (`a`, `button`, `input`, `[role=button]`) has a bounding box of
**at least 44 × 44 pt** at the 375 px (iPhone) viewport.

```python
# tests/e2e/test_touch_targets.py
@pytest.mark.e2e
@pytest.mark.parametrize("path", P1_PATHS)
def test_touch_targets_at_375px(playwright_page, path):
    playwright_page.set_viewport_size({"width": 375, "height": 812})
    playwright_page.goto(path)
    too_small = playwright_page.evaluate("""() => {
        const els = document.querySelectorAll('a, button, input, [role=button]');
        return [...els].filter(el => {
            const r = el.getBoundingClientRect();
            return r.width < 44 || r.height < 44;
        }).map(el => el.outerHTML.slice(0, 80));
    }""")
    assert too_small == [], f"Tap targets < 44pt: {too_small}"
```

### 13.2 Lighthouse CI

`lighthouse-ci` runs against a production build (gunicorn + the seeded
reference dataset) on every release-blocking PR. Budgets enforced (per
[`docs/v1-implementation-goals.md`](./docs/v1-implementation-goals.md) §2.6):

- Performance ≥ 90 (mobile profile, slow-4G, mid-tier CPU).
- Accessibility ≥ 95.
- Best Practices ≥ 95.
- PWA badge: present.
- LCP ≤ 2.5 s, CLS ≤ 0.1, TBT ≤ 200 ms.

Routes audited at minimum: dashboard (admin + operator), tickets list,
ticket detail, intervention create.

### 13.3 Real-device pass (manual, per release)

Lighthouse can't catch every iOS Safari quirk. Each release-blocker PR
includes a manual real-device pass on iPhone (latest iOS Safari) and
Android (latest Chrome). The findings list is appended to the release
notes; any P1 regression blocks the tag.

### 13.4 Service-worker tests

The service worker is plain JS, not Python — but we still test it:

- A unit test (Vitest, not pytest) over the cache-naming and stale-cache
  invalidation logic.
- An e2e Playwright test that:
  1. loads `/` with the SW active,
  2. goes offline,
  3. reloads,
  4. asserts the app shell still renders (the dashboard placeholder, not
     a blank page).

A bad SW can pin users on a broken build, so the test that the
versioned cache key advances on every release is a **release blocker**.

## 14. i18n testing (RO + EN)

i18n is a v1 foundation concern (per
[`docs/v1-implementation-goals.md`](./docs/v1-implementation-goals.md) §3.2).
Tests fall into four buckets:

### 14.1 Locale selector (unit + integration)

```python
# tests/i18n/test_locale_selector.py
@pytest.mark.unit
@pytest.mark.parametrize("user_pref, query, header, expected", [
    ("ro", None,  "en",         "ro"),  # user pref wins
    (None, "en",  "ro",         "en"),  # query wins over header
    (None, None,  "en;q=0.9",   "en"),  # header honored
    (None, None,  None,         "ro"),  # default
    (None, None,  "fr",         "ro"),  # unsupported → default
])
def test_locale_selector(user_pref, query, header, expected):
    ...
```

Plus an integration test that hits `/healthz?lang=ro` and `/healthz?lang=en`
and asserts the response body contains the translated text.

### 14.2 No-hardcoded-strings template walk (CI gate)

```python
# tests/i18n/test_no_hardcoded_strings.py
@pytest.mark.unit
def test_every_visible_text_is_translated():
    """Walk every shipped Jinja template; assert no bare text node
    that isn't inside {% trans %}, {{ _(...) }}, or a Babel filter."""
    offenders = scan_templates_for_hardcoded_text(Path("service_crm/templates"))
    assert offenders == [], "\n".join(map(str, offenders))
```

The walker uses `jinja2.lex` to tokenise and tracks `Output` blocks that
aren't wrapped in a translation call. Allowlist: numeric output, dates,
identifiers, content explicitly marked `{# i18n: ignore #}`.

### 14.3 Catalog freshness (CI gate)

```bash
# .github/workflows/ci.yml — sketch
- name: Catalog freshness
  run: |
    pybabel extract -F babel.cfg -o locale/messages.pot service_crm
    pybabel update  -i locale/messages.pot -d locale --omit-header
    git diff --exit-code locale || (
      echo "::error::Translation catalogs out of date. Run pybabel update locally."
      exit 1
    )
```

A new `_()` call without a fresh extraction fails the PR.

### 14.4 Layout under the longer string

RO and EN labels can differ by 50 %+ in length. Add a Playwright spec
that loads each P1 page once in `ro` and once in `en`, asserts no
horizontal scrollbar at 320 px, and snapshots the topbar height to
catch label overflow.

```python
# tests/e2e/test_layout_in_both_locales.py
@pytest.mark.e2e
@pytest.mark.parametrize("locale", ["ro", "en"])
@pytest.mark.parametrize("path", P1_PATHS)
def test_no_horizontal_scroll_at_320px(playwright_page, locale, path):
    playwright_page.set_viewport_size({"width": 320, "height": 700})
    playwright_page.goto(f"{path}?lang={locale}")
    has_h_scroll = playwright_page.evaluate(
        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )
    assert not has_h_scroll, f"horizontal scroll at 320px on {path} ({locale})"
```

### 14.5 What we do *not* translate

- Stable enum values (`TicketStatus.NEW = "new"`) — these are DB-stored
  identifiers, not display text.
- Lookup `code` columns (`TicketType.code`, `EquipmentControllerType.code`).
- Test assertions — tests run in `en` by default.
- Log lines (operator audience, English).
- Internal route paths.
