"""Factories for creating domain objects from input records."""

from .models import PerishableProduct, Product, StandardProduct


class ProductFactory:
    """Create the product subtype declared by a sample-data record."""

    _PRODUCT_TYPES = {
        "perishable_product": PerishableProduct,
        "standard_product": StandardProduct,
    }

    @classmethod
    def from_dict(cls, data: dict) -> Product:
        """Build a product from a record containing its ``entity_type``."""
        entity_type = data.get("entity_type")
        product_model = cls._PRODUCT_TYPES.get(entity_type)
        if product_model is None:
            raise ValueError(f"unknown product entity_type {entity_type!r}")
        return product_model.from_dict(data)
