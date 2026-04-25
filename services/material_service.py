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
from models.work_order import WorkOrderMaterial


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
    user_id: int | None = None,
    ip_address: str | None = None,
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
    db.session.flush()

    from services.audit_service import log_audit
    from models.audit import AuditAction
    log_audit(
        action=AuditAction.MATERIAL_CREATE,
        user_id=user_id,
        ip_address=ip_address,
        entity_type="Material",
        entity_id=material.id,
        new_values={
            "sku": sku,
            "name": name.strip(),
            "unit": unit.value,
            "current_stock": stock,
            "reorder_level": reorder,
            "unit_cost": cost,
        },
    )

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
    user_id: int | None = None,
    ip_address: str | None = None,
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

    old_values = {
        "sku": material.sku,
        "name": material.name,
        "unit": material.unit.value,
        "current_stock": float(material.current_stock),
        "reorder_level": float(material.reorder_level),
        "unit_cost": float(material.unit_cost),
    }

    material.sku           = sku
    material.name          = name.strip()
    material.unit          = unit
    material.current_stock = stock
    material.reorder_level = reorder
    material.unit_cost     = cost

    from services.audit_service import log_audit
    from models.audit import AuditAction
    log_audit(
        action=AuditAction.MATERIAL_UPDATE,
        user_id=user_id,
        ip_address=ip_address,
        entity_type="Material",
        entity_id=material_pk,
        old_values=old_values,
        new_values={
            "sku": sku,
            "name": name.strip(),
            "unit": unit.value,
            "current_stock": stock,
            "reorder_level": reorder,
            "unit_cost": cost,
        },
    )

    db.session.commit()
    return True, f"Material '{sku}' updated successfully."


# ------------------------------------------------------------------ #
# Delete                                                              #
# ------------------------------------------------------------------ #

def delete_material(material_pk: int, user_id: int | None = None, ip_address: str | None = None) -> tuple[bool, str]:
    material = db.session.get(Material, material_pk)
    if not material:
        return False, "Material not found."

    # BOM lines keep FK to materials — block delete if any work order references this SKU
    bom_ref = WorkOrderMaterial.query.filter_by(material_id=material_pk).count()
    if bom_ref > 0:
        return False, (
            f"Cannot delete — this material appears on {bom_ref} work order BOM line(s). "
            "Remove it from those orders first."
        )

    from services.audit_service import log_audit
    from models.audit import AuditAction
    log_audit(
        action=AuditAction.MATERIAL_DELETE,
        user_id=user_id,
        ip_address=ip_address,
        entity_type="Material",
        entity_id=material_pk,
        old_values={
            "sku": material.sku,
            "name": material.name,
            "unit": material.unit.value,
        },
    )

    db.session.delete(material)
    db.session.commit()
    return True, f"Material '{material.sku}' deleted."