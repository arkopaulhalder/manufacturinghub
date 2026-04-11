"""
models/__init__.py

Re-exports every model class so the rest of the app can do:
    from models import User, Machine, WorkOrder, ...
"""

from .user         import User, UserRole, NotificationPreference
from .machine      import Machine, MachineType, MachineStatus
from .material     import Material, MaterialUnit
from .work_order   import WorkOrder, WorkOrderMaterial, WorkOrderPriority, WorkOrderStatus
from .inventory    import InventoryMovement, MovementType
from .maintenance  import MaintenanceRule, MaintenanceLog, MaintenanceFrequency
from .notification import Notification, NotificationType, NotificationStatus
from .audit        import AuditLog, AuditAction

__all__ = [
    # User
    "User", "UserRole", "NotificationPreference",
    # Machine
    "Machine", "MachineType", "MachineStatus",
    # Material
    "Material", "MaterialUnit",
    # Work Order
    "WorkOrder", "WorkOrderMaterial", "WorkOrderPriority", "WorkOrderStatus",
    # Inventory
    "InventoryMovement", "MovementType",
    # Maintenance
    "MaintenanceRule", "MaintenanceLog", "MaintenanceFrequency",
    # Notification
    "Notification", "NotificationType", "NotificationStatus",
    # Audit
    "AuditLog", "AuditAction",
]
