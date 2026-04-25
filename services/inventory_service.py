"""
services/inventory_service.py

US-6 — Inventory Consumption & Restocking business logic.

SRS acceptance criteria covered:
  - Consume material when work order status → IN_PROGRESS
  - Restock: IN movements with supplier, qty, timestamp
  - Adjust: ADJUST movements with reason, qty_delta
  - Log all movements in InventoryMovement table
  - Trigger low-stock alert after any movement (current_stock < reorder_level)
  - Prevent negative stock values (check before update)

SRS Don'ts:
  - Do not allow negative stock
  - Consumption requires work_order_id for OUT movements
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from models.base import db
from models.inventory import InventoryMovement, MovementType
from models.material import Material
from models.work_order import WorkOrder


# ------------------------------------------------------------------ #
# Read — Movement history                                             #
# ------------------------------------------------------------------ #

def get_movements_for_material(material_pk: int, limit: int = 50) -> list[InventoryMovement]:
    """Return recent inventory movements for a material, newest first."""
    return (
        InventoryMovement.query
        .filter_by(material_id=material_pk)
        .order_by(InventoryMovement.timestamp.desc())
        .limit(limit)
        .all()
    )


def get_all_movements(limit: int = 100) -> list[InventoryMovement]:
    """Return recent inventory movements across all materials."""
    return (
        InventoryMovement.query
        .order_by(InventoryMovement.timestamp.desc())
        .limit(limit)
        .all()
    )


# ------------------------------------------------------------------ #
# Low-stock alert helper                                              #
# ------------------------------------------------------------------ #

def check_low_stock_alert(material: Material) -> dict | None:
    """
    After any movement, check if current_stock <= reorder_level.
    Returns alert dict or None.
    """
    if float(material.current_stock) <= float(material.reorder_level):
        return {
            "material_id": material.id,
            "sku": material.sku,
            "name": material.name,
            "current_stock": float(material.current_stock),
            "reorder_level": float(material.reorder_level),
            "unit": material.unit.value,
        }
    return None


# ------------------------------------------------------------------ #
# Consume — OUT movements when work order → IN_PROGRESS              #
# ------------------------------------------------------------------ #

def consume_materials_for_work_order(work_order: WorkOrder) -> tuple[bool, str, list[dict]]:
    """
    Deduct all BOM materials from stock and create OUT movements.
    Called when work order transitions SCHEDULED → IN_PROGRESS.

    Returns (success, message, low_stock_alerts).

    SRS constraints:
      - All materials must have sufficient stock
      - No negative stock allowed
      - Each OUT movement links to work_order_id
    """
    if not work_order.materials:
        return False, "Work order has no materials in BOM.", []

    alerts = []

    for bom_line in work_order.materials:
        material = bom_line.material
        required_qty = Decimal(str(bom_line.required_qty))
        current_stock = Decimal(str(material.current_stock))

        if current_stock < required_qty:
            return False, (
                f"Insufficient stock for {material.sku} ({material.name}). "
                f"Required: {required_qty} {material.unit.value}, "
                f"Available: {current_stock} {material.unit.value}."
            ), []

    for bom_line in work_order.materials:
        material = bom_line.material
        required_qty = Decimal(str(bom_line.required_qty))

        material.current_stock = Decimal(str(material.current_stock)) - required_qty

        movement = InventoryMovement(
            material_id=material.id,
            type=MovementType.OUT,
            qty=required_qty,
            work_order_id=work_order.id,
            timestamp=datetime.now(timezone.utc),
        )
        db.session.add(movement)

        alert = check_low_stock_alert(material)
        if alert:
            alerts.append(alert)
            # US-8: Enqueue low stock notifications to managers
            from services.notification_service import enqueue_low_stock_alert
            enqueue_low_stock_alert(material)

    return True, "Materials consumed successfully.", alerts


# ------------------------------------------------------------------ #
# Restock — IN movements (Manager)                                    #
# ------------------------------------------------------------------ #

def restock_material(
    material_pk: int,
    qty: float,
    supplier: str,
    user_id: int | None = None,
    ip_address: str | None = None,
) -> tuple[bool, str, dict | None]:
    """
    Add stock to a material and create an IN movement.
    Returns (success, message, low_stock_alert_or_None).

    SRS acceptance:
      - IN movement with supplier, qty, timestamp
    """
    material = db.session.get(Material, material_pk)
    if not material:
        return False, "Material not found.", None

    try:
        restock_qty = Decimal(str(qty))
        if restock_qty <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        return False, "Restock quantity must be a positive number.", None

    supplier = supplier.strip()
    if not supplier:
        return False, "Supplier name is required.", None

    material.current_stock = Decimal(str(material.current_stock)) + restock_qty

    movement = InventoryMovement(
        material_id=material.id,
        type=MovementType.IN,
        qty=restock_qty,
        supplier=supplier,
        timestamp=datetime.now(timezone.utc),
    )
    db.session.add(movement)

    # US-10: Audit log for restock
    from services.audit_service import log_audit
    from models.audit import AuditAction
    log_audit(
        action=AuditAction.INVENTORY_ADJUST,
        user_id=user_id,
        ip_address=ip_address,
        entity_type="Material",
        entity_id=material.id,
        old_values={"current_stock": float(material.current_stock) - float(restock_qty)},
        new_values={
            "current_stock": float(material.current_stock),
            "restock_qty": float(restock_qty),
            "supplier": supplier,
            "type": "IN",
        },
    )

    db.session.commit()

    alert = check_low_stock_alert(material)
    return True, (
        f"Restocked {restock_qty} {material.unit.value} of {material.sku} from {supplier}."
    ), alert


# ------------------------------------------------------------------ #
# Adjust — ADJUST movements (Manager)                                 #
# ------------------------------------------------------------------ #

def adjust_material(
    material_pk: int,
    qty_delta: float,
    reason: str,
    user_id: int | None = None,
    ip_address: str | None = None,
) -> tuple[bool, str, dict | None]:
    """
    Adjust stock by a signed delta (+/-) and create an ADJUST movement.
    Returns (success, message, low_stock_alert_or_None).

    SRS acceptance:
      - ADJUST movement with reason, qty_delta
      - qty_delta can be positive (add) or negative (remove)
      - Final stock must not be negative
    """
    material = db.session.get(Material, material_pk)
    if not material:
        return False, "Material not found.", None

    try:
        delta = Decimal(str(qty_delta))
    except InvalidOperation:
        return False, "Invalid quantity delta.", None

    if delta == 0:
        return False, "Adjustment delta cannot be zero.", None

    reason = reason.strip()
    if not reason:
        return False, "Reason is required for adjustments.", None

    new_stock = Decimal(str(material.current_stock)) + delta
    if new_stock < 0:
        return False, (
            f"Adjustment would result in negative stock ({new_stock} {material.unit.value}). "
            "Cannot proceed."
        ), None

    old_stock = float(material.current_stock)
    material.current_stock = new_stock

    movement = InventoryMovement(
        material_id=material.id,
        type=MovementType.ADJUST,
        qty=abs(delta),
        qty_delta=delta,
        reason=reason,
        timestamp=datetime.now(timezone.utc),
    )
    db.session.add(movement)

    # US-10: Audit log for adjustment
    from services.audit_service import log_audit
    from models.audit import AuditAction
    log_audit(
        action=AuditAction.INVENTORY_ADJUST,
        user_id=user_id,
        ip_address=ip_address,
        entity_type="Material",
        entity_id=material.id,
        old_values={"current_stock": old_stock},
        new_values={
            "current_stock": float(new_stock),
            "qty_delta": float(delta),
            "reason": reason,
            "type": "ADJUST",
        },
    )

    db.session.commit()

    alert = check_low_stock_alert(material)
    action = "added" if delta > 0 else "removed"
    return True, (
        f"Adjusted {material.sku}: {action} {abs(delta)} {material.unit.value}. "
        f"New stock: {new_stock} {material.unit.value}."
    ), alert
