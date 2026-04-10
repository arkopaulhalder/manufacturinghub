"""
InventoryMovement model — covers US-6 (Inventory Consumption & Restocking).

Fields from SRS acceptance criteria:
  Consume  → type=OUT,    order_id, qty, timestamp
  Restock  → type=IN,     supplier, qty, timestamp
  Adjust   → type=ADJUST, reason, qty_delta

Constraints from SRS:
  - No negative stock values (enforced at service layer before insert)
  - Consumption requires an associated work order (work_order_id NOT NULL for OUT movements)
  - Trigger alert if current_stock < reorder_level after any movement (service layer)
"""

import enum
from datetime import datetime, timezone

from .base import db


class MovementType(enum.Enum):
    IN = "IN"           # restock
    OUT = "OUT"         # consumption when work order → IN_PROGRESS
    ADJUST = "ADJUST"   # manual correction by manager


class InventoryMovement(db.Model):
    __tablename__ = "inventory_movements"

    id = db.Column(db.Integer, primary_key=True)

    material_id = db.Column(
        db.Integer, db.ForeignKey("materials.id"), nullable=False, index=True
    )
    type = db.Column(db.Enum(MovementType), nullable=False)
    qty = db.Column(db.Numeric(12, 3), nullable=False)                  # absolute quantity (always positive)

    # --- OUT movements: must have a work order ---
    work_order_id = db.Column(
        db.Integer, db.ForeignKey("work_orders.id"), nullable=True, index=True
    )

    # --- IN movements: supplier name ---
    supplier = db.Column(db.String(255), nullable=True)

    # --- ADJUST movements: reason and signed delta ---
    reason = db.Column(db.String(500), nullable=True)
    qty_delta = db.Column(db.Numeric(12, 3), nullable=True)             # signed: positive=add, negative=remove

    timestamp = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )

    # --- Relationships ---
    material = db.relationship("Material", back_populates="inventory_movements")
    work_order = db.relationship("WorkOrder", back_populates="inventory_movements")

    def __repr__(self):
        return f"<InventoryMovement id={self.id} type={self.type.value} material_id={self.material_id} qty={self.qty}>"