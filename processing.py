"""
processing.py - Data structures and collection processing.
List, tuple, set, dict, deque, heapq, comprehensions, sorting, and business logic.
"""

from collections import deque
import heapq
from typing import List, Dict, Set, Tuple
from .models import Product, Location, InventoryItem, TransferOrder

def process_shipment_manifest(manifest_records: List[Tuple]) -> dict:
    summary = {}
    for record in manifest_records:
        order_id, destination, *skus = record
        summary[order_id] = {
            "destination": destination,
            "items_count": len(skus),
            "skus": skus
        }
    return summary


class LocationCategoryTracker:
    def __init__(self):
        self.active_locations: Set[str] = set()
        self.refrigerated_locations: Set[str] = set()

    def register_location(self, location_id: str, is_refrigerated: bool = False):
        self.active_locations.add(location_id)
        if is_refrigerated:
            self.refrigerated_locations.add(location_id)

    def deactivate_location(self, location_id: str):
        self.active_locations.discard(location_id)
        if location_id in self.refrigerated_locations:
            self.refrigerated_locations.remove(location_id)

    def check_location_exists(self, location_id: str) -> bool:
        return location_id in self.active_locations

    def get_non_refrigerated_locations(self) -> Set[str]:
        return self.active_locations - self.refrigerated_locations

    def get_common_locations(self, other_set: Set[str]) -> Set[str]:
        return self.active_locations.intersection(other_set)

    def combine_locations(self, other_set: Set[str]) -> Set[str]:
        return self.active_locations | other_set


class InventoryRegistry:
    def __init__(self):
        self.products_by_sku: Dict[str, Product] = {}
        self.inventory_by_location: Dict[str, List[InventoryItem]] = {}

    def add_product(self, product: Product, overwrite: bool = False):
        if product.sku in self.products_by_sku and not overwrite:
            raise ValueError(f"Product with SKU {product.sku!r} already exists in registry.")
        self.products_by_sku[product.sku] = product

    def get_product(self, sku: str) -> Product:
        return self.products_by_sku.get(sku, None)

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

    def __len__(self):
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

    def __len__(self):
        return len(self._heap)


def filter_high_value_products(products: List[Product], min_price: float) -> List[str]:
    return [p.name for p in products if p.price > min_price]


def extract_unique_brands(products: List[Product]) -> Set[str]:
    return {p.brand for p in products}


def build_sku_to_price_map(products: List[Product]) -> Dict[str, float]:
    return {p.sku: p.price for p in products}


def _get_product_price(product: Product) -> float:
    return product.price


def sort_products_by_price(products: List[Product]) -> List[Product]:
    return sorted(products, key=_get_product_price)


def sort_products_by_name(products: List[Product]) -> List[Product]:
    return sorted(products, key=lambda p: p.name)


def sort_inventory_items_multi_criteria(items: List[InventoryItem]) -> List[InventoryItem]:
    return sorted(items, key=lambda item: (item.location_id, -item.available_quantity))


def calculate_order_priority(inventory_item: InventoryItem) -> int:
    if inventory_item.quantity == 0:
        return 1
    if inventory_item.is_low_stock:
        return 2
    return 3


def process_order_lifecycle(order: TransferOrder, source_inventory: dict, dest_inventory: dict, action: str) -> bool:
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

    elif action == "DISPATCH":
        for item in order.items:
            source_inventory[item.sku].dispatch_reserved(item.quantity)
        order.status = "IN_TRANSIT"
        return True

    elif action == "DELIVER":
        for item in order.items:
            if item.sku in dest_inventory:
                dest_inventory[item.sku].receive_incoming(item.quantity)
        order.status = "DELIVERED"
        return True

    elif action == "CANCEL":
        if order.status == "PENDING":
            for item in order.items:
                source_inventory[item.sku].release_reservation(item.quantity)
                if item.sku in dest_inventory:
                    dest_inventory[item.sku].reduce_incoming(item.quantity)
        order.status = "CANCELLED"
        return True

    return False