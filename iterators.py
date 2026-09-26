"""
iterators.py - Part D: Custom Iterables, Iterators, and Generators.
OrderRegistry + OrderIterator for traversing transfer orders.
urgent_orders_generator for yielding open orders (lazy evaluation).
"""

from models import TransferOrder


class OrderIterator:
    """Iterator for OrderRegistry: tracks position and state during traversal."""

    def __init__(self, orders: list):
        self._orders = orders
        self._index = 0

    def __iter__(self):
        return self

    def __next__(self) -> TransferOrder:
        if self._index >= len(self._orders):
            raise StopIteration
        order = self._orders[self._index]
        self._index += 1
        return order


class OrderRegistry:
    """Iterable collection of transfer orders. Each iter() returns a fresh OrderIterator."""

    def __init__(self):
        self._orders = []

    def add_order(self, order: TransferOrder):
        if not isinstance(order, TransferOrder):
            raise ValueError(f"Expected TransferOrder, got: {type(order).__name__}")
        self._orders.append(order)

    def remove_order(self, order_id: str) -> bool:
        for order in self._orders:
            if order.order_id == order_id:
                self._orders.remove(order)
                return True
        return False

    def get_order(self, order_id: str) -> TransferOrder | None:
        for order in self._orders:
            if order.order_id == order_id:
                return order
        return None

    def count(self) -> int:
        return len(self._orders)

    def __iter__(self):
        """Return a fresh iterator for this registry."""
        return OrderIterator(list(self._orders))

    def __str__(self) -> str:
        return f"OrderRegistry with {len(self._orders)} orders"

    def __repr__(self) -> str:
        return f"OrderRegistry(orders_count={len(self._orders)})"


def open_orders_generator(registry: OrderRegistry):
    """
    Generator: yields open orders (PENDING or IN_TRANSIT) without loading all at once.
    Skips DELIVERED and CANCELLED orders.
    """
    for order in registry:
        if order.status not in ("DELIVERED", "CANCELLED"):
            yield order


def critical_priority_orders_pipeline(registry: OrderRegistry):
    """
    Lazy 3-stage pipeline for critical priority orders (no intermediate lists).
    Stage 1: Filter open orders (not DELIVERED/CANCELLED)
    Stage 2: Filter critical priority (priority = 1)
    Stage 3: Transform to summary dict
    """
    for order in registry:
        if order.status not in ("DELIVERED", "CANCELLED"):
            if order.priority == 1:
                yield {
                    "order_id": order.order_id,
                    "status": order.status,
                    "priority": order.priority,
                    "from_location": order.from_location_id,
                    "to_location": order.to_location_id,
                }
