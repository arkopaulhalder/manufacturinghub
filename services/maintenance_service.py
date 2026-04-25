"""
services/maintenance_service.py

US-7 — Preventive Maintenance Scheduling business logic.

SRS acceptance criteria covered:
  - Define maintenance rules: machine_id, frequency, interval
  - System calculates next_due_date based on last_maintenance_date and interval
  - Log completed maintenance (date, performed_by, notes); recalculate next_due
  - Machine status auto-changes to MAINTENANCE when due (±2 days grace)
  - Show upcoming maintenance (next 7 days) on manager dashboard
  - Prevent scheduling work orders on machines due for maintenance

SRS Don'ts:
  - Do not allow maintenance intervals < 1 day or < 10 hours
"""

from datetime import datetime, timedelta, timezone

from models.base import db
from models.machine import Machine, MachineStatus
from models.maintenance import MaintenanceFrequency, MaintenanceLog, MaintenanceRule


GRACE_DAYS = 2


# ------------------------------------------------------------------ #
# Read — Rules                                                        #
# ------------------------------------------------------------------ #

def get_all_rules() -> list[MaintenanceRule]:
    """Return all maintenance rules, ordered by next_due_date."""
    return (
        MaintenanceRule.query
        .order_by(
            MaintenanceRule.next_due_date.is_(None),
            MaintenanceRule.next_due_date.asc(),
        )
        .all()
    )


def get_rules_for_machine(machine_pk: int) -> list[MaintenanceRule]:
    """Return all rules for a specific machine."""
    return (
        MaintenanceRule.query
        .filter_by(machine_id=machine_pk)
        .order_by(
            MaintenanceRule.next_due_date.is_(None),
            MaintenanceRule.next_due_date.asc(),
        )
        .all()
    )


def get_rule_by_id(rule_pk: int) -> MaintenanceRule | None:
    return db.session.get(MaintenanceRule, rule_pk)


def get_upcoming_maintenance(days: int = 7) -> list[MaintenanceRule]:
    """
    Return rules where next_due_date is within the specified days
    (or already overdue). Used for dashboard display.
    """
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=days)
    return (
        MaintenanceRule.query
        .filter(
            MaintenanceRule.next_due_date.isnot(None),
            MaintenanceRule.next_due_date <= horizon,
        )
        .order_by(MaintenanceRule.next_due_date.asc())
        .all()
    )


def is_machine_due_for_maintenance(machine_pk: int) -> bool:
    """
    Check if a machine has any rule where next_due_date is within
    ±GRACE_DAYS of today. Used to block scheduling.
    """
    now = datetime.now(timezone.utc)
    grace_start = now - timedelta(days=GRACE_DAYS)
    grace_end = now + timedelta(days=GRACE_DAYS)

    count = (
        MaintenanceRule.query
        .filter(
            MaintenanceRule.machine_id == machine_pk,
            MaintenanceRule.next_due_date.isnot(None),
            MaintenanceRule.next_due_date >= grace_start,
            MaintenanceRule.next_due_date <= grace_end,
        )
        .count()
    )
    return count > 0


# ------------------------------------------------------------------ #
# Create Rule                                                         #
# ------------------------------------------------------------------ #

def calculate_next_due_date(
    last_date: datetime | None,
    frequency: MaintenanceFrequency,
    interval_value: int,
) -> datetime:
    """
    Calculate next_due_date based on last_maintenance_date and interval.
    If last_date is None, use current time as starting point.
    """
    base = last_date or datetime.now(timezone.utc)

    if frequency == MaintenanceFrequency.DATE_BASED:
        return base + timedelta(days=interval_value)
    else:
        return base + timedelta(hours=interval_value)


def create_rule(
    machine_pk: int,
    frequency_str: str,
    interval_value: int,
    last_maintenance_date: datetime | None = None,
) -> tuple[bool, str, MaintenanceRule | None]:
    """
    Create a new maintenance rule for a machine.
    Returns (success, message, rule_or_None).

    SRS Don'ts:
      - DATE_BASED: interval_value >= 1 day
      - HOURS_BASED: interval_value >= 10 hours
    """
    machine = db.session.get(Machine, machine_pk)
    if not machine:
        return False, "Machine not found.", None

    try:
        frequency = MaintenanceFrequency[frequency_str.upper()]
    except KeyError:
        return False, "Invalid frequency. Choose HOURS_BASED or DATE_BASED.", None

    try:
        interval = int(interval_value)
    except (TypeError, ValueError):
        return False, "Interval must be an integer.", None

    if frequency == MaintenanceFrequency.DATE_BASED and interval < 1:
        return False, "For date-based maintenance, interval must be at least 1 day.", None
    if frequency == MaintenanceFrequency.HOURS_BASED and interval < 10:
        return False, "For hours-based maintenance, interval must be at least 10 hours.", None

    next_due = calculate_next_due_date(last_maintenance_date, frequency, interval)

    rule = MaintenanceRule(
        machine_id=machine_pk,
        frequency=frequency,
        interval_value=interval,
        last_maintenance_date=last_maintenance_date,
        next_due_date=next_due,
    )
    db.session.add(rule)
    db.session.commit()

    unit = "days" if frequency == MaintenanceFrequency.DATE_BASED else "hours"
    return True, (
        f"Maintenance rule created for {machine.machine_id}: "
        f"every {interval} {unit}. Next due: {next_due.strftime('%d %b %Y')}."
    ), rule


# ------------------------------------------------------------------ #
# Update Rule                                                         #
# ------------------------------------------------------------------ #

