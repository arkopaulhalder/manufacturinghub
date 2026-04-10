"""
MaintenanceRule and MaintenanceLog models — covers US-7 (Preventive Maintenance Scheduling).

MaintenanceRule fields from SRS:
  machine_id, frequency [HOURS_BASED/DATE_BASED],
  interval_value (e.g. 500 hours or 30 days),
  last_maintenance_date, next_due_date (computed from last + interval)

Constraints from SRS:
  - interval_value >= 10 (hours) or >= 1 (days) — CHECK in migration
  - Machine status auto-changes to MAINTENANCE when within ±2 days of next_due_date (scheduler)
  - Cannot schedule work orders on machines due for maintenance (service layer)

MaintenanceLog fields from SRS:
  machine_id, date, performed_by, notes
  After logging, next_due_date is recalculated.
"""

import enum
from datetime import datetime, timezone

from .base import db


class MaintenanceFrequency(enum.Enum):
    HOURS_BASED = "HOURS_BASED"
    DATE_BASED = "DATE_BASED"


class MaintenanceRule(db.Model):
    __tablename__ = "maintenance_rules"

    id = db.Column(db.Integer, primary_key=True)

    machine_id = db.Column(
        db.Integer, db.ForeignKey("machines.id"), nullable=False, index=True
    )
    frequency = db.Column(db.Enum(MaintenanceFrequency), nullable=False)
    # For DATE_BASED: days; for HOURS_BASED: hours. CHECK constraint in migration:
    #   DATE_BASED  → interval_value >= 1
    #   HOURS_BASED → interval_value >= 10
    interval_value = db.Column(db.Integer, nullable=False)

    last_maintenance_date = db.Column(db.DateTime(timezone=True), nullable=True)
    next_due_date = db.Column(db.DateTime(timezone=True), nullable=True, index=True)

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
    machine = db.relationship("Machine", back_populates="maintenance_rules")
    logs = db.relationship("MaintenanceLog", back_populates="rule", lazy="dynamic")

    def __repr__(self):
        return f"<MaintenanceRule id={self.id} machine_id={self.machine_id} next_due={self.next_due_date}>"


class MaintenanceLog(db.Model):
    """Records a completed maintenance event (date, performed_by, notes)."""

    __tablename__ = "maintenance_logs"

    id = db.Column(db.Integer, primary_key=True)

    machine_id = db.Column(
        db.Integer, db.ForeignKey("machines.id"), nullable=False, index=True
    )
    # Link back to the rule so next_due can be recalculated after logging
    rule_id = db.Column(
        db.Integer, db.ForeignKey("maintenance_rules.id"), nullable=True
    )

    date = db.Column(db.DateTime(timezone=True), nullable=False)
    performed_by = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # --- Relationships ---
    machine = db.relationship("Machine", back_populates="maintenance_logs")
    rule = db.relationship("MaintenanceRule", back_populates="logs")

    def __repr__(self):
        return f"<MaintenanceLog id={self.id} machine_id={self.machine_id} date={self.date}>"