# Python Testing Strategy

How we test Service CRM. This is opinionated; deviating needs a comment in
the PR explaining why.

> Companion docs: [ARCHITECTURE.md](./ARCHITECTURE.md), [ROADMAP.md](./ROADMAP.md).

## TL;DR

- `pytest` is the test runner. Nothing else.
- Three layers: **unit** (fast, pure), **integration** (real DB), **e2e** (HTTP through FastAPI).
- A single command — `pytest` — runs them all locally and in CI.
- Coverage gate: **85% line + branch**, enforced by `pyproject.toml`.
- The state machine and money math get **property-based tests** (Hypothesis).

## 1. Layout

Tests mirror the production package, one-for-one:

```
service_crm/                tests/
├── domain/                 ├── domain/                # unit
│   ├── work_order.py       │   └── test_work_order.py
│   └── money.py            │   └── test_money.py
├── services/               ├── services/              # integration
│   └── invoicing.py        │   └── test_invoicing.py
├── api/                    ├── api/                   # e2e
│   └── work_orders.py      │   └── test_work_orders_api.py
└── ...                     ├── conftest.py            # shared fixtures
                            └── factories.py           # factory-boy builders
```

A test file lives next to the module it tests, named `test_<module>.py`. No
`Test*` classes unless you actually need shared setup — plain functions are
preferred.

## 2. The three layers

### 2.1 Unit (`pytest -m unit`)

- Tests **pure Python** in `service_crm/domain/` and small helpers.
- **No I/O.** No database, no filesystem, no network, no `time.sleep`.
- Should run in **< 1 second total** per package.
- Use plain `assert`. Parametrize liberally with `@pytest.mark.parametrize`.
- This is where `hypothesis` lives — see §6.

```python
# tests/domain/test_work_order.py
import pytest
from service_crm.domain.work_order import WorkOrder, State, IllegalTransition

@pytest.mark.unit
@pytest.mark.parametrize("from_state, event, to_state", [
    (State.DRAFT,         "schedule",  State.SCHEDULED),
    (State.SCHEDULED,     "start",     State.IN_PROGRESS),
    (State.IN_PROGRESS,   "complete",  State.COMPLETED),
])
def test_legal_transitions(from_state, event, to_state):
    wo = WorkOrder(state=from_state)
    wo.handle(event)
    assert wo.state is to_state

@pytest.mark.unit
def test_cannot_invoice_a_cancelled_order():
    wo = WorkOrder(state=State.CANCELLED)
    with pytest.raises(IllegalTransition):
        wo.handle("invoice")
```

### 2.2 Integration (`pytest -m integration`)

- Tests `service_crm/services/` and `service_crm/db/`.
- Use a **real database**. Default to SQLite for speed; CI also runs the
  integration suite against Postgres in a service container.
- Each test gets a **fresh transaction that is rolled back at teardown** —
  no test-ordering bugs.
- Schema is created once per session via Alembic `upgrade head` against the
  test DB; we test the migrations we ship, not a `Base.metadata.create_all`
  shortcut.

```python
# tests/services/test_invoicing.py
import pytest
from service_crm.services.invoicing import issue_invoice
from tests.factories import WorkOrderFactory

@pytest.mark.integration
def test_issue_invoice_is_idempotent(db_session):
    wo = WorkOrderFactory(state="completed")
    inv1 = issue_invoice(db_session, wo.id)
    inv2 = issue_invoice(db_session, wo.id)
    assert inv1.id == inv2.id
    assert inv1.is_immutable
```

### 2.3 End-to-end (`pytest -m e2e`)

- Drives the FastAPI app via `httpx.AsyncClient` against the ASGI transport
  — no live socket needed.
- Authenticates the same way a browser would (login endpoint → session cookie).
- Asserts on **HTTP responses + DB state**, not internals.
- Reserved for golden paths and a few critical edge cases. If a test could
  be expressed as integration, it should be.

```python
# tests/api/test_work_orders_api.py
import pytest

@pytest.mark.e2e
async def test_create_work_order_round_trip(client_logged_in, customer):
    resp = await client_logged_in.post(
        "/api/work-orders",
        json={"customer_id": customer.id, "summary": "Replace screen"},
    )
    assert resp.status_code == 201
    wo_id = resp.json()["id"]
    assert (await client_logged_in.get(f"/api/work-orders/{wo_id}")).status_code == 200
```

## 3. Fixtures

`tests/conftest.py` owns the public fixtures. Keep the surface small:

| Fixture            | Scope    | Provides                                    |
| ------------------ | -------- | ------------------------------------------- |
| `db_engine`        | session  | SQLAlchemy engine on the test DB            |
| `db_session`       | function | Transactional session, rolled back on exit  |
| `app`              | session  | FastAPI app with overrides applied          |
| `client`           | function | `httpx.AsyncClient` bound to the app        |
| `client_logged_in` | function | `client` plus a default admin session       |
| `frozen_clock`     | function | Patches `app.clock.now` to a fixed instant  |

