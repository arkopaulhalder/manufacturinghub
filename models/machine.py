"""
Machine model — covers US-3 (Machine & Material Catalog Setup).

Fields from SRS acceptance criteria:
  machine_id (unique business key), name, type [CNC/LATHE/PRESS],
  capacity_per_hour, status [ACTIVE/MAINTENANCE/OFFLINE]

Constraints from SRS:
  - No duplicate machine_id
  - Positive capacity_per_hour (CHECK constraint)
  - Cannot be deleted if referenced in active work orders (enforced at service layer)
"""

import enum
from datetime import datetime, timezone

from .base import db


class MachineType(enum.Enum):
    CNC = "CNC"
    LATHE = "LATHE"
    PRESS = "PRESS"


class MachineStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    OFFLINE = "OFFLINE"


class Machine(db.Model):
    __tablename__ = "machines"

    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.String(50), unique=True, nullable=False)  # business key, no duplicates
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.Enum(MachineType), nullable=False)
    capacity_per_hour = db.Column(db.Numeric(10, 2), nullable=False)    # positive, CHECK in migration
    status = db.Column(db.Enum(MachineStatus), nullable=False, default=MachineStatus.ACTIVE)

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
    work_orders = db.relationship("WorkOrder", back_populates="machine", lazy="dynamic")
    maintenance_rules = db.relationship("MaintenanceRule", back_populates="machine", lazy="dynamic")
    maintenance_logs = db.relationship("MaintenanceLog", back_populates="machine", lazy="dynamic")

    def __repr__(self):
        return f"<Machine machine_id={self.machine_id} status={self.status.value}>"