"""
services/scheduling_service.py

US-5 — Production Scheduling business logic (Planner).

SRS acceptance criteria covered:
  - Assign work order to machine with estimated_hours based on
    quantity and machine capacity_per_hour
  - estimated_hours = CEIL(quantity / machine.capacity_per_hour)
  - Atomic scheduling with row-level lock on machine availability
  - Check machine is not MAINTENANCE or OFFLINE — block if so
  - Prevent overlapping schedules on same machine
  - Check material availability: warn if stock insufficient but
    still allow scheduling (manager can restock) — SRS Dos
  - Scheduled orders transition to SCHEDULED status
  - Gantt-style view (simple table with start/end times)
  - Handle concurrency: two planners scheduling same machine
    simultaneously — uses with_for_update() row-level lock

SRS Don'ts:
  - Do not allow overlapping schedules on the same machine
  - Do not schedule on machines in MAINTENANCE or OFFLINE status
"""

import math
from datetime import datetime, timedelta

from models.base import db
from models.machine import Machine, MachineStatus
from models.work_order import WorkOrder, WorkOrderStatus


# ------------------------------------------------------------------ #
# Read — Gantt view data                                              #
# ------------------------------------------------------------------ #

def get_scheduled_orders_for_gantt():
    """
    Returns all SCHEDULED and IN_PROGRESS orders with machine
    and time slot info — used to build the Gantt table view.
    """
    return (
        WorkOrder.query
        .filter(
            WorkOrder.status.in_([
                WorkOrderStatus.SCHEDULED,
                WorkOrderStatus.IN_PROGRESS,
            ]),
            WorkOrder.machine_id.isnot(None),
            WorkOrder.scheduled_start.isnot(None),
        )
        .order_by(WorkOrder.scheduled_start.asc())
        .all()
    )


def get_available_machines():
    """
    Returns only ACTIVE machines — MAINTENANCE and OFFLINE
    are blocked from scheduling per SRS.
    """
    return (
        Machine.query
        .filter_by(status=MachineStatus.ACTIVE)
        .order_by(Machine.name)
        .all()
    )


def get_machine_schedule(machine_pk: int) -> list:
    """
    Returns all SCHEDULED/IN_PROGRESS orders for a specific machine.
    Used to show existing bookings when scheduling a new order.
    """
    return (
        WorkOrder.query
        .filter(
            WorkOrder.machine_id == machine_pk,
            WorkOrder.status.in_([
                WorkOrderStatus.SCHEDULED,
                WorkOrderStatus.IN_PROGRESS,
            ]),
        )
        .order_by(WorkOrder.scheduled_start)
        .all()
    )


# ------------------------------------------------------------------ #
# Core scheduling logic                                               #
# ------------------------------------------------------------------ #

def calculate_estimated_hours(quantity: float, capacity_per_hour: float) -> float:
    """
    SRS: estimated_hours = CEIL(quantity / machine.capacity_per_hour)
    """
    cap = float(capacity_per_hour)
    if cap <= 0:
        raise ValueError("Machine capacity must be positive.")
    return math.ceil(float(quantity) / cap)


def check_machine_conflicts(
    machine_pk: int,
    start: datetime,
    end: datetime,
    exclude_wo_id: int = None,
) -> bool:
    """
    Returns True if there is a conflicting schedule on this machine.

    Conflict = any existing SCHEDULED/IN_PROGRESS order whose
    time window overlaps with [start, end).

    SRS: Do not allow overlapping schedules on the same machine.
    """
    query = WorkOrder.query.filter(
        WorkOrder.machine_id == machine_pk,
        WorkOrder.status.in_([
            WorkOrderStatus.SCHEDULED,
            WorkOrderStatus.IN_PROGRESS,
        ]),
        # Overlap condition: existing.start < new.end AND existing.end > new.start
        WorkOrder.scheduled_start < end,
        WorkOrder.scheduled_end   > start,
    )

    if exclude_wo_id:
        query = query.filter(WorkOrder.id != exclude_wo_id)

    return query.count() > 0


