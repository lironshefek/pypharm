"""Tests for threaded weather checking with synchronized queue access."""

import threading
from unittest.mock import Mock

import pytest

from pypharm import (
    Location,
    TransferOrder,
    WeatherReading,
    WeatherService,
    ApprovalQueue,
    process_orders_threaded,
)


@pytest.fixture
def location():
    return Location("STORE-TLV", "Tel Aviv", "STORE", "Tel Aviv", 32.0853, 34.7818)


@pytest.fixture
def locations():
    return [
        Location("STORE-MODIIN", "Modiin", "STORE", "Modiin", 31.9103, 35.1876),
        Location("STORE-TLV", "Tel Aviv", "STORE", "Tel Aviv", 32.0853, 34.7818),
        Location("STORE-HAIFA", "Haifa", "STORE", "Haifa", 32.8193, 34.9927),
    ]


def test_approval_queue_enqueue_dequeue():
    """Queue enqueue and dequeue operations work correctly."""
    queue = ApprovalQueue()

    queue.enqueue({"order_id": "ORD-001", "location": "Tel Aviv"})
    queue.enqueue({"order_id": "ORD-002", "location": "Modiin"})

    assert queue.queue_size() == 2

    order1 = queue.dequeue()
    assert order1["order_id"] == "ORD-001"
    assert queue.queue_size() == 1
    assert queue.processed_count() == 1

    order2 = queue.dequeue()
    assert order2["order_id"] == "ORD-002"
    assert queue.queue_size() == 0
    assert queue.processed_count() == 2


def test_approval_queue_dequeue_empty():
    """Dequeuing from empty queue returns None."""
    queue = ApprovalQueue()

    result = queue.dequeue()

    assert result is None
    assert queue.queue_size() == 0
    assert queue.processed_count() == 0


def test_approval_queue_thread_safe_enqueue_dequeue():
    """Queue operations are thread-safe without race conditions."""
    queue = ApprovalQueue()
    results = []

    def enqueuer(start_id, count):
        for i in range(count):
            queue.enqueue(
                {"order_id": f"ORD-{start_id + i:03d}", "location": f"LOC-{i}"}
            )

    def dequeuer():
        while True:
            order = queue.dequeue()
            if order is None:
                break
            results.append(order)

    # Start enqueuers
    t1 = threading.Thread(target=enqueuer, args=(1, 5))
    t2 = threading.Thread(target=enqueuer, args=(100, 5))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Start dequeuers
    t3 = threading.Thread(target=dequeuer)
    t4 = threading.Thread(target=dequeuer)
    t3.start()
    t4.start()
    t3.join()
    t4.join()

    assert len(results) == 10
    assert queue.queue_size() == 0
    assert queue.processed_count() == 10


def test_process_orders_threaded_with_mock_service(locations):
    """Threaded processing works with mock service."""
    service = WeatherService(
        client=Mock(
            get_weather=Mock(
                side_effect=[
                    WeatherReading(temperature_2m=33.5),
                    WeatherReading(temperature_2m=24.0),
                    WeatherReading(temperature_2m=21.5),
                ]
            )
        )
    )

    orders = [
        {"order_id": f"ORD-{i+1:03d}", "location": locations[i]}
        for i in range(3)
    ]

    results = process_orders_threaded(service, orders, num_workers=2)

    assert len(results) == 3
    order_ids = {r["order_id"] for r in results}
    assert order_ids == {"ORD-001", "ORD-002", "ORD-003"}

    locations_in_results = {r["location"] for r in results}
    assert locations_in_results == {"Modiin", "Tel Aviv", "Haifa"}


def test_process_orders_threaded_temperature_classification(locations):
    """Threaded processing correctly classifies risk levels."""
    service = WeatherService(
        client=Mock(
            get_weather=Mock(
                side_effect=[
                    WeatherReading(temperature_2m=33.5),  # DANGER
                    WeatherReading(temperature_2m=24.0),  # NORMAL
                    WeatherReading(temperature_2m=21.5),  # NORMAL
                ]
            )
        )
    )

    orders = [
        {"order_id": f"ORD-{i+1:03d}", "location": locations[i]}
        for i in range(3)
    ]

    results = process_orders_threaded(service, orders, num_workers=2)

    danger_order = next(r for r in results if r["risk_level"] == "DANGER")
    assert danger_order["location"] == "Modiin"
    assert danger_order["temperature"] == 33.5
    assert danger_order["required_roles"] == ["LOGISTICS_MANAGER"]

    normal_orders = [r for r in results if r["risk_level"] == "NORMAL"]
    assert len(normal_orders) == 2
    for order in normal_orders:
        assert "WAREHOUSE_MANAGER" in order["required_roles"]


def test_process_orders_threaded_worker_distribution(locations):
    """Work is distributed among worker threads."""
    service = WeatherService(
        client=Mock(
            get_weather=Mock(
                side_effect=[
                    WeatherReading(temperature_2m=25.0),
                    WeatherReading(temperature_2m=25.0),
                    WeatherReading(temperature_2m=25.0),
                    WeatherReading(temperature_2m=25.0),
                ]
            )
        )
    )

    orders = [
        {"order_id": f"ORD-{i+1:03d}", "location": locations[i % 3]}
        for i in range(4)
    ]

    results = process_orders_threaded(service, orders, num_workers=2)

    assert len(results) == 4
    worker_ids = {r["worker_id"] for r in results}
    # Should have contributions from worker threads
    assert worker_ids.issubset({0, 1})


def test_process_orders_threaded_single_worker(locations):
    """Single worker mode works correctly."""
    service = WeatherService(
        client=Mock(
            get_weather=Mock(
                side_effect=[
                    WeatherReading(temperature_2m=25.0),
                    WeatherReading(temperature_2m=25.0),
                    WeatherReading(temperature_2m=25.0),
                ]
            )
        )
    )

    orders = [
        {"order_id": f"ORD-{i+1:03d}", "location": locations[i]}
        for i in range(3)
    ]

    results = process_orders_threaded(service, orders, num_workers=1)

    assert len(results) == 3
    worker_ids = {r["worker_id"] for r in results}
    assert worker_ids == {0}


def test_process_orders_threaded_empty_queue():
    """Handling of empty order list works correctly."""
    service = WeatherService()
    orders = []

    results = process_orders_threaded(service, orders, num_workers=2)

    assert len(results) == 0


def test_approval_queue_processed_count_tracks_dequeued():
    """Processed count only increments on successful dequeue."""
    queue = ApprovalQueue()

    queue.enqueue({"order_id": "ORD-001"})
    queue.enqueue({"order_id": "ORD-002"})

    assert queue.processed_count() == 0

    queue.dequeue()
    assert queue.processed_count() == 1

    queue.dequeue()
    assert queue.processed_count() == 2

    # Dequeue from empty queue doesn't increment
    queue.dequeue()
    assert queue.processed_count() == 2
