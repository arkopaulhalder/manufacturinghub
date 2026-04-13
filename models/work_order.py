"""
WorkOrder and WorkOrderMaterial models — covers US-4 (Work Order Creation)
and US-5 (Production Scheduling).

WorkOrder fields from SRS:
  product_name, quantity, priority [LOW/MEDIUM/HIGH],
  target_completion_date, status [PENDING/SCHEDULED/IN_PROGRESS/COMPLETED]
  planner_id (FK → users), machine_id (FK → machines, nullable until scheduled),
  scheduled_start, scheduled_end (set during scheduling — US-5),
  estimated_hours = CEIL(quantity / machine.capacity_per_hour) — US-5

WorkOrderMaterial (BOM) fields from SRS:
  work_order_id, material_id, required_qty

Constraints from SRS:
  - quantity > 0 (CHECK in migration)
  - required_qty > 0 (CHECK in migration)
  - No overlapping schedules on same machine (enforced at service layer with row-level lock)
  - Cannot schedule on MAINTENANCE/OFFLINE machines (service layer)
  - Inventory NOT consumed until status → IN_PROGRESS (US-6)
"""

import enum
from datetime import datetime, timezone

from .base import db


class WorkOrderPriority(enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class WorkOrderStatus(enum.Enum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class WorkOrder(db.Model):
    __tablename__ = "work_orders"

    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="ck_work_order_quantity_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)

    # --- US-4: Work Order Creation ---
    product_name = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Numeric(12, 3), nullable=False)             # > 0, CHECK in migration
    priority = db.Column(db.Enum(WorkOrderPriority), nullable=False, default=WorkOrderPriority.MEDIUM)
    target_completion_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.Enum(WorkOrderStatus), nullable=False, default=WorkOrderStatus.PENDING)

    # FK to the planner who created this order
    planner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # --- US-5: Production Scheduling ---
    # Nullable until the order is scheduled
    machine_id = db.Column(db.Integer, db.ForeignKey("machines.id"), nullable=True, index=True)
    scheduled_start = db.Column(db.DateTime(timezone=True), nullable=True)
    scheduled_end = db.Column(db.DateTime(timezone=True), nullable=True)
    estimated_hours = db.Column(db.Numeric(8, 2), nullable=True)        # CEIL(qty / capacity_per_hour)

    # Optimistic locking — US-5 concurrency requirement
    version = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # --- Relationships ---
    planner = db.relationship("User", back_populates="work_orders")
    machine = db.relationship("Machine", back_populates="work_orders")
    materials = db.relationship("WorkOrderMaterial", back_populates="work_order",
                                cascade="all, delete-orphan", lazy="joined")
    inventory_movements = db.relationship("InventoryMovement", back_populates="work_order", lazy="dynamic")

    def __repr__(self):
        return f"<WorkOrder id={self.id} product={self.product_name} status={self.status.value}>"


class WorkOrderMaterial(db.Model):
    """Bill of Materials (BOM) — links a work order to its required materials."""

    __tablename__ = "work_order_materials"

    __table_args__ = (
        db.UniqueConstraint("work_order_id", "material_id", name="uq_wo_material"),
        db.CheckConstraint("required_qty > 0", name="ck_wom_required_qty_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(
        db.Integer, db.ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    material_id = db.Column(
        db.Integer, db.ForeignKey("materials.id"), nullable=False, index=True
    )
    required_qty = db.Column(db.Numeric(12, 3), nullable=False)         # > 0, CHECK in migration

    # --- Relationships ---
    work_order = db.relationship("WorkOrder", back_populates="materials")
    material = db.relationship("Material", back_populates="work_order_materials")

    def __repr__(self):
        return f"<WorkOrderMaterial wo_id={self.work_order_id} material_id={self.material_id} qty={self.required_qty}>"