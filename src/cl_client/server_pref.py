"""Server configuration for URL management.

Provides centralized configuration for all service endpoints,
matching Dart SDK's ServerConfig pattern for consistency across client libraries.
"""

import os
from dataclasses import dataclass


@dataclass
class ServerPref:
    """Configuration for CL Server service URLs.

    Centralizes URL management for auth, compute, and future services.
    Follows Dart SDK pattern for consistency across client libraries.

    All fields have sensible defaults for local development but can be
    customized for production environments.

    Example:
        # Default configuration (localhost)
        config = ServerConfig()

        # Custom configuration
        config = ServerConfig(
            auth_url="https://auth.example.com",
            compute_url="https://compute.example.com"
        )

        # From environment variables
        config = ServerConfig.from_env()
    """

    # Service URLs
    auth_url: str = "http://localhost:8000"
    compute_url: str = "http://localhost:8002"
    store_url: str = "http://localhost:8001"  # For Phase 3

    # MQTT Configuration (shared across services)
    mqtt_url: str = "mqtt://localhost:1883"

    @classmethod
    def from_env(cls) -> "ServerPref":
        """Create ServerPref from environment variables.

        Loads configuration from environment variables with fallback to defaults.
        This allows easy configuration in different deployment environments without
        code changes.

        Environment variables:
            AUTH_URL: Auth service URL (default: http://localhost:8000)
            COMPUTE_URL: Compute service URL (default: http://localhost:8002)
            STORE_URL: Store service URL (default: http://localhost:8001)
            MQTT_URL: MQTT broker URL (default: mqtt://localhost:1883)

        Returns:
            ServerPref with values from environment or defaults

        Example:
            # Set environment variables
            os.environ['AUTH_URL'] = 'https://auth.prod.example.com'
            os.environ['COMPUTE_URL'] = 'https://compute.prod.example.com'

            # Load configuration
            config = ServerPref.from_env()
            print(config.auth_url)  # https://auth.prod.example.com
        """
        # Get default instance for fallback values
        default = cls()

        return cls(
            auth_url=os.getenv("AUTH_URL", default.auth_url),
            compute_url=os.getenv("COMPUTE_URL", default.compute_url),
            store_url=os.getenv("STORE_URL", default.store_url),
            mqtt_url=os.getenv("MQTT_URL", default.mqtt_url),
        )