def update_rule(
    rule_pk: int,
    frequency_str: str,
    interval_value: int,
    last_maintenance_date: datetime | None = None,
) -> tuple[bool, str]:
    """Update an existing maintenance rule."""
    rule = db.session.get(MaintenanceRule, rule_pk)
    if not rule:
        return False, "Maintenance rule not found."

    try:
        frequency = MaintenanceFrequency[frequency_str.upper()]
    except KeyError:
        return False, "Invalid frequency."

    try:
        interval = int(interval_value)
    except (TypeError, ValueError):
        return False, "Interval must be an integer."

    if frequency == MaintenanceFrequency.DATE_BASED and interval < 1:
        return False, "For date-based maintenance, interval must be at least 1 day."
    if frequency == MaintenanceFrequency.HOURS_BASED and interval < 10:
        return False, "For hours-based maintenance, interval must be at least 10 hours."

    rule.frequency = frequency
    rule.interval_value = interval
    rule.last_maintenance_date = last_maintenance_date
    rule.next_due_date = calculate_next_due_date(last_maintenance_date, frequency, interval)

    db.session.commit()
    return True, "Maintenance rule updated successfully."


# ------------------------------------------------------------------ #
# Delete Rule                                                         #
# ------------------------------------------------------------------ #

def delete_rule(rule_pk: int) -> tuple[bool, str]:
    """Delete a maintenance rule."""
    rule = db.session.get(MaintenanceRule, rule_pk)
    if not rule:
        return False, "Maintenance rule not found."

    db.session.delete(rule)
    db.session.commit()
    return True, "Maintenance rule deleted."


# ------------------------------------------------------------------ #
# Log Maintenance                                                     #
# ------------------------------------------------------------------ #

def get_logs_for_machine(machine_pk: int, limit: int = 50) -> list[MaintenanceLog]:
    """Return maintenance logs for a machine, newest first."""
    return (
        MaintenanceLog.query
        .filter_by(machine_id=machine_pk)
        .order_by(MaintenanceLog.date.desc())
        .limit(limit)
        .all()
    )


def get_logs_for_rule(rule_pk: int, limit: int = 50) -> list[MaintenanceLog]:
    """Return maintenance logs linked to a specific rule."""
    return (
        MaintenanceLog.query
        .filter_by(rule_id=rule_pk)
        .order_by(MaintenanceLog.date.desc())
        .limit(limit)
        .all()
    )


def log_maintenance(
    rule_pk: int,
    date: datetime,
    performed_by: str,
    notes: str | None = None,
    user_id: int | None = None,
    ip_address: str | None = None,
) -> tuple[bool, str, MaintenanceLog | None]:
    """
    Record a completed maintenance event and recalculate next_due_date.
    Returns (success, message, log_or_None).

    After logging:
      - Updates rule.last_maintenance_date to the log date
      - Recalculates rule.next_due_date
      - If machine was in MAINTENANCE status, sets it back to ACTIVE
    """
    rule = db.session.get(MaintenanceRule, rule_pk)
    if not rule:
        return False, "Maintenance rule not found.", None

    performed_by = performed_by.strip()
    if not performed_by:
        return False, "Performed by is required.", None

    log = MaintenanceLog(
        machine_id=rule.machine_id,
        rule_id=rule_pk,
        date=date,
        performed_by=performed_by,
        notes=notes.strip() if notes else None,
    )
    db.session.add(log)

    rule.last_maintenance_date = date
    rule.next_due_date = calculate_next_due_date(
        date, rule.frequency, rule.interval_value
    )

    if rule.machine.status == MachineStatus.MAINTENANCE:
        rule.machine.status = MachineStatus.ACTIVE

    # US-10: Audit log for maintenance
    from services.audit_service import log_audit
    from models.audit import AuditAction
    log_audit(
        action=AuditAction.MAINTENANCE_LOG,
        user_id=user_id,
        ip_address=ip_address,
        entity_type="Machine",
        entity_id=rule.machine_id,
        new_values={
            "machine_id": rule.machine.machine_id,
            "performed_by": performed_by,
            "date": date.isoformat(),
            "next_due_date": rule.next_due_date.isoformat(),
            "notes": notes.strip() if notes else None,
        },
    )

    db.session.commit()

    return True, (
        f"Maintenance logged for {rule.machine.machine_id}. "
        f"Next due: {rule.next_due_date.strftime('%d %b %Y')}."
    ), log


# ------------------------------------------------------------------ #
# Auto-set machine to MAINTENANCE when due                            #
# ------------------------------------------------------------------ #

def update_machines_due_for_maintenance() -> int:
    """
    Check all rules and set machine status to MAINTENANCE if
    next_due_date is within ±GRACE_DAYS of today.

    Returns count of machines updated.

    This would typically be called by a scheduled job/cron.
    """
    now = datetime.now(timezone.utc)
    grace_start = now - timedelta(days=GRACE_DAYS)
    grace_end = now + timedelta(days=GRACE_DAYS)

    due_rules = (
        MaintenanceRule.query
        .filter(
            MaintenanceRule.next_due_date.isnot(None),
            MaintenanceRule.next_due_date >= grace_start,
            MaintenanceRule.next_due_date <= grace_end,
        )
        .all()
    )

    updated_machines = set()
    for rule in due_rules:
        if rule.machine.status == MachineStatus.ACTIVE:
            rule.machine.status = MachineStatus.MAINTENANCE
            updated_machines.add(rule.machine_id)

    if updated_machines:
        db.session.commit()

    return len(updated_machines)
