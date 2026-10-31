"""
Shipment approval queue shared by several manager threads.

The shared business resource is the queue of transfer orders waiting for
approval. Every order enters the queue with the weather risk at its
destination and the roles allowed to approve it (NORMAL: warehouse or
logistics manager, DANGER: logistics manager only, UNKNOWN: nobody).

Managers go over the same pending orders at the same time and try to approve
them. Approving an order is a check-then-update sequence:

    1. is the order still PENDING?
    2. may this manager's role approve this risk level?
    3. move it to IN_TRANSIT and record who approved it

Without a lock, two managers can both see the same order as PENDING before
either of them updates it - both approve, and the order is approved twice.

Every order has its own Lock, which protects that sequence for that order:
two managers on the same order take turns, so only the first allowed one
approves and the other is refused. Managers working on different orders do
not wait for each other.

A separate short lock protects only the shared statistics (the approval log
and the refusal counters), which every manager writes to.

The weather check is a network call, so it is done before the order enters
the queue - never inside a locked section.
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

    # Risk recorded when the weather check failed; such an order may be re-checked
    UNKNOWN_RISK = "UNKNOWN"

    def __init__(self, authorizer: OrderActionAuthorizer = None):
        self._authorizer = authorizer or OrderActionAuthorizer()
        self._entries: dict[str, dict] = {}
        self._stats_lock = threading.Lock()
        self._approval_log: list[tuple[str, str, str]] = []
        self._approval_records: dict[str, dict] = {}
        self._refusals = {self.ALREADY_HANDLED: 0, self.NOT_AUTHORIZED: 0}

    def submit(
        self,
        order: TransferOrder,
        risk_level: str,
        required_roles: list,
        employees_catalog: dict | None = None,
    ) -> None:
        """
        Add an order with its weather risk and the roles allowed to approve it.

        An order already in the queue is rejected - unless its weather check
        failed (UNKNOWN) and it is still PENDING: then this is the re-check,
        and the order gets its real risk and approvers in place.

        Re-checks must use the original order object and destination. The
        employee catalog, when supplied, is checked at approval time so the
        audit records the assignment that actually preceded the approval.

        Orders are submitted before the managers of that round start working.
        """
        self.validate_submission(order)
        entry = self._entries.get(order.order_id)
        if entry is not None:
            with entry["lock"]:
                entry["risk_level"] = risk_level
                entry["required_roles"] = set(required_roles)
                if employees_catalog is not None:
                    entry["employees_catalog"] = employees_catalog
            return
        self._entries[order.order_id] = {
            "order": order,
            "destination_id": order.to_location_id,
            "risk_level": risk_level,
            "required_roles": set(required_roles),
            "employees_catalog": employees_catalog,
            # Approval replaces the order's handler, so keep who was assigned before it
            "assigned_employee_id": order.handled_by_employee_id,
            "lock": threading.Lock(),
        }

    def validate_submission(self, order: TransferOrder) -> None:
        """Raise ValueError if the order cannot enter the queue. Changes nothing."""
        entry = self._entries.get(order.order_id)
        if entry is not None:
            self._validate_queued_order(order, entry)
            if entry["risk_level"] != self.UNKNOWN_RISK:
                raise ValueError(f"Order {order.order_id} is already waiting for approval")
        if order.status != "PENDING":
            raise ValueError(f"Only PENDING orders can wait for approval, {order.order_id} is {order.status}")

    @staticmethod
    def _validate_queued_order(order: TransferOrder, entry: dict) -> None:
        """Keep cached weather tied to the exact order and destination checked."""
        if order is not entry["order"]:
            raise ValueError(f"Order {order.order_id} must use the same object already in the approval queue")
        if order.to_location_id != entry["destination_id"]:
            raise ValueError(f"Order {order.order_id} destination changed after it entered the approval queue")

    def risk_by_order(self) -> dict[str, str]:
        """Weather risk level recorded for every order in the queue."""
        return {order_id: entry["risk_level"] for order_id, entry in self._entries.items()}

    def assigned_employee_by_order(self) -> dict[str, str | None]:
        """Employee each order was assigned to when it entered the queue."""
        return {order_id: entry["assigned_employee_id"] for order_id, entry in self._entries.items()}

    def pending_ids(self) -> list[str]:
        """Order ids still waiting, in arrival order."""
        return [order_id for order_id, entry in self._entries.items() if entry["order"].status == "PENDING"]

    def try_approve(self, order_id: str, manager: Employee) -> str:
        """
        Approve the order if it is still PENDING and the manager may approve its risk level.

        Only this order's lock is held, so approvals of other orders run at the same time.

        Returns:
            APPROVED, ALREADY_HANDLED or NOT_AUTHORIZED.
        """
        entry = self._entries.get(order_id)
        if entry is None:
            raise ValueError(f"Order {order_id} is not in the approval queue")

        approval_record = None
        with entry["lock"]:
            order = entry["order"]
            self._validate_queued_order(order, entry)
            risk_level = entry["risk_level"]
            if order.status != "PENDING":
                result = self.ALREADY_HANDLED
            elif manager.role not in entry["required_roles"]:
                result = self.NOT_AUTHORIZED
            else:
                assigned_employee_id = order.handled_by_employee_id
                employees_catalog = entry["employees_catalog"]
                if assigned_employee_id is None:
                    integrity_issue = False
                elif employees_catalog is None:
                    integrity_issue = None
                else:
                    employee = employees_catalog.get(assigned_employee_id)
                    integrity_issue = employee is None or not employee.is_active
                try:
                    # Checks the employee is active and allowed to update statuses, then updates.
                    self._authorizer.authorize_and_update_status(order, manager, "IN_TRANSIT")
                    result = self.APPROVED
                    approval_record = {
                        "assigned_employee_id": assigned_employee_id,
                        "integrity_issue": integrity_issue,
                    }
                except PermissionError:
                    result = self.NOT_AUTHORIZED

        self._record(result, order_id, manager, risk_level, approval_record)
        return result

    def _record(
        self,
        result: str,
        order_id: str,
        manager: Employee,
        risk_level: str,
        approval_record: dict | None,
    ) -> None:
        """Update the approval log, historical records and counters together."""
        with self._stats_lock:
            if result == self.APPROVED:
                assert approval_record is not None
                self._approval_log.append((order_id, manager.name, risk_level))
                self._approval_records[order_id] = approval_record
            else:
                self._refusals[result] += 1
        if result != self.APPROVED:
            logger.info(f"{manager.name} cannot approve {order_id}: {result}")

    @property
    def approved_count(self) -> int:
        with self._stats_lock:
            return len(self._approval_log)

    @property
    def refusals(self) -> dict[str, int]:
        """How many approval attempts were refused, by reason."""
        with self._stats_lock:
            return dict(self._refusals)

    @property
    def approval_log(self) -> list[tuple[str, str, str]]:
        """Copy of the (order_id, manager name, risk level) records, in approval order."""
        with self._stats_lock:
            return list(self._approval_log)

    @property
    def approval_records(self) -> dict[str, dict]:
        """Copies of successful approvals' assignment and integrity snapshots.

        An unknown integrity result (None) means an assigned employee could
        not be checked because no catalog was supplied. Later assignment or
        employee-status changes do not rewrite these historical facts.
        """
        with self._stats_lock:
            return {order_id: dict(record) for order_id, record in self._approval_records.items()}

    def __len__(self) -> int:
        """Number of orders still waiting for approval."""
        return len(self.pending_ids())


def queue_orders_for_approval(
    queue: ApprovalQueue,
    orders: list,
    locations_by_id: dict,
    weather_service,
    employees_catalog: dict = None,
) -> None:
    """
    Check the weather at each order's destination and put the order in the approval queue.

    Runs before any manager thread starts, so the network calls stay outside the locks.
    When the weather check fails the risk is UNKNOWN and nobody may approve the order.

    All or nothing: every order is validated first (known destination, PENDING,
    not queued twice). If one order is invalid, no order is queued and no
    weather is requested, so a bad record never leaves a partial batch behind.
    """
    seen_ids = set()
    for order in orders:
        if order.to_location_id not in locations_by_id:
            raise ValueError(f"Order {order.order_id} has unknown destination {order.to_location_id!r}")
        if order.order_id in seen_ids:
            raise ValueError(f"Order {order.order_id} appears twice in the batch")
        queue.validate_submission(order)
        seen_ids.add(order.order_id)

    for order in orders:
        location = locations_by_id[order.to_location_id]
        weather = weather_service.check_and_classify_for_order(location, order, employees_catalog)
        queue.submit(order, weather["risk_level"], weather["required_roles"], employees_catalog)


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
