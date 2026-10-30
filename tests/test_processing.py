"""Order lifecycle failures must leave inventory, order and audit unchanged."""

import pytest

from pypharm.models import Employee, InventoryItem, OrderActionAuthorizer, StandardProduct, TransferOrder
from pypharm.processing import process_order_lifecycle


@pytest.fixture
def shipment():
    order = TransferOrder("ORD-1", "WH-1", "STORE-1", 1, handled_by_employee_id="EMP-OLD")
    source, destination = {}, {}
    for sku, amount in [("SKU-A", 2), ("SKU-B", 3)]:
        product = StandardProduct(sku, sku, "PyPharm", 10.0, 1.0)
        order.add_item(sku, amount)
        source[sku] = InventoryItem(product, "WH-1", 10, 0)
        destination[sku] = InventoryItem(product, "STORE-1", 1, 0)
        source[sku].reserve(amount)
        destination[sku].add_incoming(amount)
    manager = Employee("EMP-1", "Manager", "LOGISTICS_MANAGER")
    return order, source, destination, manager, OrderActionAuthorizer()


def shipment_state(order, source, destination, authorizer):
    return (
        order.status,
        order.handled_by_employee_id,
        {sku: (stock.quantity, stock.reserved, stock.incoming) for sku, stock in source.items()},
        {sku: (stock.quantity, stock.reserved, stock.incoming) for sku, stock in destination.items()},
        authorizer.action_history,
    )


@pytest.mark.parametrize("action", ["DISPATCH", "DELIVER", "CANCEL"])
def test_invalid_second_item_leaves_everything_unchanged(shipment, action):
    order, source, destination, manager, authorizer = shipment
    if action == "DISPATCH":
        source["SKU-B"].release_reservation(3)
    else:
        destination["SKU-B"].reduce_incoming(3)
        if action == "DELIVER":
            order.status = "IN_TRANSIT"
    before = shipment_state(order, source, destination, authorizer)

    with pytest.raises(ValueError):
        process_order_lifecycle(order, source, destination, action, manager, authorizer)

    assert shipment_state(order, source, destination, authorizer) == before


@pytest.mark.parametrize("action", ["DISPATCH", "CANCEL"])
def test_missing_second_source_leaves_everything_unchanged(shipment, action):
    order, source, destination, manager, authorizer = shipment
    del source["SKU-B"]
    before = shipment_state(order, source, destination, authorizer)

    with pytest.raises(KeyError, match="SKU-B"):
        process_order_lifecycle(order, source, destination, action, manager, authorizer)

    assert shipment_state(order, source, destination, authorizer) == before


@pytest.mark.parametrize("action", ["DISPATCH", "DELIVER", "CANCEL"])
def test_denied_lifecycle_action_leaves_everything_unchanged(shipment, action):
    order, source, destination, _, authorizer = shipment
    cashier = Employee("EMP-2", "Cashier", "CASHIER")
    if action == "DELIVER":
        order.status = "IN_TRANSIT"
    before = shipment_state(order, source, destination, authorizer)

    with pytest.raises(PermissionError):
        process_order_lifecycle(order, source, destination, action, cashier, authorizer)

    assert shipment_state(order, source, destination, authorizer) == before


def test_dispatch_and_delivery_update_all_inventory_and_audit(shipment):
    order, source, destination, manager, authorizer = shipment

    assert process_order_lifecycle(order, source, destination, "DISPATCH", manager, authorizer)
    assert order.status == "IN_TRANSIT"
    assert order.handled_by_employee_id == "EMP-1"
    assert [(stock.quantity, stock.reserved) for stock in source.values()] == [(8, 0), (7, 0)]
    assert [stock.incoming for stock in destination.values()] == [2, 3]

    assert process_order_lifecycle(order, source, destination, "DELIVER", manager, authorizer)
    assert order.status == "DELIVERED"
    assert [(stock.quantity, stock.incoming) for stock in destination.values()] == [(3, 0), (4, 0)]
    assert [(entry["old_status"], entry["new_status"]) for entry in authorizer.action_history] == [
        ("PENDING", "IN_TRANSIT"), ("IN_TRANSIT", "DELIVERED")
    ]


def test_cancel_releases_all_reservations_and_records_cancel_permission(shipment):
    order, source, destination, manager, authorizer = shipment

    assert process_order_lifecycle(order, source, destination, "CANCEL", manager, authorizer)

    assert order.status == "CANCELLED"
    assert [(stock.quantity, stock.reserved) for stock in source.values()] == [(10, 0), (10, 0)]
    assert [(stock.quantity, stock.incoming) for stock in destination.values()] == [(1, 0), (1, 0)]
    assert len(authorizer.action_history) == 1
    assert authorizer.action_history[0]["action"] == "CANCEL_ORDER"


@pytest.mark.parametrize("action", ["DISPATCH", "DELIVER", "CANCEL"])
def test_inventory_failure_without_authorizer_does_not_change_status(shipment, action):
    order, source, destination, _, authorizer = shipment
    if action == "DISPATCH":
        source["SKU-B"].release_reservation(3)
    else:
        destination["SKU-B"].reduce_incoming(3)
        if action == "DELIVER":
            order.status = "IN_TRANSIT"
    before = shipment_state(order, source, destination, authorizer)

    with pytest.raises(ValueError):
        process_order_lifecycle(order, source, destination, action)

    assert shipment_state(order, source, destination, authorizer) == before
