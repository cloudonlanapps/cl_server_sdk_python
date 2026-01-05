"""Enhanced test parametrization with multi-mode auth support and server detection."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx
import pytest
from cl_client import (
    ComputeClient,
    ServerConfig,
    SessionManager,
    UserCreateRequest,
)


# ============================================================================
# CONFIGURATION LOADING
# ============================================================================

def load_auth_config() -> dict[str, Any]:
    """Load authentication configuration from JSON file."""
    config_file = Path(__file__).parent / "auth_config.json"
    if not config_file.exists():
        pytest.fail(f"Auth config file not found: {config_file}")

    with open(config_file) as f:
        return json.load(f)


async def get_server_info(compute_url: str = "http://localhost:8002") -> dict[str, Any]:
    """Get server configuration including auth_required flag."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(compute_url, timeout=2.0)
            return response.json()
    except Exception as e:
        pytest.fail(f"Could not connect to compute server at {compute_url}: {e}")


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

def pytest_addoption(parser: pytest.Parser) -> None:
    """Register custom command-line options."""
    config = load_auth_config()

    # Build choices from config file: ["auto", "no-auth"] + test user roles
    test_user_roles = list(config["test_users"].keys())
    modes = ["auto", "no-auth"] + test_user_roles

    parser.addoption(
        "--auth-mode",
        action="store",
        default="auto",
        choices=modes,
        help="Authentication mode for tests (auto-detects from server by default)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "admin_only: mark test as requiring admin permissions (skipped in no-auth mode)",
    )


# ============================================================================
# SESSION-SCOPED FIXTURES (RUN ONCE PER TEST SESSION)
# ============================================================================

@pytest.fixture(scope="session")
def test_config() -> dict[str, Any]:
    """Load test configuration from file."""
    return load_auth_config()


@pytest.fixture(scope="session")
def server_info(test_config: dict[str, Any]) -> dict[str, Any]:
    """Get server info including auth_required flag."""
    return asyncio.run(get_server_info(test_config["compute_url"]))


async def get_store_info(store_url: str = "http://localhost:8001") -> dict[str, Any]:
    """Get store configuration including guestMode flag."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(store_url, timeout=2.0)
            return response.json()
    except Exception as e:
        pytest.fail(f"Could not connect to store server at {store_url}: {e}")


@pytest.fixture(scope="session")
def store_info(test_config: dict[str, Any]) -> dict[str, Any]:
    """Get store info including guestMode flag."""
    store_url = test_config.get("store_url", "http://localhost:8001")
    return asyncio.run(get_store_info(store_url))


@pytest.fixture(scope="session")
def auth_mode(
    request: pytest.FixtureRequest,
    server_info: dict[str, Any],
    test_config: dict[str, Any],
) -> str:
    """Determine auth mode and validate against server config."""
    mode = request.config.getoption("--auth-mode")

    # Auto-detect based on server config
    if mode == "auto":
        if server_info.get("auth_required", False):
            mode = test_config.get("default_auth_mode", "user-with-permission")
        else:
            mode = "no-auth"

    # No session-level skip - let individual tests handle auth mode validation
    # Different services have different auth requirements:
    # - Compute: Can have AUTH_DISABLED=true
    # - Store: Has its own guestMode for reads
    # - Auth: Always requires auth for protected endpoints

    return mode


@pytest.fixture(scope="session")
async def test_users_setup(
    auth_mode: str,
    test_config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Ensure test users exist - create if needed, validate if exist."""

    # No setup needed for no-auth mode
    if auth_mode == "no-auth":
        return {}

    # Check if auth server is available when auth mode is enabled
    auth_url = test_config["auth_url"]
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{auth_url}/auth/public-key",
                timeout=2.0,
            )
            if response.status_code != 200:
                pytest.fail(
                    f"Auth server at {auth_url} returned {response.status_code}"
                )
    except Exception as e:
        pytest.fail(
            f"Auth server at {auth_url} is not available but auth mode is enabled: {e}"
        )

    # Get admin password from environment
    admin_password = os.getenv("TEST_ADMIN_PASSWORD")
    if not admin_password:
        pytest.fail(
            "TEST_ADMIN_PASSWORD environment variable required for auth mode tests"
        )

    admin_username = test_config["test_users"]["admin"]["username"]

    # Login as admin
    config = ServerConfig(
        auth_url=str(test_config["auth_url"]),
        compute_url=str(test_config["compute_url"]),
    )
    admin_session = SessionManager(server_config=config)

    try:
        await admin_session.login(admin_username, admin_password)
    except Exception as e:
        await admin_session.close()
        pytest.fail(f"Failed to login as admin user '{admin_username}': {e}")

    auth_client = admin_session._auth_client
    token = admin_session.get_token()

    # Setup non-admin test users
    user_credentials: dict[str, dict[str, Any]] = {
        "admin": {
            "username": admin_username,
            "password": admin_password,
            "is_admin": True,
            "permissions": [],
        }
    }

    for role in test_config["test_users"].keys():
        if role == "admin":
            continue  # Already handled

        user_config = test_config["test_users"][role]
        username = user_config["username"]
        password = user_config["password"]

        # Check if user exists by trying to get user list and find them
        try:
            users = await auth_client.list_users(token=token, skip=0, limit=100)
            existing_user = next((u for u in users if u.username == username), None)

            if existing_user:
                # User exists - validate credentials by attempting login
                test_session = SessionManager(server_config=config)
                try:
                    await test_session.login(username, password)
                    await test_session.close()
                    print(f"✓ Test user '{username}' exists and credentials valid")
                except Exception:
                    await test_session.close()
                    pytest.fail(
                        f"Test user '{username}' exists but password in config file is incorrect. "
                        f"Please update password in tests/auth_config.json or delete the user."
                    )
            else:
                # User doesn't exist - create it
                print(f"Creating test user '{username}'...")
                user_create = UserCreateRequest(
                    username=username,
                    password=password,
                    is_admin=user_config["is_admin"],
                    is_active=True,
                    permissions=user_config["permissions"],
                )
                await auth_client.create_user(token=token, user_create=user_create)
                print(f"✓ Created test user '{username}'")

        except Exception as e:
            await admin_session.close()
            pytest.fail(f"Failed to setup test user '{username}': {e}")

        user_credentials[role] = {
            "username": username,
            "password": password,
            "is_admin": user_config["is_admin"],
            "permissions": user_config["permissions"],
        }

    await admin_session.close()

    return user_credentials


