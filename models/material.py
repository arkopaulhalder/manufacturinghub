"""
Material model — covers US-3 (Machine & Material Catalog Setup).

Fields from SRS acceptance criteria:
  sku (unique), name, unit [KG/LITRE/PIECE], current_stock,
  reorder_level, unit_cost

Constraints from SRS:
  - No duplicate SKUs
  - Positive current_stock, reorder_level, unit_cost (CHECK in migration)
  - Cannot be deleted if referenced in active work orders (service layer)
"""

import enum
from datetime import datetime, timezone

from .base import db


class MaterialUnit(enum.Enum):
    KG = "KG"
    LITRE = "LITRE"
    PIECE = "PIECE"


class Material(db.Model):
    __tablename__ = "materials"

    __table_args__ = (
        db.CheckConstraint("current_stock >= 0", name="ck_material_stock_non_negative"),
        db.CheckConstraint("reorder_level > 0", name="ck_material_reorder_positive"),
        db.CheckConstraint("unit_cost > 0", name="ck_material_unit_cost_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(100), unique=True, nullable=False)        # no duplicates per SRS
    name = db.Column(db.String(255), nullable=False)
    unit = db.Column(db.Enum(MaterialUnit), nullable=False)
    current_stock = db.Column(db.Numeric(12, 3), nullable=False, default=0)   # >= 0, CHECK in migration
    reorder_level = db.Column(db.Numeric(12, 3), nullable=False)              # positive, CHECK in migration
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False)                  # positive, CHECK in migration

    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # --- Relationships ---
    work_order_materials = db.relationship("WorkOrderMaterial", back_populates="material", lazy="dynamic")
    inventory_movements = db.relationship("InventoryMovement", back_populates="material", lazy="dynamic")

    def __repr__(self):
        return f"<Material sku={self.sku} stock={self.current_stock}>"