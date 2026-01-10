"""
Single-user pytest configuration with explicit CLI-driven auth.
"""

import asyncio

import httpx
import pytest
from pydantic import BaseModel
from cl_client import ComputeClient, ServerConfig, SessionManager


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class CliConfig(BaseModel):
    """CLI configuration from pytest arguments."""
    auth_url: str
    compute_url: str
    store_url: str
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
# SERVER PROBING
# ============================================================================


async def get_server_info(url: str) -> ServerRootResponse:
    """Query server root endpoint and return parsed response."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=2.0)
            return ServerRootResponse.model_validate(r.json())
    except Exception as e:
        pytest.fail(f"Cannot connect to server at {url}: {e}")


# ============================================================================
# PYTEST CLI OPTIONS
# ============================================================================


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--auth-url", required=True)
    parser.addoption("--compute-url", required=True)
    parser.addoption("--store-url", required=True)

    parser.addoption("--username")
    parser.addoption("--password")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "admin_only: test requires admin privileges",
    )


# ============================================================================
# SESSION FIXTURES
# ============================================================================


@pytest.fixture(scope="session")
def cli_config(request: pytest.FixtureRequest) -> CliConfig:
    """Parse CLI arguments into Pydantic model."""
    return CliConfig(
        auth_url=str(request.config.getoption("--auth-url")),
        compute_url=str(request.config.getoption("--compute-url")),
        store_url=str(request.config.getoption("--store-url")),
        username=request.config.getoption("--username") or None,
        password=request.config.getoption("--password") or None,
    )


@pytest.fixture(scope="session")
def compute_server_info(cli_config: CliConfig) -> ComputeServerInfo:
    """Query compute server for auth_required and guest_mode flags."""
    info = asyncio.run(get_server_info(cli_config.compute_url))
    return ComputeServerInfo(
        auth_required=info.auth_required,
        guest_mode=(info.guestMode == "on"),
    )


@pytest.fixture(scope="session")
def store_server_info(cli_config: CliConfig) -> StoreServerInfo:
    """Query store server for guestMode flag."""
    info = asyncio.run(get_server_info(cli_config.store_url))
    return StoreServerInfo(
        guest_mode=(info.guestMode == "on"),
    )


@pytest.fixture(scope="session")
def user_info(cli_config: CliConfig) -> UserInfo | None:
    """Query auth API to get current user's admin status and permissions.

    Returns None if running in no-auth mode (no username provided).
    """
    if not cli_config.username:
        return None

    from cl_client.auth_client import AuthClient

    # Username and password are guaranteed to be not None here
    assert cli_config.username is not None
    assert cli_config.password is not None

    async def fetch_user_info():
        auth_client = AuthClient(base_url=cli_config.auth_url)
        try:
            # Login to get token
            assert cli_config.username is not None
            assert cli_config.password is not None
            token_response = await auth_client.login(
                username=cli_config.username,
                password=cli_config.password,
            )

            # Query /users/me endpoint
            user_response = await auth_client.get_current_user(
                token=token_response.access_token
            )

            # Convert to UserInfo Pydantic model
            return UserInfo(
                id=user_response.id,
                username=user_response.username,
                is_admin=user_response.is_admin,
                is_active=user_response.is_active,
                permissions=user_response.permissions,
            )
        finally:
            await auth_client.close()

    return asyncio.run(fetch_user_info())


# ============================================================================
# AUTH CONFIG (CORE OBJECT USED BY TESTS)
# ============================================================================


@pytest.fixture(scope="session")
def auth_config(
    cli_config: CliConfig,
    compute_server_info: ComputeServerInfo,
    store_server_info: StoreServerInfo,
    user_info: UserInfo | None,
) -> AuthConfig:
    """Build complete auth configuration from all sources."""
    has_auth = bool(cli_config.username)

    return AuthConfig(
        mode="auth" if has_auth else "no-auth",
        auth_url=cli_config.auth_url,
        compute_url=cli_config.compute_url,
        store_url=cli_config.store_url,
        compute_auth_required=compute_server_info.auth_required,
        compute_guest_mode=compute_server_info.guest_mode,
        store_guest_mode=store_server_info.guest_mode,
        username=cli_config.username,
        password=cli_config.password,
        user_info=user_info,
    )


# ============================================================================
# CLIENT FIXTURES
# ============================================================================


@pytest.fixture
async def test_client(auth_config: AuthConfig):
    """Create ComputeClient with auth based on config."""
    if not auth_config.username:
        client = ComputeClient(base_url=auth_config.compute_url)
        yield client
        await client.close()
        return

    # Username and password are guaranteed to be not None here
    assert auth_config.username is not None
    assert auth_config.password is not None

    config = ServerConfig(
        auth_url=auth_config.auth_url,
        compute_url=auth_config.compute_url,
        store_url=auth_config.store_url,
    )
    session = SessionManager(server_config=config)

    await session.login(
        auth_config.username,
        auth_config.password,
    )

    client = session.create_compute_client()
    client._auth_session = session  # type: ignore[attr-defined]  # for cleanup / admin calls

    yield client

    await client.close()
    await session.close()


@pytest.fixture
async def client(test_client: ComputeClient) -> ComputeClient:
    """Backward compatibility alias"""
    return test_client


@pytest.fixture
async def store_manager(auth_config: AuthConfig):
    """Create StoreManager with auth based on config."""
    from cl_client.store_manager import StoreManager

    if not auth_config.username:
        mgr = StoreManager.guest(base_url=auth_config.store_url)
        await mgr.__aenter__()
        yield mgr
        await mgr.__aexit__(None, None, None)
        return

    # Username and password are guaranteed to be not None here
    assert auth_config.username is not None
    assert auth_config.password is not None

    config = ServerConfig(
        auth_url=auth_config.auth_url,
        compute_url=auth_config.compute_url,
        store_url=auth_config.store_url,
    )
    session = SessionManager(server_config=config)

    await session.login(
        auth_config.username,
        auth_config.password,
    )

    mgr = session.create_store_manager()
    await mgr.__aenter__()
    mgr._auth_session = session  # type: ignore[attr-defined]

    yield mgr

    await mgr.__aexit__(None, None, None)
    await session.close()


@pytest.fixture
def is_no_auth(auth_config: AuthConfig) -> bool:
    """Check if running in no-auth mode."""
    return not auth_config.username
