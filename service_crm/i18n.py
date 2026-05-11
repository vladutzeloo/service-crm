"""Locale selection.

Precedence (highest wins):

1. ``flask_login`` current user's ``preferred_language``.
2. ``?lang=`` query string.
3. ``Accept-Language`` request header.
4. Default ``BABEL_DEFAULT_LOCALE`` (``ro`` per the v0.1.0 brief).

Always returns a locale that's in :data:`SUPPORTED_LOCALES`; unknown
values fall through to the next step.
"""

from __future__ import annotations

from flask import current_app, request
from flask_login import current_user

SUPPORTED_LOCALES: tuple[str, ...] = ("ro", "en")
DEFAULT_LOCALE = "ro"


def select_locale() -> str:
    user = current_user if current_user and current_user.is_authenticated else None
    if user is not None:
        pref = getattr(user, "preferred_language", None)
        if pref in SUPPORTED_LOCALES:
            return str(pref)

    query = request.args.get("lang")
    if query in SUPPORTED_LOCALES:
        return query

    best = request.accept_languages.best_match(SUPPORTED_LOCALES)
    if best:
        return str(best)

    return str(current_app.config.get("BABEL_DEFAULT_LOCALE", DEFAULT_LOCALE))
