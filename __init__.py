"""
PyPharm - Pharmacy inventory management system.
Part A-C: OOP model, data structures, processing logic
Part D: Iterators, Generators, Context Manager
"""

from models import (
    Product,
    PerishableProduct,
    StandardProduct,
    Location,
    InventoryItem,
    TransferOrder,
    TransferOrderItem,
    Employee,
    OrderActionAuthorizer,
)

from iterators import (
    OrderRegistry,
    OrderIterator,
    open_orders_generator,
    critical_priority_orders_pipeline,
)

from context_managers import LocationMaintenance

__all__ = [
    # Models
    "Product",
    "PerishableProduct",
    "StandardProduct",
    "Location",
    "InventoryItem",
    "TransferOrder",
    "TransferOrderItem",
    "Employee",
    "OrderActionAuthorizer",
    # Iterators & Generators
    "OrderRegistry",
    "OrderIterator",
    "open_orders_generator",
    "critical_priority_orders_pipeline",
    # Context Manager
    "LocationMaintenance",
]
