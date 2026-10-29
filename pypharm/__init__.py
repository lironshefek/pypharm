"""
PyPharm - Pharmacy inventory management system.
Part A-C: OOP model, data structures, processing logic
Part D: Iterators, Generators, Context Manager
"""

from .models import (
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

from .iterators import (
    OrderBatch,
    OrderIterator,
    open_orders_generator,
    critical_priority_orders_pipeline,
)

from .context_managers import LocationMaintenance
from .factories import ProductFactory

from .repository import load_sample_data_from_jsonl, load_transfer_orders_from_jsonl, load_inventory_items_from_jsonl
from .config import WeatherConfig
from .exceptions import (
    WeatherAPIException,
    WeatherCommunicationError,
    WeatherHTTPError,
    WeatherJSONError,
    WeatherDataError,
)
from .weather import WeatherReading
from .api_client import WeatherAPIClient, get_weather_with_retry
from .services import WeatherService
from .observers import (
    ApprovalEventPublisher,
    ApprovalRequiredEvent,
    AuditLogObserver,
    IntegrityAlertObserver,
)

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
    "OrderBatch",
    "OrderIterator",
    "open_orders_generator",
    "critical_priority_orders_pipeline",
    # Context Manager
    "LocationMaintenance",
    "ProductFactory",
    # Repository
    "load_sample_data_from_jsonl",
    "load_transfer_orders_from_jsonl",
    "load_inventory_items_from_jsonl",
    # API Client (Stage 2)
    "WeatherConfig",
    "WeatherAPIException",
    "WeatherCommunicationError",
    "WeatherHTTPError",
    "WeatherJSONError",
    "WeatherDataError",
    "WeatherReading",
    "WeatherAPIClient",
    "get_weather_with_retry",
    "WeatherService",
    "ApprovalEventPublisher",
    "ApprovalRequiredEvent",
    "AuditLogObserver",
    "IntegrityAlertObserver",
]
