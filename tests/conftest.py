"""Shared fixtures for all tests - auth parametrization."""

import os
from typing import Any, AsyncGenerator, cast

import pytest
from cl_client.compute_client import ComputeClient
from cl_client.session_manager import SessionManager


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "admin_only: mark test as requiring admin permissions (skipped in no-auth mode)",
    )


@pytest.fixture(params=["no_auth", "jwt"], scope="session")
def auth_mode(request: pytest.FixtureRequest) -> str:
    """Parametrize tests to run in both no-auth and JWT modes.

    Skip JWT mode if AUTH_DISABLED=true environment variable is set.

    Returns:
        "no_auth" or "jwt"
    """
    mode = cast(str, request.param)

    # Skip JWT tests if auth is disabled
    if mode == "jwt" and os.getenv("AUTH_DISABLED", "false").lower() == "true":
        pytest.skip("JWT auth tests disabled (AUTH_DISABLED=true)")

    return mode


@pytest.fixture
async def authenticated_session(
    auth_mode: str,
) -> AsyncGenerator[SessionManager | None, None]:
    """Create authenticated session for JWT mode.

    Returns:
        SessionManager (authenticated) for JWT mode
        None for no-auth mode

    Environment Variables:
        TEST_USERNAME: Username for test authentication (required for JWT mode)
        TEST_PASSWORD: Password for test authentication (required for JWT mode)
    """
    if auth_mode == "no_auth":
        yield None
        return

    # JWT mode - create and login SessionManager
    username = os.getenv("TEST_USERNAME")
    password = os.getenv("TEST_PASSWORD")

    if not username or not password:
        pytest.skip(
            "JWT mode requires TEST_USERNAME and TEST_PASSWORD environment variables"
        )

    session = SessionManager()
    try:
        await session.login(username, password)
        yield session
    finally:
        await session.close()


@pytest.fixture
async def client(
    auth_mode: str,
    authenticated_session: SessionManager | None,
) -> AsyncGenerator[ComputeClient, None]:
    """Create ComputeClient based on auth mode.

    Args:
        auth_mode: "no_auth" or "jwt"
        authenticated_session: SessionManager (JWT) or None (no-auth)

    Returns:
        ComputeClient configured for the appropriate auth mode
    """
    if auth_mode == "no_auth":
        # No-auth mode: create client directly
        client_instance = ComputeClient()
        try:
            yield client_instance
        finally:
            await client_instance.close()
    else:
        # JWT mode: get client from session
        assert authenticated_session is not None
        client_instance = authenticated_session.create_compute_client()
        try:
            yield client_instance
        finally:
            await client_instance.close()


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip admin-only tests in no-auth mode.

    Tests marked with @pytest.mark.admin_only will be skipped when
    running in no-auth mode since admin operations require authentication.
    """
    for item in items:
        # Check if test is marked as admin_only
        if "admin_only" in item.keywords:
            # Check if test is parametrized with auth_mode
            try:
                # Try to access parametrized callspec - only exists on parametrized tests
                # Type ignored: pytest internals not fully typed
                callspec: Any = getattr(item, "callspec")  # type: ignore[misc]
                params: dict[str, Any] = cast(dict[str, Any], callspec.params)
                if "auth_mode" in params:
                    mode = cast(str, params["auth_mode"])
                    if mode == "no_auth":
                        # Skip admin tests in no-auth mode
                        item.add_marker(
                            pytest.mark.skip(
                                reason="Admin operations require authentication (no-auth mode)"
                            )
                        )
            except AttributeError:
                # Test is not parametrized, skip the check
                pass
