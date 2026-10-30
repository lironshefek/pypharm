"""
processing.py - Data structures and collection processing.
List, tuple, set, dict, deque, heapq, comprehensions, sorting, and business logic.
"""

from collections import deque
import heapq
from .models import (
    Product,
    Location,
    InventoryItem,
    TransferOrder,
    Employee,
    OrderActionAuthorizer,
)


def process_shipment_manifest(manifest_records: list[tuple]) -> dict:
    summary = {}
    for record in manifest_records:
        order_id, destination, *skus = record
        summary[order_id] = {
            "destination": destination,
            "items_count": len(skus),
            "skus": skus,
        }
    return summary


class LocationCategoryTracker:
    def __init__(self):
        self.active_locations: set[str] = set()
        self.refrigerated_locations: set[str] = set()

    def register_location(self, location: Location | str, is_refrigerated: bool = False):
        loc_id = location.location_id if isinstance(location, Location) else str(location)
        self.active_locations.add(loc_id)
        if is_refrigerated:
            self.refrigerated_locations.add(loc_id)

    def deactivate_location(self, location: Location | str):
        loc_id = location.location_id if isinstance(location, Location) else str(location)
        self.active_locations.discard(loc_id)
        if loc_id in self.refrigerated_locations:
            self.refrigerated_locations.remove(loc_id)

    def check_location_exists(self, location: Location | str) -> bool:
        loc_id = location.location_id if isinstance(location, Location) else str(location)
        return loc_id in self.active_locations

    def get_non_refrigerated_locations(self) -> set[str]:
        return self.active_locations - self.refrigerated_locations

    def get_common_locations(self, other_set: set[str]) -> set[str]:
        return self.active_locations.intersection(other_set)

    def combine_locations(self, other_set: set[str]) -> set[str]:
        return self.active_locations | other_set


class InventoryRegistry:
    def __init__(self):
        self.products_by_sku: dict[str, Product] = {}
        self.inventory_by_location: dict[str, list[InventoryItem]] = {}

    def add_product(self, product: Product, overwrite: bool = False):
        if product.sku in self.products_by_sku and not overwrite:
            raise ValueError(f"Product with SKU {product.sku!r} already exists in registry.")
        self.products_by_sku[product.sku] = product

    def get_product(self, sku: str) -> Product:
        return self.products_by_sku.get(sku, None)
    
    def count_products_by_brand(self) -> dict[str, int]:
        brand_counts = {}
        for product in self.products_by_sku.values():
            brand_counts[product.brand] = brand_counts.get(product.brand, 0) + 1
        return brand_counts

    def register_inventory_item(self, item: InventoryItem):
        if item.location_id not in self.inventory_by_location:
            self.inventory_by_location[item.location_id] = []
        self.inventory_by_location[item.location_id].append(item)

    def print_inventory_summary(self):
        for loc_id, items_list in self.inventory_by_location.items():
            print(f"Location {loc_id} holds {len(items_list)} unique inventory items.")


class OrderProcessingQueue:
    def __init__(self):
        self._queue = deque()

    def enqueue_order(self, order: TransferOrder):
        self._queue.append(order)

    def process_next_order(self) -> TransferOrder:
        if not self._queue:
            return None
        return self._queue.popleft()

    def __len__(self) -> int:
        return len(self._queue)


class PriorityTransferQueue:
    def __init__(self):
        self._heap = []

    def push_order(self, order: TransferOrder):
        heapq.heappush(self._heap, order)

    def pop_next_order(self) -> TransferOrder:
        if not self._heap:
            return None
        return heapq.heappop(self._heap)

    def __len__(self) -> int:
        return len(self._heap)


def filter_high_value_products(products: list[Product], min_price: float) -> list[str]:
    return [p.name for p in products if p.price > min_price]


def extract_unique_brands(products: list[Product]) -> set[str]:
    return {p.brand for p in products}


def build_sku_to_price_map(products: list[Product]) -> dict[str, float]:
    return {p.sku: p.price for p in products}


def _get_product_price(product: Product) -> float:
    return product.price


def sort_products_by_price(products: list[Product]) -> list[Product]:
    return sorted(products, key=_get_product_price)


def sort_products_by_name(products: list[Product]) -> list[Product]:
    return sorted(products, key=lambda p: p.name)


def sort_inventory_items_multi_criteria(items: list[InventoryItem]) -> list[InventoryItem]:
    return sorted(items, key=lambda item: (item.location_id, -item.available_quantity))


def calculate_order_priority(inventory_item: InventoryItem) -> int:
    if inventory_item.quantity == 0:
        return 1
    if inventory_item.is_low_stock:
        return 2
    return 3


def process_order_lifecycle(
    order: TransferOrder,
    source_inventory: dict,
    dest_inventory: dict,
    action: str,
    employee: Employee = None,
    authorizer: OrderActionAuthorizer = None,
) -> bool:
    """Validate the whole action before changing inventory, status or audit."""
    if action == "RESERVE":
        for item in order.items:
            inv = source_inventory.get(item.sku)
            if not inv or inv.available_quantity < item.quantity:
                return False

        for item in order.items:
            source_inventory[item.sku].reserve(item.quantity)
            if item.sku in dest_inventory:
                dest_inventory[item.sku].add_incoming(item.quantity)
        return True

    target_status = {"DISPATCH": "IN_TRANSIT", "DELIVER": "DELIVERED", "CANCEL": "CANCELLED"}.get(action)
    if target_status is None:
        return False
    if action == "CANCEL" and order.status != "PENDING":
        return False

    use_authorizer = employee is not None and authorizer is not None
    if use_authorizer:
        # Permission checks must not update the order or create an audit record.
        authorizer.validate_status_update(employee, target_status)

    # Build the complete update plan first. A missing or invalid later item
    # must not leave earlier inventory items partially dispatched or received.
    updates = []
    for item in order.items:
        amount = item.quantity
        if action in ("DISPATCH", "CANCEL"):
            source = source_inventory[item.sku]
            verb = "dispatch" if action == "DISPATCH" else "release"
            if amount <= 0 or amount > source.reserved:
                raise ValueError(f"Cannot {verb} {amount}. Reserved: {source.reserved}")
            update = source.dispatch_reserved if action == "DISPATCH" else source.release_reservation
            updates.append((update, amount))

        if action in ("DELIVER", "CANCEL") and item.sku in dest_inventory:
            destination = dest_inventory[item.sku]
            verb = "receive" if action == "DELIVER" else "reduce incoming by"
            if amount <= 0 or amount > destination.incoming:
                raise ValueError(f"Cannot {verb} {amount}. Incoming: {destination.incoming}")
            update = destination.receive_incoming if action == "DELIVER" else destination.reduce_incoming
            updates.append((update, amount))

    for update, amount in updates:
        update(amount)

    # All inventory checks succeeded; only now commit the order and its audit.
    if use_authorizer:
        authorizer.authorize_and_update_status(order, employee, target_status)
    else:
        order.status = target_status
    return True


def validate_employees_integrity(
    orders: list[TransferOrder],
    employees_catalog: dict[str, Employee],
) -> tuple[bool, list[str]]:
    """Business logic that validates that orders reference valid, active employees."""
    errors = []
    for order in orders:
        emp_id = order.handled_by_employee_id
        if emp_id is not None:
            if emp_id not in employees_catalog:
                errors.append(
                    f"Integrity Error: Order {order.order_id!r} references unknown employee {emp_id!r}."
                )
            elif not employees_catalog[emp_id].is_active:
                errors.append(
                    f"Integrity Error: Order {order.order_id!r} references inactive employee {emp_id!r}."
                )
    return len(errors) == 0, errors