# ============================================================================
# TEST-SCOPED FIXTURES (RUN PER TEST)
# ============================================================================

@pytest.fixture
def auth_config(
    auth_mode: str,
    server_info: dict[str, Any],
    store_info: dict[str, Any],
    test_users_setup: dict[str, dict[str, Any]],
    test_config: dict[str, Any],
) -> dict[str, Any]:
    """Provide auth configuration for current test."""
    server_auth_enabled = server_info.get("auth_required", False)
    store_guest_mode = store_info.get("guestMode", "off")  # "on" = public read, "off" = auth required

    config: dict[str, Any] = {
        "mode": auth_mode,
        "server_auth_enabled": server_auth_enabled,
        "store_guest_mode": store_guest_mode,
        "auth_url": test_config["auth_url"],
        "compute_url": test_config["compute_url"],
        "store_url": test_config.get("store_url", "http://localhost:8001"),  # Add store URL
    }

    # Determine expected behavior
    if auth_mode == "no-auth":
        config.update(
            {
                "username": None,
                "password": None,
                "is_admin": False,
                "has_permissions": not server_auth_enabled,  # Only succeed if server has no auth
                "should_fail_with_auth_error": server_auth_enabled,  # Expect 401 if server requires auth
                "permissions": [],  # No permissions in no-auth mode
            }
        )
    else:
        user_creds = test_users_setup[auth_mode]
        config.update(
            {
                "username": user_creds["username"],
                "password": user_creds["password"],
                "is_admin": user_creds["is_admin"],
                "has_permissions": auth_mode in ["admin", "user-with-permission"],
                "should_fail_with_auth_error": False,
                "permissions": user_creds.get("permissions", []),  # Add permissions list
            }
        )

    return config


@pytest.fixture
async def test_client(auth_config: dict[str, Any]):
    """Create ComputeClient based on auth configuration."""
    if auth_config["mode"] == "no-auth":
        client = ComputeClient(base_url=str(auth_config["compute_url"]))
        yield client
        await client.close()
    else:
        config = ServerConfig(
            auth_url=str(auth_config["auth_url"]),
            compute_url=str(auth_config["compute_url"]),
        )
        session = SessionManager(server_config=config)
        await session.login(
            str(auth_config["username"]),
            str(auth_config["password"]),
        )
        client = session.create_compute_client()

        # Attach session for admin operations (use different name to avoid conflict)
        client._auth_session = session  # type: ignore[attr-defined]

        yield client

        await client.close()
        await session.close()


