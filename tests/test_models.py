"""
tests/test_models.py - Stage 1 behaviour regression tests.
Expected values come from the business rules, not from re-running the code.
"""

import pytest

from pypharm.models import (
    Employee,
    InventoryItem,
    OrderActionAuthorizer,
    PerishableProduct,
    StandardProduct,
    TransferOrder,
)


@pytest.fixture
def refrigerated_cream():
    return PerishableProduct(
        sku="CRM-001",
        name="Night Cream",
        brand="PyPharm",
        price=59.9,
        expiry_date="2030-01-01",
        requires_refrigeration=True,
    )


@pytest.fixture
def perfume():
    return StandardProduct(
        sku="PRF-001", name="Perfume", brand="PyPharm", price=199.0, weight_kg=1.5
    )


@pytest.fixture
def stock(refrigerated_cream):
    return InventoryItem(
        product=refrigerated_cream, location_id="WH-01", quantity=10, min_threshold=2
    )


@pytest.fixture
def pending_order():
    return TransferOrder(
        order_id="ORD-001", from_location_id="WH-01", to_location_id="BR-01", priority=1
    )


# --- Products: polymorphic handling cost ---

def test_refrigerated_product_handling_cost(refrigerated_cream):
    # 3 units x (2.5 base + 5.0 refrigeration) = 22.5
    assert refrigerated_cream.calculate_handling_cost(3) == pytest.approx(22.5)


def test_standard_product_handling_cost_depends_on_weight(perfume):
    # 2 units x 1.5 kg x 3.0 per kg = 9.0
    assert perfume.calculate_handling_cost(2) == pytest.approx(9.0)


# --- Inventory: reserve and dispatch ---

def test_dispatch_reserved_units_leaves_the_warehouse(stock):
    stock.reserve(4)
    stock.dispatch_reserved(4)

    assert stock.quantity == 6
    assert stock.reserved == 0
    assert stock.available_quantity == 6


def test_reserve_more_than_available_is_rejected_without_change(stock):
    stock.reserve(8)

    with pytest.raises(ValueError):
        stock.reserve(3)

    assert stock.reserved == 8
    assert stock.available_quantity == 2


# --- Transfer order: invalid input ---

@pytest.mark.parametrize(
    "order_id, from_id, to_id, priority, status",
    [
        ("ORD-X", "WH-01", "WH-01", 1, "PENDING"),  # same source and destination
        ("ORD-X", "WH-01", "BR-01", 0, "PENDING"),  # priority must be >= 1
        ("ORD-X", "WH-01", "BR-01", 1, "LOST"),     # unknown status
        ("   ", "WH-01", "BR-01", 1, "PENDING"),    # empty order id
    ],
)
def test_invalid_transfer_order_is_rejected(order_id, from_id, to_id, priority, status):
    with pytest.raises(ValueError):
        TransferOrder(order_id, from_id, to_id, priority, status=status)


# --- Authorization: who may update an order status ---

@pytest.mark.parametrize("role", ["WAREHOUSE_WORKER", "WAREHOUSE_MANAGER", "LOGISTICS_MANAGER"])
def test_authorized_employee_updates_status_and_is_audited(pending_order, role):
    authorizer = OrderActionAuthorizer()
    employee = Employee("EMP-1", "Noa", role)

    authorizer.authorize_and_update_status(pending_order, employee, "IN_TRANSIT")

    assert pending_order.status == "IN_TRANSIT"
    assert pending_order.handled_by_employee_id == "EMP-1"
    assert len(authorizer.action_history) == 1
    assert authorizer.action_history[0]["old_status"] == "PENDING"


@pytest.mark.parametrize(
    "role, is_active",
    [
        ("CASHIER", True),             # role without permission
        ("LOGISTICS_MANAGER", False),  # permitted role but inactive
    ],
)
def test_unauthorized_employee_cannot_update_status(pending_order, role, is_active):
    authorizer = OrderActionAuthorizer()
    employee = Employee("EMP-2", "Dana", role, is_active=is_active)

    with pytest.raises(PermissionError):
        authorizer.authorize_and_update_status(pending_order, employee, "IN_TRANSIT")

    assert pending_order.status == "PENDING"
    assert authorizer.action_history == []


@pytest.mark.parametrize("role", ["WAREHOUSE_WORKER", "CASHIER"])
@pytest.mark.parametrize("new_status", ["CANCELLED", "cancelled", " CANCELLED "])
def test_cancellation_permission_applies_after_normalizing_status(pending_order, role, new_status):
    authorizer = OrderActionAuthorizer()
    employee = Employee("EMP-2", "Dana", role)
    pending_order.assign_employee("EMP-ORIGINAL")

    with pytest.raises(PermissionError):
        authorizer.authorize_and_update_status(pending_order, employee, new_status)

    assert pending_order.status == "PENDING"
    assert pending_order.handled_by_employee_id == "EMP-ORIGINAL"
    assert authorizer.action_history == []


@pytest.mark.parametrize("new_status", ["CANCELLED", "cancelled", " CANCELLED "])
def test_logistics_manager_cancellation_is_audited_with_canonical_status(pending_order, new_status):
    authorizer = OrderActionAuthorizer()
    employee = Employee("EMP-MANAGER", "Aya", "LOGISTICS_MANAGER")

    authorizer.authorize_and_update_status(pending_order, employee, new_status)

    assert pending_order.status == "CANCELLED"
    assert pending_order.handled_by_employee_id == "EMP-MANAGER"
    assert len(authorizer.action_history) == 1
    entry = authorizer.action_history[0]
    assert entry["action"] == "CANCEL_ORDER"
    assert entry["old_status"] == "PENDING"
    assert entry["new_status"] == "CANCELLED"


@pytest.mark.parametrize("new_status", ["LOST", " ", None])
def test_invalid_status_update_does_not_change_order_or_audit(pending_order, new_status):
    authorizer = OrderActionAuthorizer()
    employee = Employee("EMP-MANAGER", "Aya", "LOGISTICS_MANAGER")
    pending_order.assign_employee("EMP-ORIGINAL")

    with pytest.raises(ValueError):
        authorizer.authorize_and_update_status(pending_order, employee, new_status)

    assert pending_order.status == "PENDING"
    assert pending_order.handled_by_employee_id == "EMP-ORIGINAL"
    assert authorizer.action_history == []


def test_status_update_validation_returns_canonical_status_without_committing():
    authorizer = OrderActionAuthorizer()
    employee = Employee("EMP-MANAGER", "Aya", "LOGISTICS_MANAGER")

    assert authorizer.validate_status_update(employee, " cancelled ") == "CANCELLED"
    assert authorizer.action_history == []
