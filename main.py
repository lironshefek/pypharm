from itertools import islice
from pathlib import Path

from pypharm import (
    Employee,
    Location,
    LocationMaintenance,
    OrderBatch,
    Product,
    PerishableProduct,
    StandardProduct,
    critical_priority_orders_pipeline,
    load_sample_data_from_jsonl,
    load_transfer_orders_from_jsonl,
    open_orders_generator,
)
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
)
from pypharm.reports import generate_business_report, print_business_report


def main():
    data_dir = Path(__file__).resolve().parent / "data"
    catalog_records = load_sample_data_from_jsonl(str(data_dir / "sample_data.jsonl"))
    orders = load_transfer_orders_from_jsonl(str(data_dir / "inventory_data.jsonl"))

    products = [record for record in catalog_records if isinstance(record, Product)]
    locations = [record for record in catalog_records if isinstance(record, Location)]
    employees = [record for record in catalog_records if isinstance(record, Employee)]
    batch = OrderBatch(orders)

    print("=== PyPharm demo ===")
    print(
        f"Loaded {len(products)} products, {len(locations)} locations, "
        f"{len(employees)} employees, and {len(orders)} transfer orders."
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


if __name__ == "__main__":
    main()