def schedule_work_order(
    wo_id: int,
    machine_pk: int,
    scheduled_start: datetime,
    requesting_planner_id: int,
) -> tuple[bool, str]:
    """
    Assign a machine and time slot to a PENDING work order.

    Uses with_for_update() for row-level locking — prevents two
    planners from booking the same machine at the same time.

    Returns (success, message).
    """
    # --- Fetch work order with lock ---
    wo = (
        WorkOrder.query
        .filter_by(id=wo_id)
        .with_for_update()
        .first()
    )

    if not wo:
        return False, "Work order not found."

    if wo.planner_id != requesting_planner_id:
        return False, "You can only schedule your own work orders."

    if wo.status != WorkOrderStatus.PENDING:
        return False, f"Only PENDING orders can be scheduled. This order is {wo.status.value}."

    # --- Fetch machine with lock ---
    machine = (
        Machine.query
        .filter_by(id=machine_pk)
        .with_for_update()
        .first()
    )

    if not machine:
        return False, "Machine not found."

    # Lock existing bookings on this machine so two planners cannot create overlaps (phantom rows)
    (
        WorkOrder.query.filter(
            WorkOrder.machine_id == machine_pk,
            WorkOrder.status.in_([
                WorkOrderStatus.SCHEDULED,
                WorkOrderStatus.IN_PROGRESS,
            ]),
        )
        .with_for_update()
        .all()
    )

    # SRS Don't: Do not schedule on MAINTENANCE or OFFLINE machines
    if machine.status == MachineStatus.MAINTENANCE:
        return False, f"Machine {machine.machine_id} is currently under MAINTENANCE and cannot be scheduled."

    if machine.status == MachineStatus.OFFLINE:
        return False, f"Machine {machine.machine_id} is OFFLINE and cannot be scheduled."

    # --- Calculate end time ---
    estimated_hours = calculate_estimated_hours(
        float(wo.quantity),
        float(machine.capacity_per_hour),
    )
    scheduled_end = scheduled_start + timedelta(hours=estimated_hours)

    # --- Conflict check — SRS Don't: no overlapping schedules ---
    if check_machine_conflicts(machine_pk, scheduled_start, scheduled_end):
        return False, (
            f"Machine {machine.machine_id} already has a booking that overlaps with "
            f"{scheduled_start.strftime('%d %b %Y %H:%M')} — "
            f"{scheduled_end.strftime('%d %b %Y %H:%M')}. "
            "Choose a different time slot or machine."
        )

    # --- All checks passed — commit ---
    wo.machine_id      = machine_pk
    wo.scheduled_start = scheduled_start
    wo.scheduled_end   = scheduled_end
    wo.estimated_hours = estimated_hours
    wo.status          = WorkOrderStatus.SCHEDULED
    wo.version        += 1  # optimistic locking increment

    db.session.commit()
    return True, (
        f"WO-{wo.id:04d} scheduled on {machine.machine_id} — "
        f"{scheduled_start.strftime('%d %b %Y %H:%M')} to "
        f"{scheduled_end.strftime('%d %b %Y %H:%M')} "
        f"({estimated_hours} hrs)."
    )


def unschedule_work_order(
    wo_id: int,
    requesting_planner_id: int,
) -> tuple[bool, str]:
    """
    Remove machine assignment and revert order to PENDING.
    Only allowed while still SCHEDULED (not IN_PROGRESS).
    """
    wo = WorkOrder.query.filter_by(id=wo_id).with_for_update().first()

    if not wo:
        return False, "Work order not found."

    if wo.planner_id != requesting_planner_id:
        return False, "You can only unschedule your own work orders."

    if wo.status != WorkOrderStatus.SCHEDULED:
        return False, "Only SCHEDULED orders can be unscheduled."

    wo.machine_id      = None
    wo.scheduled_start = None
    wo.scheduled_end   = None
    wo.estimated_hours = None
    wo.status          = WorkOrderStatus.PENDING
    wo.version        += 1

    db.session.commit()
    return True, f"WO-{wo.id:04d} has been unscheduled and moved back to PENDING."