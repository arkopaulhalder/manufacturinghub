"""
services/material_service.py

US-3 — Material catalog business logic (Manager only).

SRS acceptance criteria covered:
  - CRUD: add, update, list, delete materials
  - Fields: sku, name, unit [KG/LITRE/PIECE], current_stock,
            reorder_level, unit_cost
  - No duplicate SKUs
  - Positive values for stock, reorder_level, unit_cost
  - Prevent deletion of materials referenced in active work orders
  - Only plant managers can create/edit (enforced via @requires_role in routes)
  - Production planners have read-only access
"""

from models.base import db
from models.material import Material, MaterialUnit
from models.work_order import WorkOrder, WorkOrderMaterial, WorkOrderStatus


# ------------------------------------------------------------------ #
# Read                                                                #
# ------------------------------------------------------------------ #

def get_all_materials():
    return Material.query.order_by(Material.name).all()


def get_material_by_id(material_pk: int):
    return db.session.get(Material, material_pk)


# ------------------------------------------------------------------ #
# Create                                                              #
# ------------------------------------------------------------------ #

def create_material(
    sku: str,
    name: str,
    unit_str: str,
    current_stock: float,
    reorder_level: float,
    unit_cost: float,
) -> tuple[bool, str]:
    """
    Add a new material to the catalog.
    Returns (success, message).
    """
    sku = sku.strip().upper()

    # No duplicate SKU — SRS Don't
    if Material.query.filter_by(sku=sku).first():
        return False, f"SKU '{sku}' already exists."

    try:
        stock = float(current_stock)
        if stock < 0:
            raise ValueError
    except (TypeError, ValueError):
        return False, "Current stock must be zero or a positive number."

    try:
        reorder = float(reorder_level)
        if reorder <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return False, "Reorder level must be a positive number."

    try:
        cost = float(unit_cost)
        if cost <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return False, "Unit cost must be a positive number."

    try:
        unit = MaterialUnit[unit_str.upper()]
    except KeyError:
        return False, "Invalid unit. Choose KG, LITRE or PIECE."

    material = Material(
        sku=sku,
        name=name.strip(),
        unit=unit,
        current_stock=stock,
        reorder_level=reorder,
        unit_cost=cost,
    )
    db.session.add(material)
    db.session.commit()
    return True, f"Material '{sku}' added successfully."


# ------------------------------------------------------------------ #
# Update                                                              #
# ------------------------------------------------------------------ #

def update_material(
    material_pk: int,
    sku: str,
    name: str,
    unit_str: str,
    current_stock: float,
    reorder_level: float,
    unit_cost: float,
) -> tuple[bool, str]:
    material = db.session.get(Material, material_pk)
    if not material:
        return False, "Material not found."

    sku = sku.strip().upper()

    # Duplicate check — exclude self
    existing = Material.query.filter_by(sku=sku).first()
    if existing and existing.id != material_pk:
        return False, f"SKU '{sku}' already exists."

    try:
        stock = float(current_stock)
        if stock < 0:
            raise ValueError
    except (TypeError, ValueError):
        return False, "Current stock must be zero or a positive number."

    try:
        reorder = float(reorder_level)
        if reorder <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return False, "Reorder level must be a positive number."

    try:
        cost = float(unit_cost)
        if cost <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return False, "Unit cost must be a positive number."

    try:
        unit = MaterialUnit[unit_str.upper()]
    except KeyError:
        return False, "Invalid unit."

    material.sku           = sku
    material.name          = name.strip()
    material.unit          = unit
    material.current_stock = stock
    material.reorder_level = reorder
    material.unit_cost     = cost

    db.session.commit()
    return True, f"Material '{sku}' updated successfully."


# ------------------------------------------------------------------ #
# Delete                                                              #
# ------------------------------------------------------------------ #

def delete_material(material_pk: int) -> tuple[bool, str]:
    material = db.session.get(Material, material_pk)
    if not material:
        return False, "Material not found."

    # SRS Dos: prevent deletion if referenced in active work orders
    active_statuses = [
        WorkOrderStatus.PENDING,
        WorkOrderStatus.SCHEDULED,
        WorkOrderStatus.IN_PROGRESS,
    ]
    active_ref = (
        db.session.query(WorkOrderMaterial)
        .join(WorkOrder)
        .filter(
            WorkOrderMaterial.material_id == material_pk,
            WorkOrder.status.in_(active_statuses),
        )
        .count()
    )

    if active_ref > 0:
        return False, (
            f"Cannot delete — this material is used in {active_ref} active work order(s). "
            "Complete or update those orders first."
        )

    db.session.delete(material)
    db.session.commit()
    return True, f"Material '{material.sku}' deleted."