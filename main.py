from itertools import islice
from pathlib import Path

import asyncio
import sys
import time

from pypharm import (
    Employee,
    InventoryItem,
    Location,
    LocationMaintenance,
    OrderBatch,
    Product,
    PerishableProduct,
    StandardProduct,
    critical_priority_orders_pipeline,
    load_sample_data_from_jsonl,
    load_transfer_orders_from_jsonl,
    load_inventory_items_from_jsonl,
    open_orders_generator,
    WeatherConfig,
    WeatherService,
    ApprovalQueue,
    queue_orders_for_approval,
    check_branches_concurrent,
    check_branches_serial,
    run_approvers,
)
from pypharm.api_client import MockWeatherClient
from pypharm.exceptions import WeatherCommunicationError
from pypharm.processing import (
    InventoryRegistry,
    LocationCategoryTracker,
    OrderProcessingQueue,
    PriorityTransferQueue,
    build_sku_to_price_map,
    extract_unique_brands,
    filter_high_value_products,
    process_shipment_manifest,
    sort_products_by_name,
    sort_products_by_price,
    sort_inventory_items_multi_criteria,
    validate_employees_integrity,
    process_order_lifecycle,
)
from pypharm.models import OrderActionAuthorizer
from pypharm.reports import generate_business_report, print_business_report


class PartlyDownWeatherClient(MockWeatherClient):
    """Demo client: mock readings, but the service is unreachable for some branches."""

    def __init__(self, temperatures: dict = None, down: set = ()):
        super().__init__(temperatures)
        self.down = set(down)

    def get_weather(self, latitude: float, longitude: float):
        if (latitude, longitude) in self.down:
            raise WeatherCommunicationError("weather service unreachable (simulated)")
        return super().get_weather(latitude, longitude)


def print_round(orders, queue) -> None:
    risk_by_order = queue.risk_by_order()
    for order in orders:
        print(f"   {order.order_id} -> {order.to_location_id:<11} "
              f"risk={risk_by_order[order.order_id]:<8} status={order.status}")


def run_combined_process(locations, employees, data_dir) -> None:
    """
    6.5 - one process across both systems, from trigger to report:
    trigger (orders ready to ship) -> weather at each destination (external data)
    -> who may approve (employees subsystem) -> order status changes -> report.
    """
    print("\n" + "=" * 60)
    print("STAGE 2: Combined process - weather decides who may ship (6.5)")
    print("=" * 60)

    orders = load_transfer_orders_from_jsonl(str(data_dir / "inventory_data.jsonl"))
    locations_by_id = {location.location_id: location for location in locations}
    employees_by_id = {employee.employee_id: employee for employee in employees}
    noa = next(e for e in employees if e.role == "WAREHOUSE_MANAGER")
    aya = next(e for e in employees if e.role == "LOGISTICS_MANAGER")
    haifa = locations_by_id["STORE-HAIFA"]
    haifa_coords = (haifa.latitude, haifa.longitude)

    demo_config = WeatherConfig()
    demo_config.RETRY_DELAY = 0  # the demo does not need to wait between retries

    print(f"\nTRIGGER: {len(orders)} transfer orders are ready to ship (all PENDING).")
    print(f"Today {aya.name} ({aya.role}) is on leave; only {noa.name} ({noa.role}) is approving.")
    # On leave: still an employee (her orders are not an integrity issue), but she cannot approve today
    aya.start_leave()

    print("\nROUND 1 - the weather service is unreachable for Haifa (mock data):")
    queue = ApprovalQueue()
    unreachable = PartlyDownWeatherClient(down={haifa_coords})
    queue_orders_for_approval(
        queue, orders, locations_by_id,
        WeatherService(demo_config, client=unreachable, observers=[]), employees_by_id,
    )
    run_approvers(queue, [noa])
    print_round(orders, queue)
    weather = generate_business_report(OrderBatch(orders), queue, employees_by_id)["weather_approval"]
    print(f"   Blocked by weather-service failure: {weather['blocked_by_weather_failure']} "
          f"(nobody may approve without a weather check)")

    print("\nROUND 2 - the service is back; waiting orders are re-checked: heat wave in Haifa (35C, mock data):")
    waiting = [order for order in orders if order.status == "PENDING"]
    # Same queue: an UNKNOWN order stays in it and gets its real risk on the re-check
    queue_orders_for_approval(
        queue, waiting, locations_by_id,
        WeatherService(demo_config, client=MockWeatherClient({haifa_coords: 35.0})), employees_by_id,
    )
    run_approvers(queue, [noa])
    print_round(waiting, queue)

    print("\nREPORT - decision point (data from both systems):")
    print_business_report(generate_business_report(OrderBatch(orders), queue, employees_by_id))

    print(f"DECISION: {aya.name} is called back from leave and approves the hot-weather orders.")
    aya.end_leave()
    run_approvers(queue, [aya])
    print_round(waiting, queue)

    print("\nREPORT - after the change:")
    print_business_report(generate_business_report(OrderBatch(orders), queue, employees_by_id))


