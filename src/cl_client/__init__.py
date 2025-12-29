"""Python client library for CL Server compute service.

Public API exports for client library usage.
"""

from .auth import AuthProvider, JWTAuthProvider, NoAuthProvider, get_default_auth
from .compute_client import ComputeClient
from .config import ComputeClientConfig
from .exceptions import (
    AuthenticationError,
    ComputeClientError,
    JobFailedError,
    JobNotFoundError,
    PermissionError,
    WorkerUnavailableError,
)
from .models import JobResponse, WorkerCapabilitiesResponse, WorkerCapability
from .mqtt_monitor import MQTTJobMonitor

__all__ = [
    # Client
    "ComputeClient",
    # Configuration
    "ComputeClientConfig",
    # Models
    "JobResponse",
    "WorkerCapability",
    "WorkerCapabilitiesResponse",
    # Exceptions
    "ComputeClientError",
    "JobNotFoundError",
    "JobFailedError",
    "AuthenticationError",
    "PermissionError",
    "WorkerUnavailableError",
    # Auth
    "AuthProvider",
    "NoAuthProvider",
    "JWTAuthProvider",
    "get_default_auth",
    # MQTT
    "MQTTJobMonitor",
]
