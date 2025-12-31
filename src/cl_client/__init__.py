"""Python client library for CL Server compute service.

Public API exports for client library usage.
"""

from .auth import AuthProvider, JWTAuthProvider, NoAuthProvider, get_default_auth
from .auth_models import (
    PublicKeyResponse,
    TokenResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
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
from .server_config import ServerConfig
from .session_manager import SessionManager

__all__ = [
    # Client
    "ComputeClient",
    # Configuration
    "ComputeClientConfig",
    "ServerConfig",
    # Models
    "JobResponse",
    "WorkerCapability",
    "WorkerCapabilitiesResponse",
    # Auth Models
    "TokenResponse",
    "PublicKeyResponse",
    "UserResponse",
    "UserCreateRequest",
    "UserUpdateRequest",
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
    "SessionManager",
    # MQTT
    "MQTTJobMonitor",
]
