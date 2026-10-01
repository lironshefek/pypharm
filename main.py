"""
main.py - Demonstration of PyPharm system
"""

from pypharm import load_transfer_orders_from_jsonl, OrderBatch, open_orders_generator, critical_priority_orders_pipeline, LocationMaintenance


def main():
    print("\n=== PyPharm Demo ===\n")

    # 1. Load orders from JSONL file
    print("Loading orders...")
    orders = load_transfer_orders_from_jsonl("data/inventory_data.jsonl")

    # 2. Create batch (Iterable)
    print("\nCreating OrderBatch...")
    batch = OrderBatch(orders)
    print(f"Batch: {batch}")

    # 3. Test two independent iterators
    print("\nTesting two independent iterators...")
    iter1 = iter(batch)
    iter2 = iter(batch)
    print(f"Iterator 1 first order: {next(iter1).order_id}")
    print(f"Iterator 2 first order: {next(iter2).order_id}")
    print("Both start from beginning (independent)")

    # 4. Generator - lazy evaluation
    print("\nGenerator - Open orders (lazy)...")
    for order in open_orders_generator(batch):
        print(f"  {order.order_id} - {order.status}")

    # 5. Lazy Pipeline - 3-stage generator
    print("\nLazy Pipeline - Critical orders...")
    for summary in critical_priority_orders_pipeline(batch):
        print(f"  {summary}")

    # 6. Context Manager - normal case
    print("\nContext Manager - Normal case...")
    with LocationMaintenance("STORE-TLV") as loc:
        print(f"  Locked: {loc.location_id}")

    # 7. Context Manager - with exception
    print("\nContext Manager - With exception...")
    try:
        with LocationMaintenance("WH-CENTRAL") as loc:
            print(f"  Locked: {loc.location_id}")
            raise ValueError("Something went wrong")
    except ValueError:
        print("  Location unlocked even with exception")

    print("\nDemo completed!\n")


if __name__ == '__main__':
    main()



