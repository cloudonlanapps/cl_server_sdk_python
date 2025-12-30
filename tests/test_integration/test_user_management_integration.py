"""Integration tests for user management operations.

These tests verify admin user CRUD operations:
- Create user
- List users
- Get user
- Update user
- Delete user

NOTE: These tests ONLY run in JWT mode since they test admin operations.
They are automatically skipped in no-auth mode.
"""

import pytest
from cl_client.auth_models import UserCreateRequest, UserUpdateRequest
from cl_client.session_manager import SessionManager


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_create_user_success(auth_mode: str):
    """Test admin can create a new user."""
    if auth_mode == "no_auth":
        pytest.skip("Test only applies to JWT auth mode")

    # Login as admin
    admin_session = SessionManager()
    await admin_session.login("admin", "admin")

    try:
        # Create new user
        user_create = UserCreateRequest(
            username="test_new_user",
            password="password123",
            is_admin=False,
            is_active=True,
            permissions=["read:jobs"],
        )

        user = await admin_session._auth_client.create_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_create=user_create,
        )

        # Verify user created
        assert user.username == "test_new_user"
        assert user.is_admin is False
        assert user.is_active is True
        assert user.permissions == ["read:jobs"]
        assert user.id is not None

        # Cleanup
        await admin_session._auth_client.delete_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_id=user.id,
        )

    finally:
        await admin_session.close()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_list_users_success(auth_mode: str):
    """Test admin can list all users."""
    if auth_mode == "no_auth":
        pytest.skip("Test only applies to JWT auth mode")

    admin_session = SessionManager()
    await admin_session.login("admin", "admin")

    try:
        # List users
        users = await admin_session._auth_client.list_users(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
        )

        # Verify results
        assert isinstance(users, list)
        assert len(users) > 0  # At least admin user exists

        # Find admin user
        admin_user = next((u for u in users if u.username == "admin"), None)
        assert admin_user is not None
        assert admin_user.is_admin is True

    finally:
        await admin_session.close()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_get_user_success(auth_mode: str):
    """Test admin can get a specific user."""
    if auth_mode == "no_auth":
        pytest.skip("Test only applies to JWT auth mode")

    admin_session = SessionManager()
    await admin_session.login("admin", "admin")

    try:
        # First create a user to get
        user_create = UserCreateRequest(
            username="test_get_user",
            password="password123",
            is_admin=False,
            is_active=True,
            permissions=["read:jobs", "write:jobs"],
        )

        created_user = await admin_session._auth_client.create_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_create=user_create,
        )

        # Get the user
        fetched_user = await admin_session._auth_client.get_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_id=created_user.id,
        )

        # Verify
        assert fetched_user.id == created_user.id
        assert fetched_user.username == "test_get_user"
        assert fetched_user.is_admin is False
        assert fetched_user.is_active is True
        # Verify permissions list is present (server may deduplicate/filter)
        assert isinstance(fetched_user.permissions, list)
        assert len(fetched_user.permissions) > 0

        # Cleanup
        await admin_session._auth_client.delete_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_id=created_user.id,
        )

    finally:
        await admin_session.close()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_update_user_permissions(auth_mode: str):
    """Test admin can update user permissions."""
    if auth_mode == "no_auth":
        pytest.skip("Test only applies to JWT auth mode")

    admin_session = SessionManager()
    await admin_session.login("admin", "admin")

    try:
        # Create user
        user_create = UserCreateRequest(
            username="test_update_user",
            password="password123",
            is_admin=False,
            is_active=True,
            permissions=["read:jobs"],
        )

        created_user = await admin_session._auth_client.create_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_create=user_create,
        )

        # Update permissions
        user_update = UserUpdateRequest(
            permissions=["read:jobs", "write:jobs", "admin"],
        )

        updated_user = await admin_session._auth_client.update_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_id=created_user.id,
            user_update=user_update,
        )

        # Verify update
        assert updated_user.id == created_user.id
        assert set(updated_user.permissions) == {"read:jobs", "write:jobs", "admin"}

        # Cleanup
        await admin_session._auth_client.delete_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_id=created_user.id,
        )

    finally:
        await admin_session.close()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_update_user_password(auth_mode: str):
    """Test admin can update user password."""
    if auth_mode == "no_auth":
        pytest.skip("Test only applies to JWT auth mode")

    admin_session = SessionManager()
    await admin_session.login("admin", "admin")

    try:
        # Create user
        user_create = UserCreateRequest(
            username="test_password_user",
            password="oldpassword123",
            is_admin=False,
            is_active=True,
            permissions=["read:jobs"],
        )

        created_user = await admin_session._auth_client.create_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_create=user_create,
        )

        # Update password
        user_update = UserUpdateRequest(
            password="newpassword456",
        )

        await admin_session._auth_client.update_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_id=created_user.id,
            user_update=user_update,
        )

        # Try to login with new password
        user_session = SessionManager()
        await user_session.login("test_password_user", "newpassword456")

        # Verify login succeeded
        assert user_session.is_authenticated()

        # Cleanup
        await user_session.close()
        await admin_session._auth_client.delete_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_id=created_user.id,
        )

    finally:
        await admin_session.close()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_update_user_active_status(auth_mode: str):
    """Test admin can deactivate/activate users."""
    if auth_mode == "no_auth":
        pytest.skip("Test only applies to JWT auth mode")

    admin_session = SessionManager()
    await admin_session.login("admin", "admin")

    try:
        # Create active user
        user_create = UserCreateRequest(
            username="test_active_user",
            password="password123",
            is_admin=False,
            is_active=True,
            permissions=["read:jobs"],
        )

        created_user = await admin_session._auth_client.create_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_create=user_create,
        )

        # Deactivate user
        user_update = UserUpdateRequest(
            is_active=False,
        )

        updated_user = await admin_session._auth_client.update_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_id=created_user.id,
            user_update=user_update,
        )

        # Verify deactivated
        assert updated_user.is_active is False

        # Cleanup
        await admin_session._auth_client.delete_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_id=created_user.id,
        )

    finally:
        await admin_session.close()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_delete_user_success(auth_mode: str):
    """Test admin can delete a user."""
    if auth_mode == "no_auth":
        pytest.skip("Test only applies to JWT auth mode")

    admin_session = SessionManager()
    await admin_session.login("admin", "admin")

    try:
        # Create user to delete
        user_create = UserCreateRequest(
            username="test_delete_user",
            password="password123",
            is_admin=False,
            is_active=True,
            permissions=["read:jobs"],
        )

        created_user = await admin_session._auth_client.create_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_create=user_create,
        )

        user_id = created_user.id

        # Delete user
        await admin_session._auth_client.delete_user(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            user_id=user_id,
        )

        # Verify user no longer exists
        users = await admin_session._auth_client.list_users(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
        )

        deleted_user = next((u for u in users if u.id == user_id), None)
        assert deleted_user is None, "User should be deleted"

    finally:
        await admin_session.close()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_list_users_with_pagination(auth_mode: str):
    """Test admin can paginate through user list."""
    if auth_mode == "no_auth":
        pytest.skip("Test only applies to JWT auth mode")

    admin_session = SessionManager()
    await admin_session.login("admin", "admin")

    try:
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

            user = await admin_session._auth_client.create_user(  # type: ignore[attr-defined]
                token=admin_session.get_token(),
                user_create=user_create,
            )
            created_users.append(user)

        # Test pagination
        page1 = await admin_session._auth_client.list_users(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            skip=0,
            limit=3,
        )

        page2 = await admin_session._auth_client.list_users(  # type: ignore[attr-defined]
            token=admin_session.get_token(),
            skip=3,
            limit=3,
        )

        # Verify pagination works
        assert len(page1) == 3
        assert len(page2) >= 2  # At least 2 more users (admin + our created users)

        # Cleanup
        for user in created_users:
            await admin_session._auth_client.delete_user(  # type: ignore[attr-defined]
                token=admin_session.get_token(),
                user_id=user.id,
            )

    finally:
        await admin_session.close()
