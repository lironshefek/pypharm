"""
Threaded weather checking with synchronized access to shared resources.

Demonstrates concurrent thread execution with thread-safe access to a shared
approval queue using a Lock. Multiple threads process orders requiring weather
approval without race conditions or data corruption.
"""

import logging
import threading
import time

from .services import WeatherService

logger = logging.getLogger(__name__)


class ApprovalQueue:
    """Thread-safe queue for orders requiring dangerous-weather approval."""

    def __init__(self):
        self._queue = []
        self._lock = threading.Lock()
        self._processed_count = 0

    def enqueue(self, order_info: dict) -> None:
        """Add an order to the approval queue (thread-safe)."""
        with self._lock:
            self._queue.append(order_info)
            logger.info(
                f"Enqueued order {order_info['order_id']} | Queue size: {len(self._queue)}"
            )

    def dequeue(self) -> dict | None:
        """Remove and return the next order from the queue (thread-safe)."""
        with self._lock:
            if self._queue:
                order = self._queue.pop(0)
                self._processed_count += 1
                return order
            return None

    def queue_size(self) -> int:
        """Get the current queue size (thread-safe)."""
        with self._lock:
            return len(self._queue)

    def processed_count(self) -> int:
        """Get the total number of processed orders (thread-safe)."""
        with self._lock:
            return self._processed_count


def approval_worker(
    worker_id: int,
    service: WeatherService,
    approval_queue: ApprovalQueue,
    results: list,
) -> None:
    """
    Worker thread: process orders from the approval queue.

    Each worker:
    - Dequeues an order
    - Checks weather at the destination
    - Records the result
    - Continues until queue is empty

    Uses the Lock inside ApprovalQueue to avoid race conditions.

    Args:
        worker_id: Worker thread identifier
        service: WeatherService instance
        approval_queue: Thread-safe ApprovalQueue
        results: List to collect results
    """
    logger.info(f"Worker {worker_id} started")

    while True:
        order_info = approval_queue.dequeue()
        if order_info is None:
            # Queue is empty, worker exits
            break

        order_id = order_info["order_id"]
        location = order_info["location"]

        # Check weather
        logger.info(
            f"Worker {worker_id} processing {order_id} at {location.name}..."
        )
        weather_result = service.check_and_classify_for_order(location)

        # Record result
        result_entry = {
            "worker_id": worker_id,
            "order_id": order_id,
            "location": location.name,
            "temperature": weather_result["temperature"],
            "risk_level": weather_result["risk_level"],
            "required_roles": weather_result["required_roles"],
        }
        results.append(result_entry)
        logger.info(
            f"Worker {worker_id} finished {order_id}: {weather_result['risk_level']}"
        )

    logger.info(f"Worker {worker_id} exiting")


def process_orders_threaded(
    service: WeatherService, orders: list, num_workers: int = 2
) -> list:
    """
    Process a list of orders using multiple threads.

    Each thread:
    - Pulls orders from a thread-safe queue
    - Checks weather
    - Records results

    All threads synchronize via Lock on the ApprovalQueue.

    Args:
        service: WeatherService instance
        orders: List of dicts with order_id and location
        num_workers: Number of worker threads (default 2)

    Returns:
        List of processing results
    """
    approval_queue = ApprovalQueue()
    results = []

    # Enqueue all orders
    for order in orders:
        approval_queue.enqueue(order)

    # Start worker threads
    threads = []
    for worker_id in range(num_workers):
        t = threading.Thread(
            target=approval_worker,
            args=(worker_id, service, approval_queue, results),
        )
        t.start()
        threads.append(t)

    # Wait for all threads to finish
    for t in threads:
        t.join()

    logger.info(f"All {num_workers} workers finished")
    return results


def demo_threaded_processing():
    """
    Demonstrate multi-threaded order processing with synchronized queue access.

    Creates 3 orders with different locations and processes them using 2 worker
    threads. Both threads safely access the shared queue protected by a Lock.
    """
    from .config import WeatherConfig
    from .api_client import MockWeatherClient
    from . import Location, TransferOrder

    config = WeatherConfig()
    # Use MockWeatherClient for predictable results
    service = WeatherService(config=config, client=MockWeatherClient())

    # Create orders with locations
    locations = [
        Location("STORE-MODIIN", "Modiin", "STORE", "Modiin", 31.9103, 35.1876),
        Location("STORE-TLV", "Tel Aviv", "STORE", "Tel Aviv", 32.0853, 34.7818),
        Location("STORE-HAIFA", "Haifa", "STORE", "Haifa", 32.8193, 34.9927),
    ]

    orders = []
    for i, loc in enumerate(locations):
        order = TransferOrder(
            f"ORD-WEATHER-{i+1:03d}", "WH-CENTRAL", loc.location_id, 1
        )
        orders.append({"order_id": order.order_id, "location": loc})

    # Process with 2 worker threads
    print("\n" + "=" * 70)
    print("SECTION 5.2: Multi-threaded Order Processing")
    print("=" * 70)
    print(f"\nProcessing {len(orders)} orders with {2} worker threads...")
    print("Each thread safely accesses the shared queue using a Lock.\n")

    start = time.time()
    results = process_orders_threaded(service, orders, num_workers=2)
    elapsed = time.time() - start

    print("\n📋 RESULTS (processed by multiple threads):")
    print("-" * 70)
    for r in results:
        print(
            f"  Worker {r['worker_id']} | {r['order_id']} | {r['location']:12} | "
            f"Temp: {r['temperature']:5}°C | Risk: {r['risk_level']:6} | "
            f"Roles: {', '.join(r['required_roles']) if r['required_roles'] else 'None'}"
        )

    print(
        f"\n✓ Processed {len(results)} orders in {elapsed:.3f}s using Lock-protected queue"
    )
    print("✓ No race conditions: all updates were thread-safe")
    print("=" * 70 + "\n")

    return results
