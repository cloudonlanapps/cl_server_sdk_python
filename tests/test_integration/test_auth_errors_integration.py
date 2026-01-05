"""Integration tests for authentication and authorization errors.

These tests verify that the auth system properly rejects:
- Unauthenticated requests (401)
- Unauthorized requests from non-admin users (403)
- Invalid/malformed tokens (401)

NOTE: These tests ONLY run in JWT mode since they test auth behavior.
They are automatically skipped in no-auth mode.
"""

from pathlib import Path

import httpx
import pytest
from cl_client import ComputeClient
from cl_client.session_manager import SessionManager

import sys
from pathlib import Path as PathlibPath
sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
from conftest import get_expected_error, should_succeed


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(test_image: Path, auth_mode: str, auth_config: dict):
    """Test that requests without auth are rejected when auth is enabled.

    This test only runs in JWT mode since it tests auth enforcement.
    In no-auth mode, it's skipped.
    """
    if auth_mode == "no-auth":
        pytest.skip("Test only applies to JWT auth mode")

    # Create client without authentication (no token)
    async with ComputeClient(base_url=str(auth_config["compute_url"])) as client:
        # Try to submit a job without authentication
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.clip_embedding.embed_image(
                image=test_image,
                wait=False,
            )

        # Should get 401 Unauthorized
        assert exc_info.value.response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_token_rejected(test_image: Path, auth_mode: str, auth_config: dict):
    """Test that requests with invalid tokens are rejected.

    This test only runs in JWT mode.
    """
    if auth_mode == "no-auth":
        pytest.skip("Test only applies to JWT auth mode")

    from cl_client.auth import JWTAuthProvider

    # Create client with invalid token
    invalid_auth = JWTAuthProvider(token="invalid.token.here")
    async with ComputeClient(base_url=str(auth_config["compute_url"]), auth_provider=invalid_auth) as client:
        # Try to submit a job with invalid token
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.clip_embedding.embed_image(
                image=test_image,
                wait=False,
            )

        # Should get 401 Unauthorized
        assert exc_info.value.response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_malformed_token_rejected(test_image: Path, auth_mode: str, auth_config: dict):
    """Test that requests with malformed tokens are rejected.

    This test only runs in JWT mode.
    """
    if auth_mode == "no-auth":
        pytest.skip("Test only applies to JWT auth mode")

    from cl_client.auth import JWTAuthProvider

    # Create client with malformed token (not even JWT format)
    malformed_auth = JWTAuthProvider(token="not-a-jwt-token")
    async with ComputeClient(base_url=str(auth_config["compute_url"]), auth_provider=malformed_auth) as client:
        # Try to submit a job with malformed token
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.clip_embedding.embed_image(
                image=test_image,
                wait=False,
            )

        # Should get 401 Unauthorized
        assert exc_info.value.response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_non_admin_user_forbidden_from_admin_endpoints(auth_mode: str, auth_config: dict):
    """Test that non-admin users get 403 Forbidden on admin endpoints.

    This test:
    1. Creates a regular (non-admin) user
    2. Tries to access admin-only endpoints (create_user, list_users, etc.)
    3. Verifies 403 Forbidden is returned

    Only runs in JWT mode (skipped in no-auth mode via @pytest.mark.admin_only).
    """
    if auth_mode == "no_auth":
        pytest.skip("Test only applies to JWT auth mode")

    from cl_client import ServerConfig

    # Create server config with correct URLs
    config = ServerConfig(
        auth_url=str(auth_config["auth_url"]),
        compute_url=str(auth_config["compute_url"]),
    )

    # First, login as admin to create a regular user
    admin_session = SessionManager(server_config=config)
    await admin_session.login("admin", "admin")

    try:
        # Create a non-admin user
        from cl_client.auth_models import UserCreateRequest

        user_create = UserCreateRequest(
            username="testuser_nonadmin",
            password="testpass123",
            is_admin=False,
            is_active=True,
            permissions=["read:jobs"],
        )

        # Create the user
        await admin_session._auth_client.create_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_create=user_create,
        )

        # Now login as the non-admin user
        user_session = SessionManager(server_config=config)
        await user_session.login("testuser_nonadmin", "testpass123")

        try:
            # Try to create another user (admin-only operation)
            new_user = UserCreateRequest(
                username="another_user",
                password="pass123",
                is_admin=False,
                is_active=True,
                permissions=["read:jobs"],
            )

            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await user_session._auth_client.create_user(  # type: ignore[attr-defined]
                    token=user_session.get_token(),
                    user_create=new_user,
                )

            # Should get 403 Forbidden (not enough permissions)
            assert exc_info.value.response.status_code == 403

            # Also test list_users (admin-only)
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await user_session._auth_client.list_users(  # type: ignore[attr-defined]
                    token=user_session.get_token(),
                )

            # Should get 403 Forbidden
            assert exc_info.value.response.status_code == 403

        finally:
            await user_session.close()

            # Cleanup: Delete the test user
            user_id = (await admin_session._auth_client.list_users(  # type: ignore[attr-defined]
                token=admin_session.get_token(),
            ))
            # Find the user we created
            for user in user_id:
                if user.username == "testuser_nonadmin":
                    await admin_session._auth_client.delete_user(  # type: ignore[attr-defined]
                        token=admin_session.get_token(),
                        user_id=user.id,
                    )
                    break

    finally:
        await admin_session.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_expired_token_rejected(auth_mode: str):
    """Test that expired tokens are rejected.

    NOTE: This is difficult to test in integration without waiting 30 minutes
    or modifying server config. This test documents the expected behavior.

    In practice, expired tokens would:
    1. Return 401 Unauthorized
    2. Client should catch this and refresh the token via SessionManager
    """
    if auth_mode == "no_auth":
        pytest.skip("Test only applies to JWT auth mode")

    # This test would require either:
    # 1. Waiting for token expiration (30 min default)
    # 2. Mocking the server clock
    # 3. Configuring server with very short token lifetime
    #
    # For now, we document that SessionManager.get_valid_token()
    # handles this automatically by checking expiry and refreshing
    # when < 60 seconds remain.

    pytest.skip(
        "Expired token test requires server with short token lifetime. "
        "Token refresh is tested in unit tests (test_session_manager.py)."
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_compute_operations_with_valid_auth_succeed(
    test_image: Path,
    client: ComputeClient,
    auth_config: dict,
):
    """Positive test: Verify that properly authenticated requests succeed.

    This ensures our auth setup is working correctly.
    This test only runs in auth modes (skipped in no-auth via conftest logic).
    """
    # Check if user has sufficient permissions
    if should_succeed(auth_config, operation_type="plugin"):
        # Should succeed - run normal assertions
        job = await client.clip_embedding.embed_image(
            image=test_image,
            wait=True,
            timeout=30.0,
        )

        # Verify success
        assert job.status == "completed"
        assert job.task_output is not None

        # Cleanup
        await client.delete_job(job.job_id)
    else:
        # Should fail - verify correct error code
        expected_error = get_expected_error(auth_config, operation_type="plugin")
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.clip_embedding.embed_image(
                image=test_image,
                wait=False,
            )
        assert exc_info.value.response.status_code == expected_error
