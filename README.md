# service-crm

Standalone, self-hostable CRM for service-oriented small businesses —
repair shops, IT/MSP, HVAC, appliance repair, mobile field techs.

> **Status: planning.** No application code has shipped yet. The docs below
> describe what we're building and how. First runnable version is `0.1.0`
> on the [roadmap](./ROADMAP.md).

## Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md) — domain model, stack, layout, ADR process.
- [ROADMAP.md](./ROADMAP.md) — versioned milestones, `0.1.0 → 1.0.0` and beyond.
- [python.tests.md](./python.tests.md) — testing strategy: layers, fixtures, coverage gate.
- [CHANGELOG.md](./CHANGELOG.md) — Keep-a-Changelog log of every release.
- [.github/RELEASING.md](./.github/RELEASING.md) — how to cut a release.

## Stack at a glance

Python 3.11+ · FastAPI · SQLAlchemy + Alembic · PostgreSQL (SQLite for dev) ·
Jinja2 + HTMX · Argon2 sessions · Docker · pytest. See
[ARCHITECTURE.md §4](./ARCHITECTURE.md#4-architecture) for the rationale.

## Releases

Tagging `vX.Y.Z` triggers `.github/workflows/release.yml`, which validates
that `VERSION` and `CHANGELOG.md` agree with the tag, runs the suite, builds
the artifacts, and publishes a GitHub Release. Pre-1.0 tags are marked as
pre-releases automatically.

## License

MIT (see `pyproject.toml`).
