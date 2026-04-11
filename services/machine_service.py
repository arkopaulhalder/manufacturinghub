"""
services/machine_service.py

US-3 — Machine catalog business logic (Manager only).

SRS acceptance criteria covered:
  - CRUD: add, update, list, delete machines
  - Fields: machine_id, name, type [CNC/LATHE/PRESS], capacity_per_hour,
            status [ACTIVE/MAINTENANCE/OFFLINE]
  - No duplicate machine_id
  - Positive capacity_per_hour
  - Prevent deletion of machines referenced in active work orders
  - Only plant managers can create/edit (enforced via @requires_role in routes)
  - Production planners have read-only access
"""

from models.base import db
from models.machine import Machine, MachineType, MachineStatus
from models.work_order import WorkOrder, WorkOrderStatus


# ------------------------------------------------------------------ #
# Read                                                                #
# ------------------------------------------------------------------ #

def get_all_machines():
    return Machine.query.order_by(Machine.name).all()


def get_machine_by_id(machine_pk: int):
    return db.session.get(Machine, machine_pk)


# ------------------------------------------------------------------ #
# Create                                                              #
# ------------------------------------------------------------------ #

def create_machine(
    machine_id: str,
    name: str,
    type_str: str,
    capacity_per_hour: float,
    status_str: str = "ACTIVE",
) -> tuple[bool, str]:
    """
    Add a new machine to the catalog.
    Returns (success, message).
    """
    machine_id = machine_id.strip().upper()

    # No duplicate machine_id — 
    if Machine.query.filter_by(machine_id=machine_id).first():
        return False, f"Machine ID '{machine_id}' already exists."

    # Positive capacity — 
    try:
        capacity = float(capacity_per_hour)
        if capacity <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return False, "Capacity per hour must be a positive number."

    try:
        m_type = MachineType[type_str.upper()]
    except KeyError:
        return False, "Invalid machine type. Choose CNC, LATHE or PRESS."

    try:
        m_status = MachineStatus[status_str.upper()]
    except KeyError:
        return False, "Invalid status. Choose ACTIVE, MAINTENANCE or OFFLINE."

    machine = Machine(
        machine_id=machine_id,
        name=name.strip(),
        type=m_type,
        capacity_per_hour=capacity,
        status=m_status,
    )
    db.session.add(machine)
    db.session.commit()
    return True, f"Machine '{machine_id}' added successfully."


# ------------------------------------------------------------------ #
# Update                                                              #
# ------------------------------------------------------------------ #

def update_machine(
    machine_pk: int,
    machine_id: str,
    name: str,
    type_str: str,
    capacity_per_hour: float,
    status_str: str,
) -> tuple[bool, str]:
    machine = db.session.get(Machine, machine_pk)
    if not machine:
        return False, "Machine not found."

    machine_id = machine_id.strip().upper()

    # Duplicate check — exclude self
    existing = Machine.query.filter_by(machine_id=machine_id).first()
    if existing and existing.id != machine_pk:
        return False, f"Machine ID '{machine_id}' already exists."

    try:
        capacity = float(capacity_per_hour)
        if capacity <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return False, "Capacity per hour must be a positive number."

    try:
        m_type = MachineType[type_str.upper()]
    except KeyError:
        return False, "Invalid machine type."

    try:
        m_status = MachineStatus[status_str.upper()]
    except KeyError:
        return False, "Invalid status."

    machine.machine_id       = machine_id
    machine.name             = name.strip()
    machine.type             = m_type
    machine.capacity_per_hour = capacity
    machine.status           = m_status

    db.session.commit()
    return True, f"Machine '{machine_id}' updated successfully."


# ------------------------------------------------------------------ #
# Delete                                                              #
# ------------------------------------------------------------------ #

def delete_machine(machine_pk: int) -> tuple[bool, str]:
    machine = db.session.get(Machine, machine_pk)
    if not machine:
        return False, "Machine not found."

    # SRS Dos: prevent deletion if referenced in active work orders
    active_statuses = [
        WorkOrderStatus.PENDING,
        WorkOrderStatus.SCHEDULED,
        WorkOrderStatus.IN_PROGRESS,
    ]
    active_orders = WorkOrder.query.filter(
        WorkOrder.machine_id == machine_pk,
        WorkOrder.status.in_(active_statuses),
    ).count()

    if active_orders > 0:
        return False, (
            f"Cannot delete — this machine has {active_orders} active work order(s). "
            "Complete or reassign them first."
        )

    db.session.delete(machine)
    db.session.commit()
    return True, f"Machine '{machine.machine_id}' deleted."