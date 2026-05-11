"""Auth blueprint.

Owns ``User`` and ``Role``, plus the login/logout routes and the
Flask-Login ``user_loader``. The blueprint also registers a
``before_app_request`` hook that stashes ``request_id`` and the acting
user's id into the audit context vars (see ``service_crm.shared.audit``).
"""

from __future__ import annotations

import uuid

from flask import Blueprint, g
from flask_login import current_user

from ..extensions import db, login_manager
from ..shared.audit import ACTOR_CTX, REQUEST_ID_CTX

bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth",
    template_folder="../templates/auth",
)

# Importing the models module here registers them with the SQLAlchemy
# metadata at blueprint-registration time, so Alembic autogenerate and
# `db.create_all` both see them.
from . import models, routes  # noqa: E402, F401


@login_manager.user_loader  # type: ignore[untyped-decorator]
def _load_user(user_id_hex: str) -> models.User | None:
    try:
        user_id = bytes.fromhex(user_id_hex)
    except ValueError:
        return None
    user: models.User | None = db.session.get(models.User, user_id)
    return user


@bp.before_app_request
def _wire_audit_context() -> None:
    """Bind the per-request audit context vars.

    Runs on every request (not just /auth), so business writes anywhere
    in the app carry the actor + request id through the audit listener.
    """
    rid = uuid.uuid4().hex[:12]
    g.request_id = rid
    REQUEST_ID_CTX.set(rid)
    if current_user.is_authenticated:
        ACTOR_CTX.set(current_user.id)
    else:
        ACTOR_CTX.set(None)


# Re-export the Flask-Login decorators that views need.
__all__ = ["bp"]
