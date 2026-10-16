"""
tests/test_weather_services.py - Weather service tests.
Tests for risk classification and approval role determination.
"""

import pytest
from unittest import mock

from pypharm import (
    WeatherService,
    WeatherReading,
    WeatherConfig,
)


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