Avoid fixture sprawl. If a fixture is used in only one file, define it locally.

### Factories, not fixtures, for objects

Use `factory-boy` for entities. A factory makes intent obvious at the call site:

```python
# tests/factories.py
import factory
from service_crm.db.models import Customer, WorkOrder

class CustomerFactory(factory.Factory):
    class Meta:
        model = Customer
    name = factory.Faker("company")

class WorkOrderFactory(factory.Factory):
    class Meta:
        model = WorkOrder
    customer = factory.SubFactory(CustomerFactory)
    summary = "Diagnose"
    state = "draft"
```

```python
def test_x():
    wo = WorkOrderFactory(state="completed")          # one-liner, reads like English
```

## 4. Markers and selection

Defined in `pyproject.toml`:

| Marker        | Meaning                                  |
| ------------- | ---------------------------------------- |
| `unit`        | Fast, no I/O                             |
| `integration` | Touches DB or filesystem                 |
| `e2e`         | Drives the HTTP layer end-to-end         |
| `slow`        | Excluded from pre-commit; CI-only        |

Common invocations:

```bash
pytest                          # everything
pytest -m unit                  # < 1s feedback loop while coding
pytest -m "not slow"            # what pre-commit runs
pytest -k "invoice and not pdf" # ad-hoc filter
pytest -n auto                  # parallel via pytest-xdist
```

`--strict-markers` is on, so a typo in `@pytest.mark.unti` fails the suite.

## 5. Database tests in detail

### Strategy: nested transaction + rollback

Each `db_session` fixture begins a SAVEPOINT and rolls it back at teardown.
This is **~100× faster** than recreating the schema per test, and it surfaces
ordering bugs because tests can't accidentally rely on residual state.

```python
# tests/conftest.py (sketch)
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
```

### Two databases, same suite

```yaml
# .github/workflows/ci.yml — sketch
services:
  postgres:
    image: postgres:15
    env: { POSTGRES_PASSWORD: postgres }
    options: >-
      --health-cmd "pg_isready -U postgres"
      --health-interval 5s --health-timeout 5s --health-retries 5
```

We run the integration suite **twice** — once with `DATABASE_URL=sqlite:///...`
and once with `DATABASE_URL=postgresql://...`. Anything that diverges
(`render_as_batch`, JSON column quirks, `ILIKE`, etc.) is caught at PR time.

## 6. Property-based tests (Hypothesis)

Reach for property tests when the input space is too large for examples to
cover. The two pillars of the system both qualify:

### Money

```python
from decimal import Decimal
from hypothesis import given, strategies as st
from service_crm.domain.money import Money

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

### State machine

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant
from service_crm.domain.work_order import WorkOrder, State

class WorkOrderMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.wo = WorkOrder()

    @rule()
    def schedule(self):  self.wo.try_handle("schedule")
    @rule()
    def start(self):     self.wo.try_handle("start")
    @rule()
    def complete(self):  self.wo.try_handle("complete")
    @rule()
    def cancel(self):    self.wo.try_handle("cancel")

    @invariant()
    def closed_orders_never_reopen(self):
        if self.wo.state is State.CLOSED:
            assert self.wo.history[-1].to is State.CLOSED

TestWorkOrderMachine = WorkOrderMachine.TestCase
```

## 7. What we do *not* test

- Third-party libraries. We assume SQLAlchemy works.
- HTML structure pixel-by-pixel. Assert on semantics (a button exists, a
  flash message is set), not on classnames.
- Generated migrations as such — but we **do** test that
  `alembic upgrade head && alembic downgrade base` is round-trippable on a
  populated DB. That catches the real bugs.

## 8. Coverage

- Configured in `pyproject.toml`: `branch = true`, `fail_under = 85`.
- The state machine module gets a higher local bar — **95%** — enforced via
  a per-file pragma in CI (`--cov-fail-under` plus a grep on the report).
- Coverage is a smoke alarm, not a goal. A 100%-covered module can still be
  wrong; a well-tested module can be at 90%. Don't game it.

## 9. Performance & flakiness

- Any test that takes > 200 ms gets `@pytest.mark.slow` or gets fixed.
- Time is mocked via `frozen_clock`. We never use real `sleep` in tests.
- Randomness uses Hypothesis (deterministic with a seed) or `random.Random(seed)`.
  Never `random.random()` directly.
- A test that fails intermittently is a **bug**, not a nuisance. Quarantine
  with `@pytest.mark.skip(reason="flaky — see #NNN")` and open the issue
  the same day.

## 10. Local workflow

```bash
# one-time
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# fast loop while coding
pytest -m unit -x --ff

# before pushing
pytest -m "not slow" -n auto
ruff check . && mypy service_crm
```

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
3. `pytest` against SQLite **and** Postgres.
4. Coverage ≥ 85%.

`.github/workflows/release.yml` re-runs the suite before publishing a
release — see [.github/RELEASING.md](./.github/RELEASING.md).
