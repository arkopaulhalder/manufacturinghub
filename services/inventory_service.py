"""
services/inventory_service.py

US-6 — Inventory Consumption & Restocking.

SRS acceptance criteria covered:
  Consume  → when work order status → IN_PROGRESS:
               deduct required_qty from current_stock
               log movement type=OUT, order_id, qty, timestamp
  Restock  → Manager adds stock via Restock form:
               log movement type=IN, supplier, qty, timestamp
  Adjust   → Manager manually adjusts stock:
               log movement type=ADJUST, reason, qty_delta
  Alert    → after any movement, if current_stock < reorder_level
               enqueue LOW_STOCK notification to manager

SRS Don'ts:
  - Do not allow negative stock values
  - Do not allow consumption without an associated work order
  - Do not auto-consume until order is IN_PROGRESS
"""

from datetime import datetime, timezone

from models.base import db
from models.inventory import InventoryMovement, MovementType
from models.material import Material
from models.work_order import WorkOrder, WorkOrderMaterial, WorkOrderStatus


def _now():
    return datetime.now(timezone.utc)

# Read

def get_movements_for_material(material_id: int) -> list:
    return (
        InventoryMovement.query
        .filter_by(material_id=material_id)
        .order_by(InventoryMovement.timestamp.desc())
        .all()
    )


def get_all_movements() -> list:
    return (
        InventoryMovement.query
        .order_by(InventoryMovement.timestamp.desc())
        .limit(200)
        .all()
    )


def get_low_stock_materials() -> list:
    """Returns materials where current_stock <= reorder_level."""
    return [
        m for m in Material.query.all()
        if float(m.current_stock) <= float(m.reorder_level)
    ]


# US-6: Consume — triggered when SCHEDULED → IN_PROGRESS

def start_production(wo_id: int, requesting_planner_id: int) -> tuple[bool, str]:
    """
    Transition a SCHEDULED work order to IN_PROGRESS.
    Deducts all BOM required_qty from material current_stock.
    Logs an OUT movement per material.
    Alerts if any material drops below reorder_level.

    SRS Don't: do not allow consumption without a work order.
    SRS Don't: do not allow negative stock values.
    """
    wo = WorkOrder.query.filter_by(id=wo_id).with_for_update().first()

    if not wo:
        return False, "Work order not found."

    if wo.planner_id != requesting_planner_id:
        return False, "You can only start your own work orders."

    if wo.status != WorkOrderStatus.SCHEDULED:
        return False, f"Only SCHEDULED orders can be started. This order is {wo.status.value}."

    # --- Pre-flight check: enough stock for all BOM lines? ---
    shortfalls = []
    for bom in wo.materials:
        material = db.session.get(Material, bom.material_id)
        if float(material.current_stock) < float(bom.required_qty):
            shortfalls.append(
                f"{material.name} (need {bom.required_qty}, have {material.current_stock})"
            )

    if shortfalls:
        return False, (
            "Insufficient stock to start production: " + "; ".join(shortfalls) +
            ". Ask the manager to restock before starting."
        )

    # --- Consume each BOM material ---
    for bom in wo.materials:
        material = db.session.get(Material, bom.material_id)

        material.current_stock = float(material.current_stock) - float(bom.required_qty)

        movement = InventoryMovement(
            material_id=bom.material_id,
            type=MovementType.OUT,
            qty=float(bom.required_qty),
            work_order_id=wo.id,
            timestamp=_now(),
        )
        db.session.add(movement)

        # Enqueue low-stock notification if needed
        _check_and_enqueue_low_stock(material)

    wo.status   = WorkOrderStatus.IN_PROGRESS
    wo.version += 1
    db.session.commit()

    return True, f"WO-{wo.id:04d} is now IN PROGRESS. Inventory has been consumed."

# US-6: Complete production

def complete_production(wo_id: int, requesting_planner_id: int) -> tuple[bool, str]:
    """Transition IN_PROGRESS → COMPLETED."""
    wo = WorkOrder.query.filter_by(id=wo_id).with_for_update().first()

    if not wo:
        return False, "Work order not found."

    if wo.planner_id != requesting_planner_id:
        return False, "You can only complete your own work orders."

    if wo.status != WorkOrderStatus.IN_PROGRESS:
        return False, f"Only IN_PROGRESS orders can be completed. This order is {wo.status.value}."

    wo.status   = WorkOrderStatus.COMPLETED
    wo.version += 1
    db.session.commit()

    return True, f"WO-{wo.id:04d} has been marked COMPLETED."

# US-6: Restock (IN movement) — Manager only

def restock_material(
    material_id: int,
    qty: float,
    supplier: str,
) -> tuple[bool, str]:
    """
    Add stock to a material (type=IN).
    Logs supplier name and timestamp.
    """
    material = db.session.get(Material, material_id)
    if not material:
        return False, "Material not found."

    try:
        qty = float(qty)
        if qty <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return False, "Quantity must be a positive number."

    material.current_stock = float(material.current_stock) + qty

    movement = InventoryMovement(
        material_id=material_id,
        type=MovementType.IN,
        qty=qty,
        supplier=supplier.strip() if supplier else None,
        timestamp=_now(),
    )
    db.session.add(movement)
    db.session.commit()

    return True, f"Restocked {qty} {material.unit.value} of {material.name}. New stock: {material.current_stock}."


# US-6: Adjust (ADJUST movement) — Manager only


def adjust_stock(
    material_id: int,
    qty_delta: float,
    reason: str,
) -> tuple[bool, str]:
    """
    Manually adjust stock by a signed delta.
    Positive delta = add, negative delta = remove.
    SRS Don't: do not allow negative stock values.
    """
    material = db.session.get(Material, material_id)
    if not material:
        return False, "Material not found."

    if not reason or not reason.strip():
        return False, "A reason is required for stock adjustment."

    try:
        delta = float(qty_delta)
    except (TypeError, ValueError):
        return False, "Delta must be a number."

    new_stock = float(material.current_stock) + delta

    if new_stock < 0:
        return False, (
            f"Adjustment would result in negative stock "
            f"({material.current_stock} + {delta} = {new_stock:.3f}). "
            "Not allowed."
        )

    material.current_stock = new_stock

    movement = InventoryMovement(
        material_id=material_id,
        type=MovementType.ADJUST,
        qty=abs(delta),
        qty_delta=delta,
        reason=reason.strip(),
        timestamp=_now(),
    )
    db.session.add(movement)
    _check_and_enqueue_low_stock(material)
    db.session.commit()

    return True, f"Stock adjusted by {delta:+.3f}. New stock: {new_stock:.3f} {material.unit.value}."

# Internal helper

def _check_and_enqueue_low_stock(material: Material):
    """
    If current_stock <= reorder_level, create a LOW_STOCK
    notification row for all MANAGER users.
    Called inside a transaction — does not commit itself.
    """
    if float(material.current_stock) > float(material.reorder_level):
        return

    from models.notification import Notification, NotificationType, NotificationStatus
    from models.user import User, UserRole

    managers = User.query.filter_by(role=UserRole.MANAGER).all()
    for manager in managers:
        notif = Notification(
            type=NotificationType.LOW_STOCK,
            recipient_id=manager.id,
            status=NotificationStatus.QUEUED,
            payload={
                "material_id":   material.id,
                "sku":           material.sku,
                "name":          material.name,
                "current_stock": str(material.current_stock),
                "reorder_level": str(material.reorder_level),
                "unit":          material.unit.value,
            },
        )
        db.session.add(notif)