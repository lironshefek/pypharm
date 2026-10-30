"""
Shipment approval queue shared by several approver threads.

The shared business resource is the queue of transfer orders waiting for
approval. Approving an order is a check-then-update sequence:

    1. take the next order from the queue
    2. check that it is still PENDING
    3. move it to IN_TRANSIT and record the approval

The same order can be queued more than once (for example, when two branch
managers request the same shipment). Without a lock, two approvers can both
see the order as PENDING before either of them updates it - the order is then
approved twice and counted twice in the approval log. One Lock protects the
whole sequence, so only one approver can run it at a time.

Slow work such as a weather check must happen outside the locked section.
"""

import logging
import threading
import time
from collections import deque

from .models import TransferOrder

logger = logging.getLogger(__name__)


class ApprovalQueue:
    """FIFO queue of orders waiting for shipment approval, safe for several threads."""

    def __init__(self, orders=()):
        self._queue = deque(orders)
        self._lock = threading.Lock()
        self._approval_log: list[tuple[str, str]] = []

    def submit(self, order: TransferOrder) -> None:
        """Add an order to the end of the approval queue."""
        with self._lock:
            self._queue.append(order)

    def approve_next(self, approver: str) -> TransferOrder | None:
        """
        Approve the next PENDING order in the queue.

        Orders that are no longer PENDING (already approved or cancelled) are
        dropped from the queue without a second approval.

        Returns:
            The approved order, or None when no order is left to approve.
        """
        with self._lock:
            while self._queue:
                order = self._queue.popleft()
                if order.status != "PENDING":
                    logger.info(f"{approver} skipped {order.order_id}: already {order.status}")
                    continue
                order.status = "IN_TRANSIT"
                self._approval_log.append((order.order_id, approver))
                return order
            return None

    @property
    def approved_count(self) -> int:
        with self._lock:
            return len(self._approval_log)

    @property
    def approval_log(self) -> list[tuple[str, str]]:
        """Copy of the (order_id, approver) records, in approval order."""
        with self._lock:
            return list(self._approval_log)

    def __len__(self) -> int:
        with self._lock:
            return len(self._queue)


def approval_worker(queue: ApprovalQueue, approver: str, handling_time: float = 0.0) -> None:
    """
    Approve orders from the shared queue until it is empty.

    handling_time simulates the paperwork after each approval. It runs outside
    the lock, so other approvers can keep working in the meantime.
    """
    while True:
        order = queue.approve_next(approver)
        if order is None:
            break
        logger.info(f"{approver} approved {order.order_id}")
        time.sleep(handling_time)


def run_approvers(queue: ApprovalQueue, approvers: list, handling_time: float = 0.0) -> ApprovalQueue:
    """
    Run one thread per approver on the same queue and wait for all of them.

    All threads are started before any join(), so they work at the same time.
    """
    threads = [
        threading.Thread(target=approval_worker, args=(queue, approver, handling_time))
        for approver in approvers
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return queue
