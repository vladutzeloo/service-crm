"""Flask extension instances.

Single source of truth for ``db``, ``migrate``, ``login_manager``,
``csrf`` and ``babel``. The ``init_app`` helper attaches every
extension to the Flask app the factory hands it.
"""

from __future__ import annotations

from flask import Flask
from flask_babel import Babel
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
babel = Babel()


def init_app(app: Flask) -> None:
    from .i18n import select_locale

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    csrf.init_app(app)
    babel.init_app(app, locale_selector=select_locale, default_translation_directories="locale")

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"
