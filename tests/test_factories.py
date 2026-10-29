import json

import pytest

from pypharm import PerishableProduct, ProductFactory, StandardProduct
from pypharm.repository import load_sample_data_from_jsonl


def test_product_factory_creates_perishable_product():
    product = ProductFactory.from_dict(
        {
            "entity_type": "perishable_product",
            "sku": "CRM-TEST",
            "name": "Test Cream",
            "brand": "PyPharm",
            "price": 10,
            "expiry_date": "2030-01-01",
            "requires_refrigeration": True,
        }
    )

    assert isinstance(product, PerishableProduct)
    assert product.expiry_date == "2030-01-01"
    assert product.requires_refrigeration is True


def test_product_factory_creates_standard_product():
    product = ProductFactory.from_dict(
        {
            "entity_type": "standard_product",
            "sku": "PRF-TEST",
            "name": "Test Perfume",
            "brand": "PyPharm",
            "price": 20,
            "weight_kg": 0.2,
        }
    )

    assert isinstance(product, StandardProduct)
    assert product.weight_kg == 0.2


def test_product_factory_rejects_unknown_type():
    with pytest.raises(ValueError, match="unknown product entity_type"):
        ProductFactory.from_dict({"entity_type": "unknown_product"})


def test_sample_loader_uses_factory_for_product_records(tmp_path):
    data_file = tmp_path / "catalog.jsonl"
    records = [
        {
            "entity_type": "perishable_product",
            "sku": "CRM-TEST",
            "name": "Test Cream",
            "brand": "PyPharm",
            "price": 10,
            "expiry_date": "2030-01-01",
            "requires_refrigeration": False,
        },
        {
            "entity_type": "standard_product",
            "sku": "PRF-TEST",
            "name": "Test Perfume",
            "brand": "PyPharm",
            "price": 20,
            "weight_kg": 0.2,
        },
    ]
    data_file.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")

    products = load_sample_data_from_jsonl(str(data_file))

    assert [type(product) for product in products] == [PerishableProduct, StandardProduct]
