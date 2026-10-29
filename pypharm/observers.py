"""Observers for dangerous-weather approval events."""

import logging
from dataclasses import dataclass

from .processing import validate_employees_integrity

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApprovalRequiredEvent:
    order_id: str | None
    temperature: float
    risk_level: str
    employee_id: str | None = None
    order: object | None = None


class ApprovalEventPublisher:
    """Notify registered observers when a dangerous order needs approval."""

    def __init__(self, observers=()):
        self._observers = list(observers)

    def subscribe(self, observer) -> None:
        if not callable(getattr(observer, "update", None)):
            raise TypeError("observer must define an update(event) method")
        self._observers.append(observer)

    def publish(self, event: ApprovalRequiredEvent) -> None:
        for observer in tuple(self._observers):
            observer.update(event)


class AuditLogObserver:
    """Write dangerous-weather approval requests to the application log."""

    def update(self, event: ApprovalRequiredEvent) -> None:
        logger.warning(
            "Approval required: order=%s risk=%s temperature=%sC employee=%s",
            event.order_id or "unknown",
            event.risk_level,
            event.temperature,
            event.employee_id or "unassigned",
        )


class IntegrityAlertObserver:
    """Check the order's assigned employee and log integrity problems."""

    def __init__(self, employees_catalog: dict | None = None):
        self.employees_catalog = employees_catalog or {}
        self.alerts: list[str] = []

    def update(self, event: ApprovalRequiredEvent) -> None:
        if event.order is None:
            return
        is_valid, errors = validate_employees_integrity(
            [event.order], self.employees_catalog
        )
        if not is_valid:
            self.alerts.extend(errors)
            for error in errors:
                logger.error("%s", error)
