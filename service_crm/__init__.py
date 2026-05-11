"""Service-CRM application package.

The :func:`create_app` factory is the only entry point for both the
production runtime (``waitress``/``gunicorn``) and the test suite
(``tests/conftest.py``). Every test instantiates its own app — there is
no module-level global Flask instance — which is what lets the SQLAlchemy
fixture run inside a per-test transaction.

See ``docs/architecture-plan.md`` §3.1.
"""

from __future__ import annotations

from flask import Flask

from .config import BaseConfig, ProdConfig
from .extensions import init_app as init_extensions

__all__ = ["create_app"]


def create_app(config: type[BaseConfig] = ProdConfig) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    init_extensions(app)
    _register_blueprints(app)
    _register_cli(app)
    _register_error_handlers(app)
    _register_audit_listeners(app)
    _register_jinja_globals(app)

    app.config["VERSION"] = _read_version_file()
    return app


def _register_jinja_globals(app: Flask) -> None:
    from flask_babel import get_locale

    app.jinja_env.globals["get_locale"] = get_locale


def _register_blueprints(app: Flask) -> None:
    from . import auth, health

    app.register_blueprint(health.bp)
    app.register_blueprint(auth.bp)


def _register_cli(app: Flask) -> None:
    from . import cli

    cli.register(app)


def _register_error_handlers(app: Flask) -> None:
    from . import errors

    errors.register(app)


def _register_audit_listeners(app: Flask) -> None:
    # Importing the module is enough — the @event.listens_for decorators
    # at import time wire the listeners onto the global Session class.
    from .shared import audit  # noqa: F401


def _read_version_file() -> str:
    from pathlib import Path

    version_path = Path(__file__).resolve().parent.parent / "VERSION"
    try:
        return version_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "0.0.0"
