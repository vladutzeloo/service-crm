"""Auth routes: login + logout.

Routes stay thin per the layering rule: parse the request, call into
``services.py``, render or redirect. Audit-log actor + request id are
bound by the blueprint's ``before_app_request`` hook, so we don't need
to set them here.
"""

from __future__ import annotations

from typing import Any

from flask import flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import login_required, login_user, logout_user

from ..extensions import db
from ..shared.audit import ACTOR_CTX
from . import bp, forms, services


@bp.route("/login", methods=["GET", "POST"])
def login() -> Any:
    form = forms.LoginForm()
    if form.validate_on_submit():
        user = services.get_user_by_email(db.session, form.email.data or "")  # type: ignore[arg-type]
        password = form.password.data or ""
        if (
            user is None
            or not user.is_active
            or not services.verify_password(password, user.password_hash)
        ):
            flash(_("Invalid email or password."), "error")
            return render_template("auth/login.html", form=form), 401
        login_user(user)
        # The before_app_request hook ran before authentication, so
        # ACTOR_CTX is still None. Set it now so the upcoming
        # ``record_login`` write is attributed to the user.
        ACTOR_CTX.set(user.id)
        services.record_login(db.session, user)  # type: ignore[arg-type]
        db.session.commit()
        flash(_("Welcome, %(email)s.", email=user.email), "success")
        next_url = request.args.get("next") or url_for("health.version")
        return redirect(next_url)
    return render_template("auth/login.html", form=form)


@bp.route("/logout")
@login_required  # type: ignore[untyped-decorator]
def logout() -> Any:
    logout_user()
    flash(_("You have been signed out."), "info")
    return redirect(url_for("auth.login"))
