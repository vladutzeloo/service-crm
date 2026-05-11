"""Flask-WTF forms for the auth blueprint."""

from __future__ import annotations

from flask_babel import lazy_gettext as _
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length


class LoginForm(FlaskForm):  # type: ignore[misc]
    email = StringField(
        _("Email"),
        validators=[DataRequired(), Email(), Length(max=200)],
    )
    password = PasswordField(
        _("Password"),
        validators=[DataRequired(), Length(max=200)],
    )
    submit = SubmitField(_("Sign in"))
