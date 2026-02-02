"""
Shared test configuration - Pydantic models and helper functions.

This conftest provides models and helpers that are imported directly by test files.
Integration test fixtures are in tests/test_integration/conftest.py
"""

import os
from pathlib import Path

import pytest
from pydantic import BaseModel

# ============================================================================
# TEST ARTIFACT DIRECTORY
# ============================================================================

TEST_ARTIFACT_DIR = Path(os.getenv("TEST_ARTIFACT_DIR", "/tmp/cl_server_test_artifacts")) / "pysdk"
TEST_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class CliConfig(BaseModel):
    """CLI configuration from pytest arguments."""
    auth_url: str
    compute_url: str
    store_url: str
    mqtt_url: str
    username: str | None
    password: str | None


class ServerRootResponse(BaseModel):
    """Server root endpoint response (health check)."""
    status: str
    service: str
    version: str
    guestMode: str = "off"  # "on" or "off"
    auth_required: bool = True  # Only from compute service


class ComputeServerInfo(BaseModel):
    """Compute server capability information."""
    auth_required: bool = True
    guest_mode: bool = False  # Converted from "on"/"off" string


class StoreServerInfo(BaseModel):
    """Store server capability information."""
    guest_mode: bool = False  # Converted from "on"/"off" string


class UserInfo(BaseModel):
    """Current user information from /users/me."""
    id: int
    username: str
    is_admin: bool
    is_active: bool
    permissions: list[str]


class AuthConfig(BaseModel):
    """Complete auth configuration for tests."""
    mode: str  # "auth" or "no-auth"
    auth_url: str
    compute_url: str
    store_url: str
    mqtt_url: str
    compute_auth_required: bool
    compute_guest_mode: bool
    store_guest_mode: bool
    username: str | None
    password: str | None
    user_info: UserInfo | None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def should_succeed(auth_config: AuthConfig, operation_type: str) -> bool:
    """Determine if operation should succeed based on auth config.

    Args:
        auth_config: AuthConfig Pydantic model
        operation_type: "plugin", "store_read", "store_write", or "admin"

    Returns:
        True if operation should succeed, False otherwise
    """
    user_info = auth_config.user_info
    compute_auth_required = auth_config.compute_auth_required
    compute_guest_mode = auth_config.compute_guest_mode
    store_guest_mode = auth_config.store_guest_mode

    # No auth mode (user_info is None)
    if user_info is None:
        if operation_type == "plugin":
            # Plugin operations succeed if compute auth not required OR compute guest mode enabled
            return (not compute_auth_required) or compute_guest_mode
        elif operation_type == "store_read":
            # Store read succeeds if store guest mode enabled
            return store_guest_mode
        elif operation_type in ["store_write", "admin"]:
            # Write/admin always require auth
            return False

    # Authenticated mode
    # At this point user_info is guaranteed to be not None
    assert user_info is not None
    is_admin = user_info.is_admin
    permissions = user_info.permissions

    if operation_type == "plugin":
        return is_admin or "ai_inference_support" in permissions
    elif operation_type == "store_read":
        return is_admin or "media_store_read" in permissions
    elif operation_type == "store_write":
        return is_admin or "media_store_write" in permissions
    elif operation_type == "admin":
        return is_admin
    else:
        raise ValueError(f"Unknown operation_type: {operation_type}")


def get_expected_error(auth_config: AuthConfig, operation_type: str) -> int:
    """Get expected HTTP error code when operation fails.

    Args:
        auth_config: AuthConfig Pydantic model
        operation_type: Operation type

    Returns:
        401 (no auth) or 403 (insufficient permissions)
    """
    assert not should_succeed(auth_config, operation_type), \
        "get_expected_error() called for operation that should succeed"

    # No auth = 401 Unauthorized
    if auth_config.user_info is None:
        return 401

    # Authenticated but insufficient permissions = 403 Forbidden
    return 403

# ============================================================================
# PYTEST CLI OPTIONS
# ============================================================================


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add CLI options for all PySDK tests."""
    # We use a try/except or check if already added to avoid conflicts if 
    # integration conftest also defines it (though we plan to remove it there)
    try:
        parser.addoption(
            "--mqtt-url",
            action="store",
            default="mqtt://localhost:1883",
            help="MQTT broker URL (e.g., mqtt://localhost:1883)"
        )
    except ValueError:
        pass # already added


@pytest.fixture
def mqtt_url(request: pytest.FixtureRequest) -> str:
    """Fixture to get MQTT URL from pytest options."""
    return str(request.config.getoption("--mqtt-url"))
