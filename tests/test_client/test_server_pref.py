"""Tests for server configuration."""


import pytest

from cl_client.server_pref import ServerPref


class TestServerPref:
    """Tests for ServerPref dataclass."""

    def test_server_pref_defaults(self):
        """Test ServerPref with default values."""
        config = ServerPref()

        assert config.auth_url == "http://localhost:8000"
        assert config.compute_url == "http://localhost:8002"
        assert config.store_url == "http://localhost:8001"
        assert config.mqtt_url == "mqtt://localhost:1883"

    def test_server_pref_custom_values(self):
        """Test ServerPref with custom values."""
        config = ServerPref(
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
            store_url="https://store.example.com",
            mqtt_url="mqtts://mqtt.example.com:8883",
        )

        assert config.auth_url == "https://auth.example.com"
        assert config.compute_url == "https://compute.example.com"
        assert config.store_url == "https://store.example.com"
        assert config.mqtt_url == "mqtts://mqtt.example.com:8883"

    def test_server_pref_partial_custom(self):
        """Test ServerPref with partial custom values."""
        config = ServerPref(
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
        )

        # Custom values
        assert config.auth_url == "https://auth.example.com"
        assert config.compute_url == "https://compute.example.com"

        # Default values
        assert config.store_url == "http://localhost:8001"
        assert config.mqtt_url == "mqtt://localhost:1883"

    def test_server_pref_from_env_all_vars(self, monkeypatch: pytest.MonkeyPatch):
        """Test ServerPref.from_env() with all environment variables set."""
        # Set environment variables
        monkeypatch.setenv("AUTH_URL", "https://auth.prod.example.com")
        monkeypatch.setenv("COMPUTE_URL", "https://compute.prod.example.com")
        monkeypatch.setenv("STORE_URL", "https://store.prod.example.com")
        monkeypatch.setenv("MQTT_URL", "mqtt://mqtt.prod.example.com:8883")

        config = ServerPref.from_env()

        assert config.auth_url == "https://auth.prod.example.com"
        assert config.compute_url == "https://compute.prod.example.com"
        assert config.store_url == "https://store.prod.example.com"
        assert config.mqtt_url == "mqtt://mqtt.prod.example.com:8883"

    def test_server_pref_from_env_partial_vars(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test ServerPref.from_env() with partial environment variables."""
        # Only set some environment variables
        monkeypatch.setenv("AUTH_URL", "https://auth.example.com")

        config = ServerPref.from_env()

        # From environment
        assert config.auth_url == "https://auth.example.com"
        assert config.mqtt_url == "mqtt://localhost:1883"  # Default if not set

        # From defaults
        assert config.compute_url == "http://localhost:8002"
        assert config.store_url == "http://localhost:8001"

    def test_server_pref_from_env_no_vars(self, monkeypatch: pytest.MonkeyPatch):
        """Test ServerPref.from_env() with no environment variables."""
        # Clear all relevant environment variables
        for var in [
            "AUTH_URL",
            "COMPUTE_URL",
            "STORE_URL",
            "MQTT_URL",
        ]:
            monkeypatch.delenv(var, raising=False)

        config = ServerPref.from_env()

        # Should use all defaults
        assert config.auth_url == "http://localhost:8000"
        assert config.compute_url == "http://localhost:8002"
        assert config.store_url == "http://localhost:8001"
        assert config.mqtt_url == "mqtt://localhost:1883"

    def test_server_pref_mqtt_url_env(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test ServerPref.from_env() supports MQTT_URL."""
        monkeypatch.setenv("MQTT_URL", "mqtt://custom:1883")
    
        config = ServerPref.from_env()
    
        assert config.mqtt_url == "mqtt://custom:1883"

    def test_server_pref_immutable(self):
        """Test that ServerPref is a dataclass (not immutable by default)."""
        config = ServerPref()

        # Dataclasses are mutable by default, but we can test assignment works
        original_url = config.auth_url
        config.auth_url = "https://new-auth.example.com"

        assert config.auth_url == "https://new-auth.example.com"
        assert config.auth_url != original_url

    def test_server_pref_equality(self):
        """Test ServerPref equality comparison."""
        config1 = ServerPref(
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
        )
        config2 = ServerPref(
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
        )
        config3 = ServerPref(
            auth_url="https://different.example.com",
            compute_url="https://compute.example.com",
        )

        # Same values should be equal
        assert config1 == config2

        # Different values should not be equal
        assert config1 != config3

    def test_server_pref_repr(self):
        """Test ServerPref string representation."""
        config = ServerPref(
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com",
        )

        repr_str = repr(config)

        # Should contain class name and field values
        assert "ServerPref" in repr_str
        assert "auth_url" in repr_str
        assert "https://auth.example.com" in repr_str
