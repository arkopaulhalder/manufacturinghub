"""
blueprints/profile/forms.py

Flask-WTF form for US-2 (User Profile Management).
Validation rules match SRS acceptance criteria:
  - full_name, department, phone, notification_preference
  - Phone: 10-digit format
  - Department: no special characters
"""

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TelField
from wtforms.validators import DataRequired, Length, Optional, Regexp


class ProfileForm(FlaskForm):
    full_name = StringField(
        "Full Name",
        validators=[DataRequired(), Length(max=255)],
    )
    department = StringField(
        "Department",
        validators=[
            Optional(),
            Length(max=100),
            # SRS Don't: no special characters in department names
            Regexp(
                r"^[A-Za-z0-9 ]*$",
                message="Department must not contain special characters.",
            ),
        ],
    )
    phone = TelField(
        "Phone",
        validators=[
            Optional(),
            # SRS: 10-digit format
            Regexp(r"^\d{10}$", message="Phone must be exactly 10 digits."),
        ],
    )
    notification_preference = SelectField(
        "Notification Preference",
        choices=[
            ("EMAIL", "Email"),
            ("SMS", "SMS"),
            ("NONE", "None"),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField("Save Profile")