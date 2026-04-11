"""
blueprints/work_order/forms.py — US-4 Work Order Creation forms.

SRS acceptance criteria:
  Fields: product_name, quantity, priority [LOW/MEDIUM/HIGH],
          target_completion_date, required_materials (BOM)
  - quantity > 0
  - target_completion_date is optional
  - BOM lines are handled dynamically via JS and parsed
    manually in the route — not part of this WTForm class
  - Do not allow zero or negative quantities
  - Only PLANNER can submit this form (enforced in route)
"""

from flask_wtf import FlaskForm
from wtforms import DateField, DecimalField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class WorkOrderForm(FlaskForm):
    product_name = StringField(
        "Product Name",
        validators=[DataRequired(), Length(max=255)],
    )
    quantity = DecimalField(
        "Quantity",
        validators=[
            DataRequired(),
            NumberRange(
                min=0.001,
                message="Quantity must be greater than zero.",
            ),
        ],
        places=3,
    )
    priority = SelectField(
        "Priority",
        choices=[
            ("LOW",    "Low"),
            ("MEDIUM", "Medium"),
            ("HIGH",   "High"),
        ],
        validators=[DataRequired()],
        default="MEDIUM",
    )
    target_completion_date = DateField(
        "Target Completion Date",
        validators=[Optional()],
        format="%Y-%m-%d",
    )
    submit = SubmitField("Save Work Order")