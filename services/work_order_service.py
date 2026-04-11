"""
services/work_order_service.py

US-4 — Work Order Creation business logic (Planner).

SRS acceptance criteria covered:
  - Fields: product_name, quantity, priority [LOW/MEDIUM/HIGH],
            required_materials (BOM), target_completion_date
  - Validate that required materials exist in catalog
  - Work order starts in PENDING status
  - Planner can SUBMIT for scheduling (status stays PENDING until scheduled)
  - Allow saving draft work orders
  - Show material availability warnings (current_stock < required_qty)
  - Do not allow zero or negative quantities
  - Do not auto-consume inventory until order is IN_PROGRESS (US-6)
"""

import math
from datetime import date

from models.base import db
from models.material import Material
from models.work_order import WorkOrder, WorkOrderMaterial, WorkOrderPriority, WorkOrderStatus


# ------------------------------------------------------------------ #
# Read                                                                #
# ------------------------------------------------------------------ #

def get_all_work_orders():
    """All work orders — planners see own, managers see all (filter in route)."""
    return WorkOrder.query.order_by(WorkOrder.created_at.desc()).all()


def get_work_orders_for_planner(planner_id: int):
    return (
        WorkOrder.query
        .filter_by(planner_id=planner_id)
        .order_by(WorkOrder.created_at.desc())
        .all()
    )


def get_work_order_by_id(wo_id: int):
    return db.session.get(WorkOrder, wo_id)


def check_material_availability(bom_lines: list[dict]) -> list[dict]:
    """
    Given a list of {material_id, required_qty} dicts,
    return a list of warnings where current_stock < required_qty.
    Used to show warnings on the form — SRS Dos.
    """
    warnings = []
    for line in bom_lines:
        material = db.session.get(Material, int(line["material_id"]))
        if not material:
            continue
        required = float(line["required_qty"])
        available = float(material.current_stock)
        if available < required:
            warnings.append({
                "sku": material.sku,
                "name": material.name,
                "required": required,
                "available": available,
                "shortfall": round(required - available, 3),
                "unit": material.unit.value,
            })
    return warnings


# ------------------------------------------------------------------ #
# Create                                                              #
# ------------------------------------------------------------------ #

def create_work_order(
    product_name: str,
    quantity: float,
    priority_str: str,
    target_completion_date,       # date or None
    planner_id: int,
    bom_lines: list[dict],        # [{"material_id": int, "required_qty": float}, ...]
) -> tuple[bool, str, WorkOrder | None]:
    """
    Create a new work order in PENDING status with its BOM.
    Returns (success, message, work_order_or_None).

    SRS Don'ts:
      - Do not allow zero or negative quantities
      - Do not auto-consume inventory (happens in US-6 on IN_PROGRESS)
    """
    product_name = product_name.strip()
    if not product_name:
        return False, "Product name is required.", None

    try:
        qty = float(quantity)
        if qty <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return False, "Quantity must be a positive number.", None

    try:
        priority = WorkOrderPriority[priority_str.upper()]
    except KeyError:
        return False, "Invalid priority. Choose LOW, MEDIUM or HIGH.", None

    # Validate all materials exist in catalog — SRS acceptance criteria
    validated_bom = []
    for line in bom_lines:
        material = db.session.get(Material, int(line["material_id"]))
        if not material:
            return False, f"Material ID {line['material_id']} does not exist in catalog.", None
        try:
            req_qty = float(line["required_qty"])
            if req_qty <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return False, f"Required quantity for {material.name} must be positive.", None
        validated_bom.append({"material": material, "required_qty": req_qty})

    if not validated_bom:
        return False, "At least one material must be added to the BOM.", None

    wo = WorkOrder(
        product_name=product_name,
        quantity=qty,
        priority=priority,
        target_completion_date=target_completion_date,
        status=WorkOrderStatus.PENDING,
        planner_id=planner_id,
    )
    db.session.add(wo)
    db.session.flush()  # get wo.id before adding BOM lines

    for item in validated_bom:
        bom = WorkOrderMaterial(
            work_order_id=wo.id,
            material_id=item["material"].id,
            required_qty=item["required_qty"],
        )
        db.session.add(bom)

    db.session.commit()
    return True, f"Work order WO-{wo.id:04d} created successfully.", wo


# ------------------------------------------------------------------ #
# Update                                                              #
# ------------------------------------------------------------------ #

def update_work_order(
    wo_id: int,
    requesting_planner_id: int,
    product_name: str,
    quantity: float,
    priority_str: str,
    target_completion_date,
    bom_lines: list[dict],
) -> tuple[bool, str]:
    """
    Update a PENDING work order.
    Only the planner who created it can edit it,
    and only while it is still PENDING.
    """
    wo = db.session.get(WorkOrder, wo_id)
    if not wo:
        return False, "Work order not found."

    if wo.planner_id != requesting_planner_id:
        return False, "You can only edit your own work orders."

    if wo.status != WorkOrderStatus.PENDING:
        return False, "Only PENDING work orders can be edited."

    product_name = product_name.strip()
    if not product_name:
        return False, "Product name is required."

    try:
        qty = float(quantity)
        if qty <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return False, "Quantity must be a positive number."

    try:
        priority = WorkOrderPriority[priority_str.upper()]
    except KeyError:
        return False, "Invalid priority."

    validated_bom = []
    for line in bom_lines:
        material = db.session.get(Material, int(line["material_id"]))
        if not material:
            return False, f"Material ID {line['material_id']} does not exist in catalog."
        try:
            req_qty = float(line["required_qty"])
            if req_qty <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return False, f"Required quantity for {material.name} must be positive."
        validated_bom.append({"material": material, "required_qty": req_qty})

    if not validated_bom:
        return False, "At least one material must be added to the BOM."

    wo.product_name           = product_name
    wo.quantity               = qty
    wo.priority               = priority
    wo.target_completion_date = target_completion_date

    # Replace BOM lines
    WorkOrderMaterial.query.filter_by(work_order_id=wo_id).delete()
    for item in validated_bom:
        bom = WorkOrderMaterial(
            work_order_id=wo.id,
            material_id=item["material"].id,
            required_qty=item["required_qty"],
        )
        db.session.add(bom)

    db.session.commit()
    return True, f"Work order WO-{wo.id:04d} updated successfully."


# ------------------------------------------------------------------ #
# Delete                                                              #
# ------------------------------------------------------------------ #

def delete_work_order(wo_id: int, requesting_planner_id: int) -> tuple[bool, str]:
    wo = db.session.get(WorkOrder, wo_id)
    if not wo:
        return False, "Work order not found."

    if wo.planner_id != requesting_planner_id:
        return False, "You can only delete your own work orders."

    if wo.status not in [WorkOrderStatus.PENDING]:
        return False, "Only PENDING work orders can be deleted."

    db.session.delete(wo)
    db.session.commit()
    return True, f"Work order WO-{wo_id:04d} deleted."