def main():
    data_dir = Path(__file__).resolve().parent / "data"
    catalog_records = load_sample_data_from_jsonl(str(data_dir / "sample_data.jsonl"))
    orders = load_transfer_orders_from_jsonl(str(data_dir / "inventory_data.jsonl"))

    products = [record for record in catalog_records if isinstance(record, Product)]
    locations = [record for record in catalog_records if isinstance(record, Location)]
    employees = [record for record in catalog_records if isinstance(record, Employee)]
    batch = OrderBatch(orders)

    products_dict = {p.sku: p for p in products}
    inventory_items = load_inventory_items_from_jsonl(str(data_dir / "inventory_data.jsonl"), products_dict)

    print("=== PyPharm demo ===")
    print(
        f"Loaded {len(products)} products, {len(locations)} locations, "
        f"{len(employees)} employees, {len(orders)} transfer orders, and {len(inventory_items)} inventory items."
    )

    print("\nProduct behavior through the shared Product type:")
    polymorphic_products = [
        next(product for product in products if isinstance(product, PerishableProduct)),
        next(product for product in products if isinstance(product, StandardProduct)),
    ]
    for product in polymorphic_products:
        print(
            f"{product.name}: handling {product.calculate_handling_cost(1):.2f}; "
            f"{product.get_storage_requirements()}"
        )

    if orders:
        print(f"\nComposition: {orders[0].order_id} contains {len(orders[0])} item types.")

    print("\nCollection processing:")
    print("High-value products:", filter_high_value_products(products, 200))
    print("Unique brands:", sorted(extract_unique_brands(products)))
    print("SKU to price:", build_sku_to_price_map(products))
    print("Sorted by price:", [product.sku for product in sort_products_by_price(products)])
    print("Sorted by name:", [product.sku for product in sort_products_by_name(products)])

    print("\nMulti-criteria sorting (by location, then -available_quantity):")
    print("  From loaded inventory items:")
    for item in sort_inventory_items_multi_criteria(inventory_items[:3]):
        print(f"    {item.location_id}: {item.product.sku} ({item.available_quantity} available)")

    registry = InventoryRegistry()
    for product in products:
        registry.add_product(product)
    print("Expected missing product:", registry.get_product("UNKNOWN-SKU"))
    for brand, count in registry.count_products_by_brand().items():
        print(f"{brand}: {count} products")

    manifest = process_shipment_manifest(
        [("SHIP-1", "STORE-TLV", "CRM-1001", "PRF-2001")]
    )
    print("Shipment manifest:", manifest)

    location_tracker = LocationCategoryTracker()
    for location in locations:
        location_tracker.register_location(location)
    if locations:
        location_tracker.register_location(locations[0], is_refrigerated=True)
    print("Active locations:", sorted(location_tracker.active_locations))
    print("Non-refrigerated locations:", sorted(location_tracker.get_non_refrigerated_locations()))

    fifo = OrderProcessingQueue()
    for order in orders[:3]:
        fifo.enqueue_order(order)
    print("FIFO order:")
    for _ in range(3):
        next_order = fifo.process_next_order()
        if next_order is not None:
            print(" ", next_order.order_id)
    print("Empty FIFO:", fifo.process_next_order())

    priority_queue = PriorityTransferQueue()
    for order in orders[:3]:
        priority_queue.push_order(order)
    next_priority_order = priority_queue.pop_next_order()
    if next_priority_order is not None:
        print("Next priority order (smaller number is more urgent):", next_priority_order.order_id)

    print("\nIndependent iterators:")
    first_iterator = iter(batch)
    second_iterator = iter(batch)
    print("First iterator:", next(first_iterator).order_id)
    print("First iterator advances:", next(first_iterator).order_id)
    print("Second iterator still starts at:", next(second_iterator).order_id)

    print("\nGenerator continuation:")
    open_orders = open_orders_generator(batch)
    try:
        print("First open order:", next(open_orders).order_id)
    except StopIteration:
        print("No open orders.")
    for order in open_orders:
        print("Remaining open order:", order.order_id)
    try:
        next(open_orders)
    except StopIteration:
        print("The generator is exhausted; a new one is needed to start over.")
    restarted_orders = open_orders_generator(batch)
    try:
        print("New generator starts at:", next(restarted_orders).order_id)
    except StopIteration:
        print("No open orders to restart.")

    print("\nFirst two results from the lazy pipeline:")
    for summary in islice(critical_priority_orders_pipeline(batch), 2):
        print(" ", summary)

    print("\nContext manager:")
    with LocationMaintenance("STORE-TLV") as location:
        print("Locked:", location.location_id)
    try:
        with LocationMaintenance("WH-CENTRAL") as location:
            print("Locked:", location.location_id)
            raise ValueError("Demonstration error")
    except ValueError:
        print("The location was unlocked and the exception was not suppressed.")

    print_business_report(generate_business_report(batch))

    print("\n" + "="*60)
    print("OOP DEMONSTRATION: Authorization (check before update)")
    print("="*60)

    if orders and employees:
        authorizer = OrderActionAuthorizer()
        order = orders[0]

        logistics = next((e for e in employees if e.role == "LOGISTICS_MANAGER"), None)
        cashier = next((e for e in employees if e.role == "CASHIER"), None)

        if logistics:
            print(f"\nAuthorized (LOGISTICS_MANAGER) updates {order.order_id}:")
            try:
                authorizer.authorize_and_update_status(order, logistics, "IN_TRANSIT")
                print(f"  ✓ Status changed to {order.status}")
            except PermissionError as e:
                print(f"  ✗ {e}")

        if cashier:
            print(f"\nUnauthorized (CASHIER) tries to update {order.order_id}:")
            try:
                authorizer.authorize_and_update_status(order, cashier, "DELIVERED")
                print(f"  ✓ Status changed")
            except PermissionError as e:
                print(f"  ✗ {e}")

    print("\n" + "="*60)
    print("CREATIVITY: Order Lifecycle (reserve → dispatch → deliver)")
    print("="*60)

    if orders and products:
        order = orders[0]
        print(f"\nOrder {order.order_id}:")
        for item in order.items:
            print(f"  {item.sku}, qty={item.quantity}")

        inv_source = {}
        inv_dest = {}
        for item in order.items:
            product = next((p for p in products if p.sku == item.sku), None)
            if product:
                inv_source[item.sku] = InventoryItem(product, "WH", 50, 2)
                inv_dest[item.sku] = InventoryItem(product, "STORE", 10, 2)

        sku = order.items[0].sku
        print(f"\n1. Before reserve: available={inv_source[sku].available_quantity}")
        process_order_lifecycle(order, inv_source, inv_dest, "RESERVE")
        print(f"   After reserve:  available={inv_source[sku].available_quantity}, reserved={inv_source[sku].reserved}")

        process_order_lifecycle(order, inv_source, inv_dest, "DISPATCH")
        print(f"2. After dispatch: qty={inv_source[sku].quantity}")

        process_order_lifecycle(order, inv_source, inv_dest, "DELIVER")
        print(f"3. After deliver (destination): qty={inv_dest[sku].quantity}")

    print("\n" + "="*60)
    print("GROUP OF 4 EXTENSION: Data Integrity & Employee Validation")
    print("="*60)

    employees_dict = {emp.employee_id: emp for emp in employees}
    is_valid, errors = validate_employees_integrity(orders, employees_dict)

    if is_valid:
        print("All orders reference valid and active employees. System is consistent.")
    else:
        print("Integrity issues found:")
        for error in errors:
            print(f"  - {error}")

    print("\n" + "="*60)
    print("STAGE 2: Weather API Integration")
    print("="*60)

    config = WeatherConfig()
    service = WeatherService(config)
    if service.source == "live":
        print("\nMode: LIVE - real data from Open-Meteo (set by WEATHER_MODE=live)")
    else:
        print("\nMode: MOCK - simulated data, no network (run with WEATHER_MODE=live for the real API)")

    for location in locations:
        print(f"\n📍 {location.name} ({location.city}):")
        print(f"   Coordinates: ({location.latitude}, {location.longitude})")
        result = service.check_and_classify_for_order(location)
        if result["error"]:
            print(f"   ⚠️  Weather check failed: {result['error']}")
            print("   No one may approve this shipment - the order stays PENDING.")
            continue
        print(f"   Temperature: {result['temperature']}°C ({result['source']} data)")
        print(f"   Risk Level: {result['risk_level']}")
        print(f"   Approval Roles: {', '.join(result['required_roles'])}")

    print("\n" + "="*60)
    print("STAGE 2: Async weather checks (5.1) - simulated data, no network")
    print("="*60)

    branch_ids = [location.location_id for location in locations]
    simulation_service = WeatherService(config, client=MockWeatherClient())

    start = time.perf_counter()
    serial_results = asyncio.run(check_branches_serial(branch_ids, simulation_service))
    serial_time = time.perf_counter() - start

    start = time.perf_counter()
    concurrent_results = asyncio.run(check_branches_concurrent(branch_ids, simulation_service))
    concurrent_time = time.perf_counter() - start

    for result in concurrent_results:
        print(f"   {result['location_id']:12} {result['temperature']:5}°C -> {result['risk_level']}")
    print(f"\nSerial (one check after another): {serial_time:.2f}s")
    print(f"Concurrent (gather):              {concurrent_time:.2f}s")
    print(f"Same results, same input order: {serial_results == concurrent_results}")

    print("\n" + "="*60)
    print("STAGE 2: Shared approval queue with threads and a Lock (5.2)")
    print("="*60)

    approval_orders = load_transfer_orders_from_jsonl(str(data_dir / "inventory_data.jsonl"))
    haifa = next(location for location in locations if location.location_id == "STORE-HAIFA")
    heat_wave = MockWeatherClient({(haifa.latitude, haifa.longitude): 35.0})
    print("\nSimulated weather (mock): heat wave in Haifa (35°C), normal elsewhere.")

    # Weather is checked before the managers start - no network call inside the lock.
    queue = ApprovalQueue()
    queue_orders_for_approval(
        queue,
        approval_orders,
        {location.location_id: location for location in locations},
        WeatherService(config, client=heat_wave),
        employees_dict,
    )
    # Both managers compete for the orders; thread start order does not determine
    # which manager reaches an order first or how refusals split by reason.
    managers = [e for e in employees if e.role == "WAREHOUSE_MANAGER"] + [
        e for e in employees if e.role == "LOGISTICS_MANAGER"
    ]
    print(f"{len(queue)} orders waiting for approval.")
    print("Managers reviewing the same orders at the same time: "
          + ", ".join(f"{m.name} ({m.role})" for m in managers))

    run_approvers(queue, managers, review_time=0.05)

    print(f"\nApprovals: {queue.approved_count} (one per order)")
    print(f"Refused - already approved by the other manager: {queue.refusals[ApprovalQueue.ALREADY_HANDLED]}")
    print(f"Refused - role not allowed for this weather risk: {queue.refusals[ApprovalQueue.NOT_AUTHORIZED]}")
    print(f"Orders now IN_TRANSIT: {sum(order.status == 'IN_TRANSIT' for order in approval_orders)}")
    print(f"Orders still waiting: {len(queue)}")
    for order_id, manager, risk_level in queue.approval_log:
        print(f"   {order_id} ({risk_level}) approved by {manager}")

    run_combined_process(locations, employees, data_dir)


if __name__ == "__main__":
    # Windows uses a legacy encoding when output is redirected to a file or pipe.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    main()
