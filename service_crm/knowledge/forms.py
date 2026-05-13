"""Flask-WTF forms for the knowledge blueprint."""

from __future__ import annotations

from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional


class TemplateCreateForm(FlaskForm):  # type: ignore[misc]
    name = StringField(_l("Name"), validators=[DataRequired(), Length(max=200)])
    description = TextAreaField(_l("Description"), validators=[Optional(), Length(max=8000)])
    submit = SubmitField(_l("Save"))


class TemplateEditForm(TemplateCreateForm):
    is_active = BooleanField(_l("Active"), default=True)


class TemplateItemForm(FlaskForm):  # type: ignore[misc]
    key = StringField(_l("Key"), validators=[DataRequired(), Length(max=80)])
    label = StringField(_l("Label"), validators=[DataRequired(), Length(max=200)])
    kind = SelectField(
        _l("Kind"),
        choices=[
            ("bool", _l("Yes / no")),
            ("text", _l("Text")),
            ("number", _l("Number")),
            ("choice", _l("Choice")),
        ],
        validators=[DataRequired()],
    )
    is_required = BooleanField(_l("Required"), default=True)
    choice_options = StringField(
        _l("Choice options (comma-separated)"),
        validators=[Optional(), Length(max=400)],
    )
    submit = SubmitField(_l("Add item"))


class TagCreateForm(FlaskForm):  # type: ignore[misc]
    code = StringField(_l("Code"), validators=[DataRequired(), Length(max=40)])
    name = StringField(_l("Name"), validators=[DataRequired(), Length(max=120)])
    submit = SubmitField(_l("Save"))


class TagEditForm(FlaskForm):  # type: ignore[misc]
    name = StringField(_l("Name"), validators=[DataRequired(), Length(max=120)])
    is_active = BooleanField(_l("Active"), default=True)
    submit = SubmitField(_l("Save"))


class ProcedureCreateForm(FlaskForm):  # type: ignore[misc]
    title = StringField(_l("Title"), validators=[DataRequired(), Length(max=200)])
    summary = StringField(_l("Summary"), validators=[Optional(), Length(max=400)])
    body = TextAreaField(_l("Body (Markdown)"), validators=[Optional(), Length(max=65536)])
    tags = SelectMultipleField(
        _l("Tags"), choices=[], validate_choice=False, validators=[Optional()]
    )
    submit = SubmitField(_l("Save"))


class ProcedureEditForm(ProcedureCreateForm):
    is_active = BooleanField(_l("Active"), default=True)
