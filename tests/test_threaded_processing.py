"""Tests for the shipment approval queue shared by several manager threads."""

import pytest

from pypharm import ApprovalQueue, TransferOrder, run_approvers


def make_orders(count):
    return [
        TransferOrder(f"ORD-{i:03d}", "WH-CENTRAL", "STORE-TLV", priority=1)
        for i in range(1, count + 1)
    ]


@pytest.fixture
def orders():
    return make_orders(6)


def test_order_already_waiting_cannot_be_submitted_again(orders):
    queue = ApprovalQueue(orders)

    with pytest.raises(ValueError, match="ORD-001 is already waiting"):
        queue.submit(orders[0])
    assert len(queue) == 6


def test_second_approval_of_the_same_order_is_refused(orders):
    queue = ApprovalQueue(orders)

    assert queue.try_approve("ORD-001", "Aya") is True
    assert queue.try_approve("ORD-001", "noa") is False

    assert orders[0].status == "IN_TRANSIT"
    assert queue.approval_log == [("ORD-001", "Aya")]
    assert queue.refused_attempts == 1


def test_many_managers_racing_for_one_order_approve_it_once():
    order = TransferOrder("ORD-777", "WH-CENTRAL", "STORE-HAIFA", priority=1)
    queue = ApprovalQueue([order])

    run_approvers(queue, [f"manager-{i}" for i in range(10)], review_time=0.001)

    assert queue.approved_count == 1
    assert queue.refused_attempts == 9
    assert order.status == "IN_TRANSIT"


@pytest.mark.parametrize("managers", [["Aya"], ["Aya", "noa"], ["Aya", "noa", "Ruth", "Liron"]])
def test_every_order_is_approved_exactly_once(orders, managers):
    queue = run_approvers(ApprovalQueue(orders), managers, review_time=0.001)

    assert queue.approved_count == 6
    assert sorted(order_id for order_id, _ in queue.approval_log) == [o.order_id for o in orders]
    assert queue.refused_attempts == 6 * (len(managers) - 1)
    assert all(order.status == "IN_TRANSIT" for order in orders)
    assert len(queue) == 0


def test_many_managers_on_many_orders():
    orders = make_orders(200)

    queue = run_approvers(ApprovalQueue(orders), [f"manager-{i}" for i in range(8)])

    assert queue.approved_count == 200
    assert queue.refused_attempts == 200 * 7
    assert all(order.status == "IN_TRANSIT" for order in orders)
    assert len(queue) == 0
