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
from .models import JobResponse, OnJobResponseCallback, WorkerCapabilitiesResponse, WorkerCapability
from .mqtt_monitor import MQTTJobMonitor
from .server_pref import ServerPref
from .session_manager import SessionManager
from .store_manager import StoreManager
from .store_models import (
    Entity,
    EntityListResponse,
    EntityPagination,
    EntityVersion,
    StoreConfig,
    StoreOperationResult,
)

__all__ = [
    # Client
    "ComputeClient",
    # Configuration
    "ComputeClientConfig",
    "ServerPref",
    # Models
    "JobResponse",
    "OnJobResponseCallback",
    "WorkerCapability",
    "WorkerCapabilitiesResponse",
    # Auth Models
    "TokenResponse",
    "PublicKeyResponse",
    "UserResponse",
    "UserCreateRequest",
    "UserUpdateRequest",
    # Store Models
    "Entity",
    "EntityListResponse",
    "EntityPagination",
    "EntityVersion",
    "StoreConfig",
    "StoreOperationResult",
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
    # Store
    "StoreManager",
    # MQTT
    "MQTTJobMonitor",
]
