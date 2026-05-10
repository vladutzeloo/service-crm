# Commands

Copy-pasteable from the repo root. PowerShell-flavored per the workspace
preference; bash equivalents are noted where they differ.

> **Note:** Commands assume the v0.1.0 walking skeleton (see
> [`ROADMAP.md`](../ROADMAP.md)) has landed — the importable package is
> `service_crm`, the Flask entry point is the app factory in
> `service_crm/__init__.py`, and Alembic is wired through Flask-Migrate.
> Until then, only `Install`, `Lint / format`, and `Run tests` work.

## Stack

- Flask 3.x.
- Jinja 3.x.
- SQLAlchemy 2.x + Flask-SQLAlchemy.
- Alembic via Flask-Migrate.
- pytest 8.x.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e ".[dev,postgres]"
```

bash:

```bash
python -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -e '.[dev,postgres]'
```

## Run app

Dev server (auto-reload, debug pages):

```powershell
$env:FLASK_APP    = "service_crm"
$env:FLASK_DEBUG  = "1"
$env:DATABASE_URL = "sqlite:///instance/dev.sqlite3"
flask --app service_crm run --port 5000
```

Production-style (single host, single Postgres):

```powershell
$env:FLASK_APP    = "service_crm"
$env:DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/service_crm"
waitress-serve --listen=0.0.0.0:5000 "service_crm:create_app()"
```

bash / Linux container:

```bash
gunicorn "service_crm:create_app()" --bind 0.0.0.0:5000 --workers 4
```

## Run tests

```powershell
pytest                          # everything
pytest -m unit -x --ff          # fast loop while coding
pytest -m "not slow" -n auto    # what pre-commit runs
pytest --cov                    # with coverage report
```

See [`../python.tests.md`](../python.tests.md) for layering and markers.

## Run migrations

Apply the latest schema to whatever DB `DATABASE_URL` points at:

```powershell
flask --app service_crm db upgrade
```

Roll back one step (sanity-check that downgrades work):

```powershell
flask --app service_crm db downgrade -1
```

## Create migration

After editing `service_crm/<bp>/models.py`:

```powershell
flask --app service_crm db migrate -m "add ServiceTicket.due_date"
```

Review the generated file in `migrations/versions/` **before committing** —
autogenerate is a draft, not a final answer. Common edits:

- Add `op.execute(...)` for data backfill.
- Set `render_as_batch=True` in the Alembic env if running on SQLite.
- Add explicit `server_default=` for `NOT NULL` adds on populated tables.

## Lint / format

```powershell
ruff check .                    # lint
ruff format .                   # format in place
ruff format --check .           # CI-style check
mypy service_crm                # type check (strict)
```

`pre-commit` (recommended once installed):

```powershell
pre-commit install              # one-time
pre-commit run --all-files      # ad-hoc
```

## Database utilities

Reset the dev DB (destructive — never run against prod):

```powershell
flask --app service_crm reset-db --yes
```

Seed demo data:

```powershell
flask --app service_crm seed
```

## Docker (post-0.1.0)

```powershell
docker compose up --build
```

The compose file boots Postgres and the app side-by-side; `flask db upgrade`
runs once on container start.

## Maintenance Rules

- Replace placeholders as soon as commands exist.
- Keep commands copy-pasteable from repo root.
- Prefer PowerShell-compatible examples for this workspace.
- Do not document commands that are not actually configured.
