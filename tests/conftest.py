"""
Single-user pytest configuration with explicit CLI-driven auth.
"""

import asyncio
from typing import Any, List

import httpx
import pytest
from cl_client import ComputeClient, ServerConfig, SessionManager


# ============================================================================
# SERVER PROBING
# ============================================================================


async def get_server_info(url: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=2.0)
            return r.json()
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

    parser.addoption(
        "--is-admin",
        action="store_true",
        default=False,
        help="Mark user as admin",
    )

    parser.addoption(
        "--permissions",
        default="",
        help="Comma-separated permissions list",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "admin_only: test requires admin privileges",
    )


# ============================================================================
# SESSION FIXTURES
# ============================================================================


@pytest.fixture(scope="session")
def cli_config(request: pytest.FixtureRequest) -> dict[str, Any]:
    permissions = request.config.getoption("--permissions")
    permissions_list: List[str] = (
        [p.strip() for p in permissions.split(",") if p.strip()] if permissions else []
    )

    return {
        "auth_url": request.config.getoption("--auth-url"),
        "compute_url": request.config.getoption("--compute-url"),
        "store_url": request.config.getoption("--store-url"),
        "username": request.config.getoption("--username"),
        "password": request.config.getoption("--password"),
        "is_admin": request.config.getoption("--is-admin"),
        "permissions": permissions_list,
    }


@pytest.fixture(scope="session")
def compute_server_info(cli_config: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(get_server_info(cli_config["compute_url"]))


@pytest.fixture(scope="session")
def store_server_info(cli_config: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(get_server_info(cli_config["store_url"]))


# ============================================================================
# AUTH CONFIG (CORE OBJECT USED BY TESTS)
# ============================================================================


@pytest.fixture
def auth_config(
    cli_config: dict[str, Any],
    compute_server_info: dict[str, Any],
    store_server_info: dict[str, Any],
) -> dict[str, Any]:

    compute_auth_required = compute_server_info.get("auth_required", True)
    store_guest_mode = store_server_info.get("guestMode", "off")

    has_auth = bool(cli_config["username"])

    return {
        "mode": "auth" if has_auth else "no-auth",
        "auth_url": cli_config["auth_url"],
        "compute_url": cli_config["compute_url"],
        "store_url": cli_config["store_url"],
        "compute_auth_required": compute_auth_required,
        "store_guest_mode": store_guest_mode,
        "username": cli_config["username"],
        "password": cli_config["password"],
        "is_admin": cli_config["is_admin"],
        "permissions": cli_config["permissions"],
        "has_permissions": bool(cli_config["permissions"]),
    }


# ============================================================================
# CLIENT FIXTURES
# ============================================================================


@pytest.fixture
async def test_client(auth_config: dict[str, Any]):
    if not auth_config["username"]:
        client = ComputeClient(base_url=auth_config["compute_url"])
        yield client
        await client.close()
        return

    config = ServerConfig(
        auth_url=auth_config["auth_url"],
        compute_url=auth_config["compute_url"],
        store_url=auth_config["store_url"],
    )
    session = SessionManager(server_config=config)

    await session.login(
        auth_config["username"],
        auth_config["password"],
    )

    client = session.create_compute_client()
    client._auth_session = session  # for cleanup / admin calls

    yield client

    await client.close()
    await session.close()


@pytest.fixture
async def client(test_client):
    """Backward compatibility alias"""
    return test_client


@pytest.fixture
async def store_manager(auth_config: dict[str, Any]):
    from cl_client.store_manager import StoreManager

    if not auth_config["username"]:
        mgr = StoreManager.guest(base_url=auth_config["store_url"])
        await mgr.__aenter__()
        yield mgr
        await mgr.__aexit__(None, None, None)
        return

    config = ServerConfig(
        auth_url=auth_config["auth_url"],
        compute_url=auth_config["compute_url"],
        store_url=auth_config["store_url"],
    )
    session = SessionManager(server_config=config)

    await session.login(
        auth_config["username"],
        auth_config["password"],
    )

    mgr = session.create_store_manager()
    await mgr.__aenter__()
    mgr._auth_session = session

    yield mgr

    await mgr.__aexit__(None, None, None)
    await session.close()


@pytest.fixture
def is_no_auth(auth_config):
    return not auth_config["username"]