# Backward compatibility alias
@pytest.fixture
async def client(test_client):
    """Backward compatibility alias for test_client fixture."""
    return test_client


@pytest.fixture
async def store_manager(auth_config: dict[str, Any]):
    """Create StoreManager based on auth configuration."""
    from cl_client.store_manager import StoreManager

    if auth_config["mode"] == "no-auth":
        # Guest mode
        manager = StoreManager.guest(base_url=str(auth_config["store_url"]))
        await manager.__aenter__()
        yield manager
        await manager.__aexit__(None, None, None)
    else:
        # Authenticated mode
        config = ServerConfig(
            auth_url=str(auth_config["auth_url"]),
            compute_url=str(auth_config["compute_url"]),
            store_url=str(auth_config["store_url"]),
        )
        session = SessionManager(server_config=config)
        await session.login(
            str(auth_config["username"]),
            str(auth_config["password"]),
        )

        manager = session.create_store_manager()
        await manager.__aenter__()

        # Attach session for cleanup
        manager._auth_session = session  # type: ignore[attr-defined]

        yield manager

        await manager.__aexit__(None, None, None)
        await session.close()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def should_succeed(auth_config: dict[str, Any], operation_type: str = "plugin") -> bool:
    """Determine if operation should succeed based on auth config.

    Args:
        auth_config: Authentication configuration
        operation_type: Type of operation - "plugin", "admin", "store_read", "store_write"

    Store-specific logic:
    - "store_read": Can be public if read_auth disabled (assumes disabled in no-auth mode)
    - "store_write": ALWAYS requires auth + media_store_write permission
    """
    mode = auth_config["mode"]

    # Store read operations - can be public if guestMode is "on"
    if operation_type == "store_read":
        store_guest_mode = auth_config.get("store_guest_mode", "off")
        if store_guest_mode == "on":
            # Guest mode enabled - read operations work for everyone
            return True
        # Guest mode disabled - need auth and permission
        if mode == "no-auth":
            return False
        # With auth, check for media_store_read permission or admin
        return auth_config["is_admin"] or "media_store_read" in auth_config.get("permissions", [])

    # Store write operations - ALWAYS require auth + permission
    elif operation_type == "store_write":
        if mode == "no-auth":
            # Write never works without auth
            return False
        if auth_config["is_admin"]:
            # Admin can always write
            return True
        # Check for media_store_write permission
        return "media_store_write" in auth_config.get("permissions", [])

    # Existing logic for plugin and admin operations
    if auth_config["should_fail_with_auth_error"]:
        return False

    if operation_type == "admin":
        return auth_config["is_admin"]
    elif operation_type == "plugin":
        return auth_config["has_permissions"]

    return True


def get_expected_error(
    auth_config: dict[str, Any], operation_type: str = "plugin"
) -> int | None:
    """Get expected HTTP error code for failed operations.

    Args:
        auth_config: Authentication configuration
        operation_type: Type of operation - "plugin", "admin", "store_read", "store_write"

    Store-specific logic:
    - store_read: 401 if read_auth enabled and no token, 403 if no permission
    - store_write: 401 if no token, 403 if insufficient permission
    """
    mode = auth_config["mode"]

    # Store read operations
    if operation_type == "store_read":
        if mode == "no-auth":
            # Only fails if read_auth is enabled (401 Unauthorized)
            # For testing, we assume read_auth is disabled in no-auth mode
            # so this shouldn't be called
            return 401
        # Has token but no permission
        return 403

    # Store write operations
    elif operation_type == "store_write":
        if mode == "no-auth":
            return 401  # No token
        # Has token but no permission
        return 403

    # Existing logic for plugin and admin operations
    if auth_config["should_fail_with_auth_error"]:
        return 401  # Unauthorized - no credentials provided

    if operation_type == "admin" and not auth_config["is_admin"]:
        return 403  # Forbidden - not admin

    if operation_type == "plugin" and not auth_config["has_permissions"]:
        return 403  # Forbidden - no permissions

    return None


# ============================================================================
# COLLECTION HOOKS
# ============================================================================

def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """No skipping - all tests run to verify server behavior.

    We test server endpoints in all auth modes to verify they return
    the correct HTTP status codes (200, 401, 403) based on the configuration.
    """
    pass  # Keep function for potential future use
