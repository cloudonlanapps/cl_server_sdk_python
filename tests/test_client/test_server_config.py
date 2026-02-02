"""Tests for server configuration."""


import pytest

from cl_client.server_config import ServerConfig


class TestServerConfig:
    """Tests for ServerConfig dataclass."""

    def test_server_config_defaults(self, mqtt_url):
        """Test ServerConfig with default values for other fields."""
        config = ServerConfig(mqtt_url=mqtt_url)

        assert config.auth_url == "http://localhost:8000"
        assert config.compute_url == "http://localhost:8002"
        assert config.store_url == "http://localhost:8001"
        assert config.mqtt_url == mqtt_url

    def test_server_config_custom_values(self):
        """Test ServerConfig with custom values."""
        config = ServerConfig(
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
            store_url="https://store.example.com",
            mqtt_url="mqtts://mqtt.example.com:8883",
        )

        assert config.auth_url == "https://auth.example.com"
        assert config.compute_url == "https://compute.example.com"
        assert config.store_url == "https://store.example.com"
        assert config.mqtt_url == "mqtts://mqtt.example.com:8883"

    def test_server_config_partial_custom(self, mqtt_url):
        """Test ServerConfig with partial custom values."""
        config = ServerConfig(
            mqtt_url=mqtt_url,
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
        )

        # Custom values
        assert config.auth_url == "https://auth.example.com"
        assert config.compute_url == "https://compute.example.com"

        # Default values and provided mandatory
        assert config.store_url == "http://localhost:8001"
        assert config.mqtt_url == mqtt_url







    def test_server_config_mqtt_url_formats(self):
        """Test ServerConfig accepts various MQTT URL formats."""
        # Standard MQTT URL
        config1 = ServerConfig(mqtt_url="mqtt://broker:1883")
        assert config1.mqtt_url == "mqtt://broker:1883"

        # Secure MQTT URL
        config2 = ServerConfig(mqtt_url="mqtts://broker:8883")
        assert config2.mqtt_url == "mqtts://broker:8883"



    def test_server_config_immutable(self, mqtt_url):
        """Test that ServerConfig is a dataclass (not immutable by default)."""
        config = ServerConfig(mqtt_url=mqtt_url)

        # Dataclasses are mutable by default, but we can test assignment works
        original_url = config.auth_url
        config.auth_url = "https://new-auth.example.com"

        assert config.auth_url == "https://new-auth.example.com"
        assert config.auth_url != original_url

    def test_server_config_equality(self, mqtt_url):
        """Test ServerConfig equality comparison."""
        config1 = ServerConfig(
            mqtt_url=mqtt_url,
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
        )
        config2 = ServerConfig(
            mqtt_url=mqtt_url,
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
        )
        config3 = ServerConfig(
            mqtt_url="mqtt://other:1883",
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
        )

        # Same values should be equal
        assert config1 == config2

        # Different values should not be equal
        assert config1 != config3

    def test_server_config_repr(self, mqtt_url):
        """Test ServerConfig string representation."""
        config = ServerConfig(
            mqtt_url=mqtt_url,
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
        )

        repr_str = repr(config)

        # Should contain class name and field values
        assert "ServerConfig" in repr_str
        assert "auth_url" in repr_str
        assert "https://auth.example.com" in repr_str
