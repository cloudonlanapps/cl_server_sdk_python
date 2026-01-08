"""Integration tests for user management operations.

These tests verify admin user CRUD operations:
- Create user
- List users
- Get user
- Update user
- Delete user

NOTE: These tests test admin operations. They run in all auth modes but expect
different outcomes based on whether the user has admin permissions:
- Admin mode: Operations succeed
- Non-admin modes: Operations fail with 403 Forbidden
- No-auth mode: Tests are skipped
"""

from typing import Any

import httpx
import pytest
from cl_client import ServerConfig
from cl_client.auth_models import UserCreateRequest, UserUpdateRequest
from cl_client.session_manager import SessionManager

import sys
from pathlib import Path as PathlibPath

sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
from conftest import get_expected_error, should_succeed


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_create_user_success(auth_config: dict[str, Any], is_no_auth: bool):
    """Test admin user creation endpoint.

    In no-auth mode: Verify auth service rejects unauthenticated requests (401)
    In JWT mode: Verify admin can create users, non-admin gets 403
    """
    # Create session with credentials from auth_config
    config = ServerConfig(
        auth_url=str(auth_config["auth_url"]),
        compute_url=str(auth_config["compute_url"]),
    )
    session = SessionManager(server_config=config)

    # In no-auth mode, verify auth service rejects unauthenticated admin requests
    if is_no_auth:
        # Try to access admin endpoint without valid auth
        auth_url = str(auth_config["auth_url"])
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{auth_url}/users/",
                json={
                    "username": "test_new_user",
                    "password": "password123",
                    "is_admin": False,
                    "is_active": True,
                    "permissions": ["read:jobs"],
                },
            )
            # Auth service always requires auth - should get 401
            assert response.status_code == 401
        await session.close()
        return  # Test passes - verified auth service security

    await session.login(
        str(auth_config["username"]),
        str(auth_config["password"]),
    )

    try:
        user_create = UserCreateRequest(
            username="test_new_user",
            password="password123",
            is_admin=False,
            is_active=True,
            permissions=["read:jobs"],
        )

        if should_succeed(auth_config, operation_type="admin"):
            # Should succeed - admin user
            user = await session._auth_client.create_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_create=user_create,
            )

            # Verify user created
            assert user.username == "test_new_user"
            assert user.is_admin is False
            assert user.is_active is True
            assert user.permissions == ["read:jobs"]
            assert user.id is not None

            # Cleanup
            await session._auth_client.delete_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_id=user.id,
            )
        else:
            # Should fail - non-admin user
            expected_code = get_expected_error(auth_config, operation_type="admin")
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await session._auth_client.create_user(  # type: ignore[attr-defined]
                    token=session.get_token(),
                    user_create=user_create,
                )
            assert exc_info.value.response.status_code == expected_code

    finally:
        await session.close()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_list_users_success(auth_config: dict[str, Any], is_no_auth: bool):
    """Test admin list users endpoint.

    In no-auth mode: Verify auth service rejects unauthenticated requests (401)
    In JWT mode: Verify admin can list users, non-admin gets 403
    """
    config = ServerConfig(
        auth_url=str(auth_config["auth_url"]),
        compute_url=str(auth_config["compute_url"]),
    )
    session = SessionManager(server_config=config)

    # In no-auth mode, verify auth service rejects unauthenticated admin requests
    if is_no_auth:
        # Try to access admin endpoint without valid auth
        auth_url = str(auth_config["auth_url"])
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{auth_url}/users/")
            # Auth service always requires auth - should get 401
            assert response.status_code == 401
        await session.close()
        return  # Test passes - verified auth service security

    await session.login(
        str(auth_config["username"]),
        str(auth_config["password"]),
    )

    try:
        if should_succeed(auth_config, operation_type="admin"):
            # Should succeed - admin user
            users = await session._auth_client.list_users(  # type: ignore[attr-defined]
                token=session.get_token(),
            )

            # Verify results
            assert isinstance(users, list)
            assert len(users) > 0  # At least admin user exists

            # Find admin user
            admin_user = next((u for u in users if u.username == "admin"), None)
            assert admin_user is not None
            assert admin_user.is_admin is True
        else:
            # Should fail - non-admin user
            expected_code = get_expected_error(auth_config, operation_type="admin")
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await session._auth_client.list_users(  # type: ignore[attr-defined]
                    token=session.get_token(),
                )
            assert exc_info.value.response.status_code == expected_code

    finally:
        await session.close()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_get_user_success(auth_config: dict[str, Any], is_no_auth: bool):
    """Test admin get user endpoint.

    In no-auth mode: Verify auth service rejects unauthenticated requests (401)
    In JWT mode: Verify admin can get users, non-admin gets 403
    """
    config = ServerConfig(
        auth_url=str(auth_config["auth_url"]),
        compute_url=str(auth_config["compute_url"]),
    )
    session = SessionManager(server_config=config)

    # In no-auth mode, verify auth service rejects unauthenticated admin requests
    if is_no_auth:
        # Try to access admin endpoint without valid auth
        auth_url = str(auth_config["auth_url"])
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{auth_url}/users/1")
            # Auth service always requires auth - should get 401
            assert response.status_code == 401
        await session.close()
        return  # Test passes - verified auth service security

    await session.login(
        str(auth_config["username"]),
        str(auth_config["password"]),
    )

    try:
        if should_succeed(auth_config, operation_type="admin"):
            # Should succeed - admin user
            # First create a user to get
            user_create = UserCreateRequest(
                username="test_get_user",
                password="password123",
                is_admin=False,
                is_active=True,
                permissions=["read:jobs", "write:jobs"],
            )

            created_user = await session._auth_client.create_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_create=user_create,
            )

            # Get the user
            fetched_user = await session._auth_client.get_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_id=created_user.id,
            )

            # Verify
            assert fetched_user.id == created_user.id
            assert fetched_user.username == "test_get_user"
            assert fetched_user.is_admin is False
            assert fetched_user.is_active is True
            assert isinstance(fetched_user.permissions, list)
            assert len(fetched_user.permissions) > 0

            # Cleanup
            await session._auth_client.delete_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_id=created_user.id,
            )
        else:
            # Should fail - non-admin user trying to get any user
            # We need a user_id to test with, so we'll use a fake one
            expected_code = get_expected_error(auth_config, operation_type="admin")
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await session._auth_client.get_user(  # type: ignore[attr-defined]
                    token=session.get_token(),
                    user_id=1,  # Fake user_id
                )
            assert exc_info.value.response.status_code == expected_code

    finally:
        await session.close()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_update_user_permissions(auth_config: dict[str, Any], is_no_auth: bool):
    """Test admin update user permissions endpoint.

    In no-auth mode: Verify auth service rejects unauthenticated requests (401)
    In JWT mode: Verify admin can update permissions, non-admin gets 403
    """
    config = ServerConfig(
        auth_url=str(auth_config["auth_url"]),
        compute_url=str(auth_config["compute_url"]),
    )
    session = SessionManager(server_config=config)

    # In no-auth mode, verify auth service rejects unauthenticated admin requests
    if is_no_auth:
        # Try to access admin endpoint without valid auth
        auth_url = str(auth_config["auth_url"])
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{auth_url}/users/1",
                json={"permissions": ["read:jobs"]},
            )
            # Auth service always requires auth - should get 401
            assert response.status_code == 401
        await session.close()
        return  # Test passes - verified auth service security

    await session.login(
        str(auth_config["username"]),
        str(auth_config["password"]),
    )

    try:
        if should_succeed(auth_config, operation_type="admin"):
            # Should succeed - admin user
            # Create user
            user_create = UserCreateRequest(
                username="test_update_user",
                password="password123",
                is_admin=False,
                is_active=True,
                permissions=["read:jobs"],
            )

            created_user = await session._auth_client.create_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_create=user_create,
            )

            # Update permissions
            user_update = UserUpdateRequest(
                permissions=["read:jobs", "write:jobs", "admin"],
            )

            updated_user = await session._auth_client.update_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_id=created_user.id,
                user_update=user_update,
            )

            # Verify update
            assert updated_user.id == created_user.id
            assert set(updated_user.permissions) == {"read:jobs", "write:jobs", "admin"}

            # Cleanup
            await session._auth_client.delete_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_id=created_user.id,
            )
        else:
            # Should fail - non-admin user
            expected_code = get_expected_error(auth_config, operation_type="admin")
            user_update = UserUpdateRequest(permissions=["read:jobs"])
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await session._auth_client.update_user(  # type: ignore[attr-defined]
                    token=session.get_token(),
                    user_id=1,  # Fake user_id
                    user_update=user_update,
                )
            assert exc_info.value.response.status_code == expected_code

    finally:
        await session.close()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_update_user_password(auth_config: dict[str, Any], is_no_auth: bool):
    """Test admin update user password endpoint.

    In no-auth mode: Verify auth service rejects unauthenticated requests (401)
    In JWT mode: Verify admin can update password, non-admin gets 403
    """
    config = ServerConfig(
        auth_url=str(auth_config["auth_url"]),
        compute_url=str(auth_config["compute_url"]),
    )
    session = SessionManager(server_config=config)

    # In no-auth mode, verify auth service rejects unauthenticated admin requests
    if is_no_auth:
        # Try to access admin endpoint without valid auth
        auth_url = str(auth_config["auth_url"])
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{auth_url}/users/1",
                json={"password": "newpassword"},
            )
            # Auth service always requires auth - should get 401
            assert response.status_code == 401
        await session.close()
        return  # Test passes - verified auth service security

    await session.login(
        str(auth_config["username"]),
        str(auth_config["password"]),
    )

    try:
        if should_succeed(auth_config, operation_type="admin"):
            # Should succeed - admin user
            # Create user
            user_create = UserCreateRequest(
                username="test_password_user",
                password="oldpassword123",
                is_admin=False,
                is_active=True,
                permissions=["read:jobs"],
            )

            created_user = await session._auth_client.create_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_create=user_create,
            )

            # Update password
            user_update = UserUpdateRequest(
                password="newpassword456",
            )

            await session._auth_client.update_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_id=created_user.id,
                user_update=user_update,
            )

            # Try to login with new password
            user_session = SessionManager(server_config=config)
            await user_session.login("test_password_user", "newpassword456")

            # Verify login succeeded
            assert user_session.is_authenticated()

            # Cleanup
            await user_session.close()
            await session._auth_client.delete_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_id=created_user.id,
            )
        else:
            # Should fail - non-admin user
            expected_code = get_expected_error(auth_config, operation_type="admin")
            user_update = UserUpdateRequest(password="newpassword")
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await session._auth_client.update_user(  # type: ignore[attr-defined]
                    token=session.get_token(),
                    user_id=1,  # Fake user_id
                    user_update=user_update,
                )
            assert exc_info.value.response.status_code == expected_code

    finally:
        await session.close()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_update_user_active_status(auth_config: dict[str, Any], is_no_auth: bool):
    """Test admin update user active status endpoint.

    In no-auth mode: Verify auth service rejects unauthenticated requests (401)
    In JWT mode: Verify admin can update status, non-admin gets 403
    """
    config = ServerConfig(
        auth_url=str(auth_config["auth_url"]),
        compute_url=str(auth_config["compute_url"]),
    )
    session = SessionManager(server_config=config)

    # In no-auth mode, verify auth service rejects unauthenticated admin requests
    if is_no_auth:
        # Try to access admin endpoint without valid auth
        auth_url = str(auth_config["auth_url"])
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{auth_url}/users/1",
                json={"is_active": False},
            )
            # Auth service always requires auth - should get 401
            assert response.status_code == 401
        await session.close()
        return  # Test passes - verified auth service security

    await session.login(
        str(auth_config["username"]),
        str(auth_config["password"]),
    )

    try:
        if should_succeed(auth_config, operation_type="admin"):
            # Should succeed - admin user
            # Create active user
            user_create = UserCreateRequest(
                username="test_active_user",
                password="password123",
                is_admin=False,
                is_active=True,
                permissions=["read:jobs"],
            )

            created_user = await session._auth_client.create_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_create=user_create,
            )

            # Deactivate user
            user_update = UserUpdateRequest(
                is_active=False,
            )

            updated_user = await session._auth_client.update_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_id=created_user.id,
                user_update=user_update,
            )

            # Verify deactivated
            assert updated_user.is_active is False

            # Cleanup
            await session._auth_client.delete_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_id=created_user.id,
            )
        else:
            # Should fail - non-admin user
            expected_code = get_expected_error(auth_config, operation_type="admin")
            user_update = UserUpdateRequest(is_active=False)
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await session._auth_client.update_user(  # type: ignore[attr-defined]
                    token=session.get_token(),
                    user_id=1,  # Fake user_id
                    user_update=user_update,
                )
            assert exc_info.value.response.status_code == expected_code

    finally:
        await session.close()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_delete_user_success(auth_config: dict[str, Any], is_no_auth: bool):
    """Test admin delete user endpoint.

    In no-auth mode: Verify auth service rejects unauthenticated requests (401)
    In JWT mode: Verify admin can delete users, non-admin gets 403
    """
    config = ServerConfig(
        auth_url=str(auth_config["auth_url"]),
        compute_url=str(auth_config["compute_url"]),
    )
    session = SessionManager(server_config=config)

    # In no-auth mode, verify auth service rejects unauthenticated admin requests
    if is_no_auth:
        # Try to access admin endpoint without valid auth
        auth_url = str(auth_config["auth_url"])
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{auth_url}/users/1")
            # Auth service always requires auth - should get 401
            assert response.status_code == 401
        await session.close()
        return  # Test passes - verified auth service security

    await session.login(
        str(auth_config["username"]),
        str(auth_config["password"]),
    )

    try:
        if should_succeed(auth_config, operation_type="admin"):
            # Should succeed - admin user
            # Create user to delete
            user_create = UserCreateRequest(
                username="test_delete_user",
                password="password123",
                is_admin=False,
                is_active=True,
                permissions=["read:jobs"],
            )

            created_user = await session._auth_client.create_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_create=user_create,
            )

            user_id = created_user.id

            # Delete user
            await session._auth_client.delete_user(  # type: ignore[attr-defined]
                token=session.get_token(),
                user_id=user_id,
            )

            # Verify user no longer exists
            users = await session._auth_client.list_users(  # type: ignore[attr-defined]
                token=session.get_token(),
            )

            deleted_user = next((u for u in users if u.id == user_id), None)
            assert deleted_user is None, "User should be deleted"
        else:
            # Should fail - non-admin user
            expected_code = get_expected_error(auth_config, operation_type="admin")
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await session._auth_client.delete_user(  # type: ignore[attr-defined]
                    token=session.get_token(),
                    user_id=1,  # Fake user_id
                )
            assert exc_info.value.response.status_code == expected_code

    finally:
        await session.close()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_list_users_with_pagination(
    auth_config: dict[str, Any], is_no_auth: bool
):
    """Test admin list users pagination endpoint.

    In no-auth mode: Verify auth service rejects unauthenticated requests (401)
    In JWT mode: Verify admin can paginate users, non-admin gets 403
    """
    config = ServerConfig(
        auth_url=str(auth_config["auth_url"]),
        compute_url=str(auth_config["compute_url"]),
    )
    session = SessionManager(server_config=config)

    # In no-auth mode, verify auth service rejects unauthenticated admin requests
    if is_no_auth:
        # Try to access admin endpoint without valid auth
        auth_url = str(auth_config["auth_url"])
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{auth_url}/users/?skip=0&limit=3")
            # Auth service always requires auth - should get 401
            assert response.status_code == 401
        await session.close()
        return  # Test passes - verified auth service security

    await session.login(
        str(auth_config["username"]),
        str(auth_config["password"]),
    )

    try:
        if should_succeed(auth_config, operation_type="admin"):
            # Should succeed - admin user
            # Create multiple users
            created_users = []
            for i in range(5):
                user_create = UserCreateRequest(
                    username=f"test_pagination_{i}",
                    password="password123",
                    is_admin=False,
                    is_active=True,
                    permissions=["read:jobs"],
                )

                user = await session._auth_client.create_user(  # type: ignore[attr-defined]
                    token=session.get_token(),
                    user_create=user_create,
                )
                created_users.append(user)

            # Test pagination
            page1 = await session._auth_client.list_users(  # type: ignore[attr-defined]
                token=session.get_token(),
                skip=0,
                limit=3,
            )

            page2 = await session._auth_client.list_users(  # type: ignore[attr-defined]
                token=session.get_token(),
                skip=3,
                limit=3,
            )

            # Verify pagination works
            assert len(page1) == 3
            assert len(page2) >= 2  # At least 2 more users

            # Cleanup
            for user in created_users:
                await session._auth_client.delete_user(  # type: ignore[attr-defined]
                    token=session.get_token(),
                    user_id=user.id,
                )
        else:
            # Should fail - non-admin user
            expected_code = get_expected_error(auth_config, operation_type="admin")
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await session._auth_client.list_users(  # type: ignore[attr-defined]
                    token=session.get_token(),
                    skip=0,
                    limit=3,
                )
            assert exc_info.value.response.status_code == expected_code

    finally:
        await session.close()
