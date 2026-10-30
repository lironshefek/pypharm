"""
Shipment approval queue shared by several manager threads.

The shared business resource is the queue of transfer orders waiting for
approval. Every manager goes over the same pending orders, reviews each one
and tries to approve it. Approving is a check-then-update sequence:

    1. check that the order is still PENDING
    2. move it to IN_TRANSIT and record who approved it

Without a lock, two managers can both see the same order as PENDING before
either of them updates it - both approve, and the order is approved twice and
recorded twice in the approval log. One Lock protects the whole sequence, so
only the first manager approves; the second one gets a refusal.

Slow work (reviewing the order, a weather check) happens outside the lock.
"""

import logging
import threading
import time

from .models import TransferOrder

logger = logging.getLogger(__name__)


class ApprovalQueue:
    """Orders waiting for shipment approval, shared by several managers."""

    def __init__(self, orders=()):
        self._pending: dict[str, TransferOrder] = {}
        self._lock = threading.Lock()
        self._approval_log: list[tuple[str, str]] = []
        self._refused_attempts = 0
        for order in orders:
            self.submit(order)

    def submit(self, order: TransferOrder) -> None:
        """Add an order to the queue. An order that is already waiting is rejected."""
        with self._lock:
            if order.order_id in self._pending:
                raise ValueError(f"Order {order.order_id} is already waiting for approval")
            if order.status != "PENDING":
                raise ValueError(f"Only PENDING orders can wait for approval, {order.order_id} is {order.status}")
            self._pending[order.order_id] = order

    def pending_ids(self) -> list[str]:
        """Snapshot of the order ids still waiting, in arrival order."""
        with self._lock:
            return list(self._pending)

    def try_approve(self, order_id: str, manager: str) -> bool:
        """
        Approve the order if it is still PENDING.

        Returns:
            True if this manager approved it, False if it was already handled.
        """
        with self._lock:
            order = self._pending.get(order_id)
            if order is None or order.status != "PENDING":
                self._refused_attempts += 1
                logger.info(f"{manager} cannot approve {order_id}: already handled")
                return False
            order.status = "IN_TRANSIT"
            del self._pending[order_id]
            self._approval_log.append((order_id, manager))
            return True

    @property
    def approved_count(self) -> int:
        with self._lock:
            return len(self._approval_log)

    @property
    def refused_attempts(self) -> int:
        """How many times a manager tried to approve an order that was already approved."""
        with self._lock:
            return self._refused_attempts

    @property
    def approval_log(self) -> list[tuple[str, str]]:
        """Copy of the (order_id, manager) records, in approval order."""
        with self._lock:
            return list(self._approval_log)

    def __len__(self) -> int:
        with self._lock:
            return len(self._pending)


def approval_worker(queue: ApprovalQueue, manager: str, order_ids: list, review_time: float = 0.0) -> None:
    """
    One manager goes over the list of pending orders, reviews each one and tries to approve it.

    review_time simulates reading the order before deciding. It runs outside
    the lock, so the other managers keep working at the same time.
    """
    for order_id in order_ids:
        time.sleep(review_time)
        if queue.try_approve(order_id, manager):
            logger.info(f"{manager} approved {order_id}")


def run_approvers(queue: ApprovalQueue, managers: list, review_time: float = 0.0) -> ApprovalQueue:
    """
    Run one thread per manager on the same queue and wait for all of them.

    Every manager gets the same list of pending orders, so they compete for
    the same orders. All threads are started before any join(), so they work
    at the same time.
    """
    order_ids = queue.pending_ids()
    threads = [
        threading.Thread(target=approval_worker, args=(queue, manager, order_ids, review_time))
        for manager in managers
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return queue
