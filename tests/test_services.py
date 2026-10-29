"""
tests/test_services.py - Weather service tests.
Tests for risk classification and approval role determination.
"""

import json

import pytest
from unittest import mock

from pypharm import (
    Employee,
    Location,
    TransferOrder,
    WeatherService,
    WeatherReading,
    WeatherConfig,
)
from pypharm.exceptions import WeatherCommunicationError
from pypharm.repository import load_sample_data_from_jsonl


class TestWeatherClassification:
    """Test weather risk classification."""

    @pytest.fixture
    def service(self):
        """Create a WeatherService instance."""
        return WeatherService()

    @pytest.mark.parametrize("temperature,expected", [
        (-5, "DANGER"),      # Below 0
        (0, "NORMAL"),       # Boundary: 0 is NORMAL
        (15, "NORMAL"),      # Mid-range
        (30, "NORMAL"),      # Boundary: 30 is NORMAL
        (31, "DANGER"),      # Above 30
        (40, "DANGER"),      # High temp
    ])
    def test_classify_risk(self, service, temperature, expected):
        """Test risk classification with various temperatures."""
        risk = service.classify_risk(temperature)
        assert risk == expected

    def test_get_required_roles_normal(self, service):
        """Test approval roles for NORMAL weather."""
        roles = service.get_required_roles("NORMAL")
        # Both WAREHOUSE_MANAGER and LOGISTICS_MANAGER can approve
        assert "WAREHOUSE_MANAGER" in roles
        assert "LOGISTICS_MANAGER" in roles
        assert len(roles) == 2

    def test_get_required_roles_danger(self, service):
        """Test approval roles for DANGER weather."""
        roles = service.get_required_roles("DANGER")
        # Only LOGISTICS_MANAGER can approve
        assert roles == ["LOGISTICS_MANAGER"]

    def test_can_approve_normal(self, service):
        """Test can_approve for NORMAL weather."""
        # noa (WAREHOUSE_MANAGER) can approve NORMAL
        assert service.can_approve("WAREHOUSE_MANAGER", "NORMAL")
        # Aya (LOGISTICS_MANAGER) can approve NORMAL
        assert service.can_approve("LOGISTICS_MANAGER", "NORMAL")
        # CASHIER cannot approve NORMAL
        assert not service.can_approve("CASHIER", "NORMAL")

    def test_can_approve_danger(self, service):
        """Test can_approve for DANGER weather."""
        # Only LOGISTICS_MANAGER can approve DANGER
        assert service.can_approve("LOGISTICS_MANAGER", "DANGER")
        # WAREHOUSE_MANAGER cannot approve DANGER
        assert not service.can_approve("WAREHOUSE_MANAGER", "DANGER")
        # CASHIER cannot approve DANGER
        assert not service.can_approve("CASHIER", "DANGER")


class TestWeatherIntegration:
    """Test weather service integration with API."""

    def test_check_and_classify_for_order(self):
        """Test complete weather check and classification."""
        # Create a mock location
        mock_location = mock.Mock()
        mock_location.latitude = 32.0853
        mock_location.longitude = 34.7818
        mock_location.city = "Tel Aviv"

        # Mock the API call
        mock_weather_reading = WeatherReading(temperature_2m=20.5, rain=2.1)

        service = WeatherService()

        with mock.patch("pypharm.services.get_weather_with_retry") as mock_get:
            mock_get.return_value = mock_weather_reading

            result = service.check_and_classify_for_order(mock_location)

        assert result["temperature"] == 20.5
        assert result["risk_level"] == "NORMAL"
        assert "WAREHOUSE_MANAGER" in result["required_roles"]
        assert "LOGISTICS_MANAGER" in result["required_roles"]
        assert isinstance(result["weather_reading"], WeatherReading)


class TestCombinedApprovalFlow:
    """Integrated flow: JSONL file -> repository/factory -> WeatherService -> observers."""

    @pytest.fixture
    def sample_file(self, tmp_path):
        records = [
            {"entity_type": "location", "location_id": "WH-CENTRAL", "name": "Central Hub",
             "location_type": "WAREHOUSE", "city": "Modiin", "latitude": 31.9103, "longitude": 35.1876},
            {"entity_type": "location", "location_id": "STORE-TLV", "name": "TLV Store",
             "location_type": "STORE", "city": "Tel Aviv", "latitude": 32.0853, "longitude": 34.7818},
            {"entity_type": "location", "location_id": "STORE-HAIFA", "name": "Haifa Store",
             "location_type": "STORE", "city": "Haifa", "latitude": 32.8193, "longitude": 34.9927},
            {"entity_type": "employee", "employee_id": "EMP-101", "name": "Aya",
             "role": "LOGISTICS_MANAGER", "is_active": True},
            {"entity_type": "perishable_product", "sku": "CRM-1003", "name": "Cleansing Balm",
             "brand": "Elemis", "price": 220.0, "expiry_date": "2030-09-30",
             "requires_refrigeration": True},
        ]
        path = tmp_path / "sample.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
        return path

    def test_loaded_orders_are_classified_and_dangerous_one_is_escalated(self, sample_file):
        objects = load_sample_data_from_jsonl(str(sample_file))
        locations = {o.location_id: o for o in objects if isinstance(o, Location)}
        employees = {o.employee_id: o for o in objects if isinstance(o, Employee)}

        # External dependency replaced: a hot day at the Tel Aviv store,
        # and one transient timeout before Haifa answers.
        temperatures = {(32.0853, 34.7818): 34.0, (32.8193, 34.9927): 22.0}
        haifa_calls = []

        def fake_get_weather(lat, lon):
            if (lat, lon) == (32.8193, 34.9927):
                haifa_calls.append(1)
                if len(haifa_calls) == 1:
                    raise WeatherCommunicationError("timeout")
            return WeatherReading(temperature_2m=temperatures[(lat, lon)], rain=0.0)

        audit = mock.Mock()
        service = WeatherService(
            client=mock.Mock(get_weather=fake_get_weather), observers=[audit]
        )
        hot_order = TransferOrder("ORD-1", "WH-CENTRAL", "STORE-TLV", 1,
                                  handled_by_employee_id="EMP-101")
        mild_order = TransferOrder("ORD-2", "WH-CENTRAL", "STORE-HAIFA", 2,
                                   handled_by_employee_id="EMP-101")

        with mock.patch("pypharm.api_client.time.sleep"):
            hot = service.check_and_classify_for_order(
                locations[hot_order.to_location_id], hot_order, employees)
            mild = service.check_and_classify_for_order(
                locations[mild_order.to_location_id], mild_order, employees)

        # 34C > 30C -> only a logistics manager may approve, and one event is raised
        assert hot["risk_level"] == "DANGER"
        assert hot["required_roles"] == ["LOGISTICS_MANAGER"]
        assert audit.update.call_count == 1
        assert audit.update.call_args.args[0].order_id == "ORD-1"

        # Haifa succeeded on the retry and stays a normal shipment
        assert len(haifa_calls) == 2
        assert mild["risk_level"] == "NORMAL"
        assert mild["required_roles"] == ["WAREHOUSE_MANAGER", "LOGISTICS_MANAGER"]

        # The assigned employee (loaded from the file) may approve both orders
        approver_role = employees["EMP-101"].role
        assert service.can_approve(approver_role, hot["risk_level"])
        assert service.can_approve(approver_role, mild["risk_level"])
        # Classification never changes the order status by itself
        assert hot_order.status == "PENDING" and mild_order.status == "PENDING"
