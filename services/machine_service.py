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
from models.work_order import WorkOrder


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
    user_id: int | None = None,
    ip_address: str | None = None,
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
    db.session.flush()

    from services.audit_service import log_audit
    from models.audit import AuditAction
    log_audit(
        action=AuditAction.MACHINE_CREATE,
        user_id=user_id,
        ip_address=ip_address,
        entity_type="Machine",
        entity_id=machine.id,
        new_values={
            "machine_id": machine_id,
            "name": name.strip(),
            "type": m_type.value,
            "capacity_per_hour": capacity,
            "status": m_status.value,
        },
    )

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
    user_id: int | None = None,
    ip_address: str | None = None,
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

    old_values = {
        "machine_id": machine.machine_id,
        "name": machine.name,
        "type": machine.type.value,
        "capacity_per_hour": float(machine.capacity_per_hour),
        "status": machine.status.value,
    }

    machine.machine_id       = machine_id
    machine.name             = name.strip()
    machine.type             = m_type
    machine.capacity_per_hour = capacity
    machine.status           = m_status

    from services.audit_service import log_audit
    from models.audit import AuditAction
    log_audit(
        action=AuditAction.MACHINE_UPDATE,
        user_id=user_id,
        ip_address=ip_address,
        entity_type="Machine",
        entity_id=machine_pk,
        old_values=old_values,
        new_values={
            "machine_id": machine_id,
            "name": name.strip(),
            "type": m_type.value,
            "capacity_per_hour": capacity,
            "status": m_status.value,
        },
    )

    db.session.commit()
    return True, f"Machine '{machine_id}' updated successfully."


# ------------------------------------------------------------------ #
# Delete                                                              #
# ------------------------------------------------------------------ #

def delete_machine(machine_pk: int, user_id: int | None = None, ip_address: str | None = None) -> tuple[bool, str]:
    machine = db.session.get(Machine, machine_pk)
    if not machine:
        return False, "Machine not found."

    # Any work order still pointing at this machine would violate FK or lose history
    ref_count = WorkOrder.query.filter(WorkOrder.machine_id == machine_pk).count()
    if ref_count > 0:
        return False, (
            f"Cannot delete — this machine is linked to {ref_count} work order(s). "
            "Reassign or archive those orders first."
        )

    from services.audit_service import log_audit
    from models.audit import AuditAction
    log_audit(
        action=AuditAction.MACHINE_DELETE,
        user_id=user_id,
        ip_address=ip_address,
        entity_type="Machine",
        entity_id=machine_pk,
        old_values={
            "machine_id": machine.machine_id,
            "name": machine.name,
            "type": machine.type.value,
        },
    )

    db.session.delete(machine)
    db.session.commit()
    return True, f"Machine '{machine.machine_id}' deleted."