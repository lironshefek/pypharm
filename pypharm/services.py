"""
services.py - Weather classification and approval logic.
Business logic for determining required approval based on weather conditions.
"""

from .api_client import get_weather_with_retry


class WeatherService:
    """
    Classify weather conditions and determine required approval role.
    """

    # Temperature thresholds
    MIN_NORMAL_TEMP = 0  # Celsius
    MAX_NORMAL_TEMP = 30  # Celsius

    def classify_risk(self, temperature: float) -> str:
        """
        Classify weather risk based on temperature.

        Args:
            temperature: Current temperature in Celsius

        Returns:
            "NORMAL" if 0-30°C (inclusive)
            "DANGER" if <0°C or >30°C
        """
        if self.MIN_NORMAL_TEMP <= temperature <= self.MAX_NORMAL_TEMP:
            return "NORMAL"
        return "DANGER"

    def get_required_role(self, risk_level: str) -> str:
        """
        Get the required employee role to approve shipment.

        Args:
            risk_level: "NORMAL" or "DANGER"

        Returns:
            "WAREHOUSE_MANAGER" for NORMAL conditions
            "LOGISTICS_MANAGER" for DANGER conditions
        """
        if risk_level == "NORMAL":
            return "WAREHOUSE_MANAGER"
        return "LOGISTICS_MANAGER"

    def check_and_classify_for_order(self, location):
        """
        Check weather at destination and determine required approval.

        Args:
            location: Location object with latitude, longitude

        Returns:
            Dictionary with:
                - temperature: Current temperature
                - risk_level: "NORMAL" or "DANGER"
                - required_role: Role needed to approve
        """
        # Get weather data from API
        weather = get_weather_with_retry(location.latitude, location.longitude)

        # Extract temperature
        temperature = weather["temperature_2m"]

        # Classify risk
        risk_level = self.classify_risk(temperature)

        # Get required role
        required_role = self.get_required_role(risk_level)

        return {
            "temperature": temperature,
            "risk_level": risk_level,
            "required_role": required_role,
        }
