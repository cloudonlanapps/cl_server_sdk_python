"""Tests for server configuration."""

import os

import pytest

from cl_client.server_config import ServerConfig


class TestServerConfig:
    """Tests for ServerConfig dataclass."""

    def test_server_config_defaults(self):
        """Test ServerConfig with default values."""
        config = ServerConfig()

        assert config.auth_url == "http://localhost:8000"
        assert config.compute_url == "http://localhost:8002"
        assert config.store_url == "http://localhost:8001"
        assert config.mqtt_broker == "localhost"
        assert config.mqtt_port == 1883

    def test_server_config_custom_values(self):
        """Test ServerConfig with custom values."""
        config = ServerConfig(
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
            store_url="https://store.example.com",
            mqtt_broker="mqtt.example.com",
            mqtt_port=8883,
        )

        assert config.auth_url == "https://auth.example.com"
        assert config.compute_url == "https://compute.example.com"
        assert config.store_url == "https://store.example.com"
        assert config.mqtt_broker == "mqtt.example.com"
        assert config.mqtt_port == 8883

    def test_server_config_partial_custom(self):
        """Test ServerConfig with partial custom values."""
        config = ServerConfig(
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
        )

        # Custom values
        assert config.auth_url == "https://auth.example.com"
        assert config.compute_url == "https://compute.example.com"

        # Default values
        assert config.store_url == "http://localhost:8001"
        assert config.mqtt_broker == "localhost"
        assert config.mqtt_port == 1883

    def test_server_config_from_env_all_vars(self, monkeypatch: pytest.MonkeyPatch):
        """Test ServerConfig.from_env() with all environment variables set."""
        # Set environment variables
        monkeypatch.setenv("AUTH_URL", "https://auth.prod.example.com")
        monkeypatch.setenv("COMPUTE_URL", "https://compute.prod.example.com")
        monkeypatch.setenv("STORE_URL", "https://store.prod.example.com")
        monkeypatch.setenv("MQTT_BROKER", "mqtt.prod.example.com")
        monkeypatch.setenv("MQTT_PORT", "8883")

        config = ServerConfig.from_env()

        assert config.auth_url == "https://auth.prod.example.com"
        assert config.compute_url == "https://compute.prod.example.com"
        assert config.store_url == "https://store.prod.example.com"
        assert config.mqtt_broker == "mqtt.prod.example.com"
        assert config.mqtt_port == 8883

    def test_server_config_from_env_partial_vars(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test ServerConfig.from_env() with partial environment variables."""
        # Only set some environment variables
        monkeypatch.setenv("AUTH_URL", "https://auth.example.com")
        monkeypatch.setenv("MQTT_PORT", "9883")

        config = ServerConfig.from_env()

        # From environment
        assert config.auth_url == "https://auth.example.com"
        assert config.mqtt_port == 9883

        # From defaults
        assert config.compute_url == "http://localhost:8002"
        assert config.store_url == "http://localhost:8001"
        assert config.mqtt_broker == "localhost"

    def test_server_config_from_env_no_vars(self, monkeypatch: pytest.MonkeyPatch):
        """Test ServerConfig.from_env() with no environment variables."""
        # Clear all relevant environment variables
        for var in [
            "AUTH_URL",
            "COMPUTE_URL",
            "STORE_URL",
            "MQTT_BROKER",
            "MQTT_PORT",
        ]:
            monkeypatch.delenv(var, raising=False)

        config = ServerConfig.from_env()

        # Should use all defaults
        assert config.auth_url == "http://localhost:8000"
        assert config.compute_url == "http://localhost:8002"
        assert config.store_url == "http://localhost:8001"
        assert config.mqtt_broker == "localhost"
        assert config.mqtt_port == 1883

    def test_server_config_mqtt_port_string_conversion(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test ServerConfig.from_env() converts MQTT_PORT string to int."""
        monkeypatch.setenv("MQTT_PORT", "8883")

        config = ServerConfig.from_env()

        assert config.mqtt_port == 8883
        assert isinstance(config.mqtt_port, int)

    def test_server_config_immutable(self):
        """Test that ServerConfig is a dataclass (not immutable by default)."""
        config = ServerConfig()

        # Dataclasses are mutable by default, but we can test assignment works
        original_url = config.auth_url
        config.auth_url = "https://new-auth.example.com"

        assert config.auth_url == "https://new-auth.example.com"
        assert config.auth_url != original_url

    def test_server_config_equality(self):
        """Test ServerConfig equality comparison."""
        config1 = ServerConfig(
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
        )
        config2 = ServerConfig(
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
        )
        config3 = ServerConfig(
            auth_url="https://different.example.com",
            compute_url="https://compute.example.com",
        )

        # Same values should be equal
        assert config1 == config2

        # Different values should not be equal
        assert config1 != config3

    def test_server_config_repr(self):
        """Test ServerConfig string representation."""
        config = ServerConfig(
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
        )

        repr_str = repr(config)

        # Should contain class name and field values
        assert "ServerConfig" in repr_str
        assert "auth_url" in repr_str
        assert "https://auth.example.com" in repr_str
