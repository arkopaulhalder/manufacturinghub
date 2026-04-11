"""
blueprints/machine/forms.py — US-3 Machine catalog forms.

SRS acceptance criteria:
  Fields: machine_id, name, type [CNC/LATHE/PRESS],
          capacity_per_hour, status [ACTIVE/MAINTENANCE/OFFLINE]
  - Positive capacity_per_hour
  - No duplicate machine_id (enforced in service layer)
  - Only MANAGER can submit this form (enforced in route)
"""

from flask_wtf import FlaskForm
from wtforms import DecimalField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange


class MachineForm(FlaskForm):
    machine_id = StringField(
        "Machine ID",
        validators=[DataRequired(), Length(max=50)],
        description="Unique identifier e.g. CNC-001",
    )
    name = StringField(
        "Machine Name",
        validators=[DataRequired(), Length(max=255)],
    )
    type = SelectField(
        "Type",
        choices=[("CNC", "CNC"), ("LATHE", "LATHE"), ("PRESS", "PRESS")],
        validators=[DataRequired()],
    )
    capacity_per_hour = DecimalField(
        "Capacity per Hour",
        validators=[
            DataRequired(),
            NumberRange(min=0.01, message="Capacity must be greater than zero."),
        ],
        places=2,
    )
    status = SelectField(
        "Status",
        choices=[
            ("ACTIVE", "Active"),
            ("MAINTENANCE", "Maintenance"),
            ("OFFLINE", "Offline"),
        ],
        validators=[DataRequired()],
        default="ACTIVE",
    )
    submit = SubmitField("Save Machine")