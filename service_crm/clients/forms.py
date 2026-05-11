"""Flask-WTF forms for the clients blueprint."""

from __future__ import annotations

from flask_babel import lazy_gettext as _
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import BooleanField, DateField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional


class ClientForm(FlaskForm):  # type: ignore[misc]
    name = StringField(_("Name"), validators=[DataRequired(), Length(max=200)])
    email = StringField(_("Email"), validators=[Optional(), Email(), Length(max=200)])
    phone = StringField(_("Phone"), validators=[Optional(), Length(max=50)])
    notes = TextAreaField(_("Notes"), validators=[Optional(), Length(max=4000)])
    submit = SubmitField(_("Save"))


class ContactForm(FlaskForm):  # type: ignore[misc]
    name = StringField(_("Name"), validators=[DataRequired(), Length(max=200)])
    role = StringField(_("Role"), validators=[Optional(), Length(max=80)])
    email = StringField(_("Email"), validators=[Optional(), Email(), Length(max=200)])
    phone = StringField(_("Phone"), validators=[Optional(), Length(max=50)])
    is_primary = BooleanField(_("Primary contact"))
    submit = SubmitField(_("Save"))


class LocationForm(FlaskForm):  # type: ignore[misc]
    label = StringField(_("Label"), validators=[DataRequired(), Length(max=200)])
    address = TextAreaField(_("Address"), validators=[Optional(), Length(max=2000)])
    city = StringField(_("City"), validators=[Optional(), Length(max=100)])
    country = StringField(_("Country"), validators=[Optional(), Length(max=80)])
    submit = SubmitField(_("Save"))


class ContractForm(FlaskForm):  # type: ignore[misc]
    title = StringField(_("Title"), validators=[DataRequired(), Length(max=200)])
    reference = StringField(_("Reference"), validators=[Optional(), Length(max=80)])
    starts_on = DateField(_("Starts on"), validators=[DataRequired()])
    ends_on = DateField(_("Ends on"), validators=[Optional()])
    notes = TextAreaField(_("Notes"), validators=[Optional(), Length(max=4000)])
    submit = SubmitField(_("Save"))


class ImportClientsForm(FlaskForm):  # type: ignore[misc]
    csv_file = FileField(
        _("CSV file"),
        validators=[
            FileRequired(),
            FileAllowed(["csv"], _("CSV files only.")),
        ],
    )
    submit = SubmitField(_("Import"))
