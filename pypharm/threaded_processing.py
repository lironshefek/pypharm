"""
Shipment approval queue shared by several manager threads.

The shared business resource is the queue of transfer orders waiting for
approval. Every order enters the queue with the weather risk at its
destination and the roles allowed to approve it (NORMAL: warehouse or
logistics manager, DANGER: logistics manager only, UNKNOWN: nobody).

Managers go over the same pending orders at the same time and try to approve
them. Approving is a check-then-update sequence:

    1. is the order still PENDING?
    2. may this manager's role approve this risk level?
    3. move it to IN_TRANSIT and record who approved it

Without a lock, two managers can both see the same order as PENDING before
either of them updates it - both approve, and the order is approved twice and
recorded twice. One Lock protects the whole sequence, so only the first
allowed manager approves; anyone after her is refused.

The weather check is a network call, so it is done before the order enters
the queue - never inside the locked section.
"""

import logging
import threading
import time

from .models import Employee, OrderActionAuthorizer, TransferOrder

logger = logging.getLogger(__name__)


class ApprovalQueue:
    """Orders waiting for shipment approval, shared by several managers."""

    APPROVED = "APPROVED"
    ALREADY_HANDLED = "ALREADY_HANDLED"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"

    def __init__(self, authorizer: OrderActionAuthorizer = None):
        self._authorizer = authorizer or OrderActionAuthorizer()
        self._pending: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._approval_log: list[tuple[str, str, str]] = []
        self._refusals = {self.ALREADY_HANDLED: 0, self.NOT_AUTHORIZED: 0}

    def submit(self, order: TransferOrder, risk_level: str, required_roles: list) -> None:
        """
        Add an order with its weather risk and the roles allowed to approve it.
        An order that is already waiting is rejected.
        """
        with self._lock:
            if order.order_id in self._pending:
                raise ValueError(f"Order {order.order_id} is already waiting for approval")
            if order.status != "PENDING":
                raise ValueError(f"Only PENDING orders can wait for approval, {order.order_id} is {order.status}")
            self._pending[order.order_id] = {
                "order": order,
                "risk_level": risk_level,
                "required_roles": set(required_roles),
            }

    def pending_ids(self) -> list[str]:
        """Snapshot of the order ids still waiting, in arrival order."""
        with self._lock:
            return list(self._pending)

    def try_approve(self, order_id: str, manager: Employee) -> str:
        """
        Approve the order if it is still PENDING and the manager may approve its risk level.

        Returns:
            APPROVED, ALREADY_HANDLED or NOT_AUTHORIZED.
        """
        with self._lock:
            entry = self._pending.get(order_id)
            if entry is None:
                return self._refuse(self.ALREADY_HANDLED, order_id, manager)

            if manager.role not in entry["required_roles"]:
                return self._refuse(self.NOT_AUTHORIZED, order_id, manager)
            try:
                # Checks the employee is active and allowed to update statuses, then updates.
                self._authorizer.authorize_and_update_status(entry["order"], manager, "IN_TRANSIT")
            except PermissionError:
                return self._refuse(self.NOT_AUTHORIZED, order_id, manager)

            del self._pending[order_id]
            self._approval_log.append((order_id, manager.name, entry["risk_level"]))
            return self.APPROVED

    def _refuse(self, reason: str, order_id: str, manager: Employee) -> str:
        """Count a refused attempt. Called only while holding the lock."""
        self._refusals[reason] += 1
        logger.info(f"{manager.name} cannot approve {order_id}: {reason}")
        return reason

    @property
    def approved_count(self) -> int:
        with self._lock:
            return len(self._approval_log)

    @property
    def refusals(self) -> dict[str, int]:
        """How many approval attempts were refused, by reason."""
        with self._lock:
            return dict(self._refusals)

    @property
    def approval_log(self) -> list[tuple[str, str, str]]:
        """Copy of the (order_id, manager name, risk level) records, in approval order."""
        with self._lock:
            return list(self._approval_log)

    def __len__(self) -> int:
        with self._lock:
            return len(self._pending)


def queue_orders_for_approval(
    queue: ApprovalQueue,
    orders: list,
    locations_by_id: dict,
    weather_service,
    employees_catalog: dict = None,
) -> None:
    """
    Check the weather at each order's destination and put the order in the approval queue.

    Runs before any manager thread starts, so the network calls stay outside the lock.
    When the weather check fails the risk is UNKNOWN and nobody may approve the order.
    """
    for order in orders:
        location = locations_by_id.get(order.to_location_id)
        if location is None:
            raise ValueError(f"Order {order.order_id} has unknown destination {order.to_location_id!r}")
        weather = weather_service.check_and_classify_for_order(location, order, employees_catalog)
        queue.submit(order, weather["risk_level"], weather["required_roles"])


def approval_worker(queue: ApprovalQueue, manager: Employee, order_ids: list, review_time: float = 0.0) -> None:
    """
    One manager goes over the list of pending orders, reviews each one and tries to approve it.

    review_time simulates reading the order before deciding. It runs outside
    the lock, so the other managers keep working at the same time.
    """
    for order_id in order_ids:
        time.sleep(review_time)
        if queue.try_approve(order_id, manager) == ApprovalQueue.APPROVED:
            logger.info(f"{manager.name} approved {order_id}")


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
