"""Server configuration for URL management.

Provides centralized configuration for all service endpoints,
matching Dart SDK's ServerConfig pattern for consistency across client libraries.
"""

import os
from dataclasses import dataclass


@dataclass
class ServerConfig:
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

    # MQTT Configuration (shared across services)
    mqtt_url: str = "mqtt://localhost:1883"

    # Service URLs
    auth_url: str = "http://localhost:8000"
    compute_url: str = "http://localhost:8002"
    store_url: str = "http://localhost:8001"  # For Phase 3


