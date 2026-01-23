"""Integration test configuration - fixtures and CLI options for integration tests."""

import asyncio
import os

# Import models from parent conftest
import sys
from pathlib import Path
from pathlib import Path as PathlibPath

import httpx
import pytest

from cl_client import ComputeClient, ServerConfig, SessionManager

sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
from conftest import (
    AuthConfig,
    CliConfig,
    ComputeServerInfo,
    ServerRootResponse,
    StoreServerInfo,
    UserInfo,
)

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
# PYTEST CLI OPTIONS (INTEGRATION TESTS ONLY)
# ============================================================================


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add CLI options for integration tests (not required for unit tests)."""
    parser.addoption(
        "--auth-url",
        action="store",
        default=None,
        help="Auth service URL (required for integration tests)"
    )
    parser.addoption(
        "--compute-url",
        action="store",
        default=None,
        help="Compute service URL (required for integration tests)"
    )
    parser.addoption(
        "--store-url",
        action="store",
        default=None,
        help="Store service URL (required for integration tests)"
    )
    parser.addoption(
        "--username",
        action="store",
        default=None,
        help="Username for authenticated integration tests"
    )
    parser.addoption(
        "--password",
        action="store",
        default=None,
        help="Password for authenticated integration tests"
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "admin_only: test requires admin privileges",
    )


# ============================================================================
# SESSION FIXTURES
# ============================================================================


@pytest.fixture(scope="session")
def cli_config(request: pytest.FixtureRequest) -> CliConfig:
    """Parse CLI arguments into Pydantic model.

    Validates that required arguments are provided for integration tests.
    """
    auth_url = request.config.getoption("--auth-url")
    compute_url = request.config.getoption("--compute-url")
    store_url = request.config.getoption("--store-url")

    if not auth_url or not compute_url or not store_url:
        pytest.fail(
            "Integration tests require --auth-url, --compute-url, and --store-url arguments"
        )

    return CliConfig(
        auth_url=str(auth_url),
        compute_url=str(compute_url),
        store_url=str(store_url),
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
        auth_client = AuthClient(base_url=cli_config.auth_url, timeout=60.0)
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


# ============================================================================
# MEDIA FIXTURES
# ============================================================================

# Test vectors base directory (can be overridden via environment variable)
TEST_VECTORS_DIR = Path(
    os.getenv("TEST_VECTORS_DIR", "/Users/anandasarangaram/Work/cl_server_test_media")
)


@pytest.fixture(scope="session")
def media_dir() -> Path:
    """Get media directory path."""
    return TEST_VECTORS_DIR


@pytest.fixture
def test_image(media_dir: Path) -> Path:
    """Get standard test image (HD JPEG)."""
    image_path = media_dir / "images" / "test_image_1920x1080.jpg"
    assert image_path.exists(), f"Test image not found: {image_path}"
    return image_path


@pytest.fixture
def unique_test_image(test_image: Path, tmp_path: Path) -> Path:
    """Create a unique copy of test image to avoid MD5 deduplication."""
    import uuid
    import random
    from .test_utils import create_unique_copy
    
    unique_path = tmp_path / f"unique_{uuid.uuid4().hex}.jpg"
    # Use random offset to ensure uniqueness even if multiple tests call this at once
    create_unique_copy(test_image, unique_path, offset=random.randint(1, 250))
    return unique_path
    

@pytest.fixture
def unique_face_single(media_dir: Path, tmp_path: Path) -> Path:
    """Get a unique copy of the single face test image."""
    from .test_utils import create_unique_copy
    source = media_dir / "images" / "test_face_single.jpg"
    dest = tmp_path / "unique_face_single.jpg"
    create_unique_copy(source, dest)
    return dest


@pytest.fixture
def test_image_png(media_dir: Path) -> Path:
    """Get PNG test image."""
    image_path = media_dir / "images" / "test_image_800x600.png"
    assert image_path.exists(), f"Test image not found: {image_path}"
    return image_path


@pytest.fixture
def test_image_exif(media_dir: Path) -> Path:
    """Get image with rich EXIF data."""
    image_path = media_dir / "images" / "test_exif_rich.jpg"
    assert image_path.exists(), f"Test image not found: {image_path}"
    return image_path


@pytest.fixture
def test_image_face_single() -> Path:
    """Get image with single face."""
    image_path = TEST_VECTORS_DIR / "images" / "test_face_single.jpg"
    assert image_path.exists(), f"Test image not found: {image_path}"
    return image_path


@pytest.fixture
def test_image_face_multiple() -> Path:
    """Get image with multiple faces."""
    image_path = TEST_VECTORS_DIR / "images" / "test_face_multiple.jpg"
    assert image_path.exists(), f"Test image not found: {image_path}"
    return image_path


@pytest.fixture
def test_video_1080p(media_dir: Path) -> Path:
    """Get 1080p test video."""
    video_path = media_dir / "videos" / "test_video_1080p_10s.mp4"
    assert video_path.exists(), f"Test video not found: {video_path}"
    return video_path


@pytest.fixture
def test_video_720p(media_dir: Path) -> Path:
    """Get 720p test video."""
    video_path = media_dir / "videos" / "test_video_720p_5s.mp4"
    assert video_path.exists(), f"Test video not found: {video_path}"
    return video_path


# ============================================================================
# CLEANUP FIXTURES
# ============================================================================


@pytest.fixture(scope="module", autouse=True)
async def cleanup_store_entities(
    request: pytest.FixtureRequest,
    auth_config,  # AuthConfig Pydantic model from parent conftest
):
    """Clean up all store entities before store integration tests run.

    Runs only for test_store_integration.py.
    Uses CLI-provided auth credentials.
    """

    # All integration tests in this folder use the store
    import logging
    logging.info(f"Cleaning up store for module: {request.module.__name__}")

    # Skip cleanup if no auth (cannot delete entities)
    if not auth_config.username:
        yield
        return

    # Bulk cleanup logic
    try:
        username = auth_config.username
        password = auth_config.password
        auth_url = auth_config.auth_url
        store_url = auth_config.store_url

        async with httpx.AsyncClient() as client:
            # Login
            token_resp = await client.post(
                f"{auth_url}/auth/token",
                data={
                    "username": username,
                    "password": password,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=5.0,
            )

            if token_resp.status_code != 200:
                return

            token = token_resp.json()["access_token"]

            # Try bulk delete first (fastest, requires admin)
            bulk_resp = await client.delete(
                f"{store_url}/entities",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )

            if bulk_resp.status_code == 403:
                # Fallback for non-admin: list and delete individually
                # This still clears Qdrant because delete_entity now includes vector cleanup
                resp = await client.get(
                    f"{store_url}/entities?page=1&page_size=100",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5.0,
                )

                if resp.status_code == 200:
                    entities = resp.json().get("items", [])
                    for entity in entities:
                        await client.delete(
                            f"{store_url}/entities/{entity['id']}",
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=5.0,
                        )

    except Exception:
        # Non-fatal cleanup failure
        pass

    yield
