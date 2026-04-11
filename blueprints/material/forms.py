"""
blueprints/material/forms.py — US-3 Material catalog forms.

SRS acceptance criteria:
  Fields: sku, name, unit [KG/LITRE/PIECE],
          current_stock, reorder_level, unit_cost
  - No duplicate SKU (enforced in service layer)
  - current_stock >= 0
  - reorder_level > 0
  - unit_cost > 0
  - Only MANAGER can submit this form (enforced in route)
"""

from flask_wtf import FlaskForm
from wtforms import DecimalField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange


class MaterialForm(FlaskForm):
    sku = StringField(
        "SKU",
        validators=[DataRequired(), Length(max=100)],
        description="Unique stock-keeping unit e.g. STL-001",
    )
    name = StringField(
        "Material Name",
        validators=[DataRequired(), Length(max=255)],
    )
    unit = SelectField(
        "Unit",
        choices=[
            ("KG", "KG"),
            ("LITRE", "Litre"),
            ("PIECE", "Piece"),
        ],
        validators=[DataRequired()],
    )
    current_stock = DecimalField(
        "Current Stock",
        validators=[
            DataRequired(),
            NumberRange(min=0, message="Stock cannot be negative."),
        ],
        places=3,
        default=0,
    )
    reorder_level = DecimalField(
        "Reorder Level",
        validators=[
            DataRequired(),
            NumberRange(min=0.001, message="Reorder level must be greater than zero."),
        ],
        places=3,
    )
    unit_cost = DecimalField(
        "Unit Cost (₹)",
        validators=[
            DataRequired(),
            NumberRange(min=0.01, message="Unit cost must be greater than zero."),
        ],
        places=2,
    )
    submit = SubmitField("Save Material")