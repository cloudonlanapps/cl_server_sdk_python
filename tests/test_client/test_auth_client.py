"""Tests for AuthClient."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from pydantic import ValidationError

from cl_client.auth_client import AuthClient
from cl_client.auth_models import (
    PublicKeyResponse,
    TokenResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from cl_client.server_config import ServerConfig


class TestAuthClientInit:
    """Tests for AuthClient initialization."""

    def test_auth_client_default_config(self):
        """Test AuthClient with default configuration."""
        client = AuthClient()

        assert client.base_url == "http://localhost:8000"
        assert client.timeout == 30.0
        assert client._session is not None
        assert isinstance(client._session, httpx.AsyncClient)

    def test_auth_client_custom_base_url(self):
        """Test AuthClient with custom base_url."""
        client = AuthClient(base_url="https://auth.example.com")

        assert client.base_url == "https://auth.example.com"

    def test_auth_client_custom_server_config(self):
        """Test AuthClient with custom ServerConfig."""
        config = ServerConfig(auth_url="https://custom-auth.example.com")
        client = AuthClient(server_config=config)

        assert client.base_url == "https://custom-auth.example.com"

    def test_auth_client_base_url_overrides_config(self):
        """Test that base_url parameter overrides server_config."""
        config = ServerConfig(auth_url="https://config-auth.example.com")
        client = AuthClient(
            base_url="https://override-auth.example.com",
            server_config=config,
        )

        assert client.base_url == "https://override-auth.example.com"

    def test_auth_client_custom_timeout(self):
        """Test AuthClient with custom timeout."""
        client = AuthClient(timeout=60.0)

        assert client.timeout == 60.0


class TestAuthClientTokenManagement:
    """Tests for AuthClient token management endpoints."""

    @pytest.mark.asyncio
    async def test_login_success(self):
        """Test successful login."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = {
            "access_token": "test_token_abc123",
            "token_type": "bearer",
        }
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            async with AuthClient() as client:
                result = await client.login(username="testuser", password="testpass")

            mock_post.assert_called_once_with(
                "/auth/token",
                data={"username": "testuser", "password": "testpass"},
            )
            assert isinstance(result, TokenResponse)
            assert result.access_token == "test_token_abc123"
            assert result.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=Mock(),
            response=Mock(status_code=401),
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            async with AuthClient() as client:
                with pytest.raises(httpx.HTTPStatusError):
                    await client.login(username="invalid", password="invalid")

    @pytest.mark.asyncio
    async def test_login_invalid_response_type(self):
        """Test login with invalid response type (Pydantic validation)."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = ["not", "a", "dict"]  # Invalid type
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            async with AuthClient() as client:
                with pytest.raises(ValidationError):
                    await client.login(username="testuser", password="testpass")

    @pytest.mark.asyncio
    async def test_refresh_token_success(self):
        """Test successful token refresh."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = {
            "access_token": "new_token_xyz789",
            "token_type": "bearer",
        }
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            async with AuthClient() as client:
                result = await client.refresh_token(token="old_token")

            mock_post.assert_called_once_with(
                "/auth/token/refresh",
                headers={"Authorization": "Bearer old_token"},
            )
            assert isinstance(result, TokenResponse)
            assert result.access_token == "new_token_xyz789"
            assert result.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_token_expired(self):
        """Test token refresh with expired token."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=Mock(),
            response=Mock(status_code=401),
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            async with AuthClient() as client:
                with pytest.raises(httpx.HTTPStatusError):
                    await client.refresh_token(token="expired_token")

    @pytest.mark.asyncio
    async def test_get_public_key_success(self):
        """Test successful public key retrieval."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = {
            "public_key": "-----BEGIN PUBLIC KEY-----\ntest_key\n-----END PUBLIC KEY-----",
            "algorithm": "ES256",
        }
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            async with AuthClient() as client:
                result = await client.get_public_key()

            mock_get.assert_called_once_with("/auth/public-key")
            assert isinstance(result, PublicKeyResponse)
            assert "BEGIN PUBLIC KEY" in result.public_key
            assert result.algorithm == "ES256"


class TestAuthClientUserInfo:
    """Tests for AuthClient user info endpoint."""

    @pytest.mark.asyncio
    async def test_get_current_user_success(self):
        """Test successful get current user."""
        now = datetime.now(UTC)
        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = {
            "id": 1,
            "username": "testuser",
            "is_admin": False,
            "is_active": True,
            "created_at": now.isoformat(),
            "permissions": ["read:jobs", "write:jobs"],
        }
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            async with AuthClient() as client:
                result = await client.get_current_user(token="valid_token")

            mock_get.assert_called_once_with(
                "/users/me",
                headers={"Authorization": "Bearer valid_token"},
            )
            assert isinstance(result, UserResponse)
            assert result.id == 1
            assert result.username == "testuser"
            assert result.is_admin is False
            assert result.permissions == ["read:jobs", "write:jobs"]

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test get current user with invalid token."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=Mock(),
            response=Mock(status_code=401),
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            async with AuthClient() as client:
                with pytest.raises(httpx.HTTPStatusError):
                    await client.get_current_user(token="invalid_token")


class TestAuthClientAdminUserManagement:
    """Tests for AuthClient admin user management endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.admin_only
    async def test_create_user_success(self):
        """Test successful user creation."""
        now = datetime.now(UTC)
        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = {
            "id": 2,
            "username": "newuser",
            "is_admin": False,
            "is_active": True,
            "created_at": now.isoformat(),
            "permissions": ["read:jobs"],
        }
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            user_create = UserCreateRequest(
                username="newuser",
                password="securepass",
                permissions=["read:jobs"],
            )

            async with AuthClient() as client:
                result = await client.create_user(
                    token="admin_token",
                    user_create=user_create,
                )

            # Verify that permissions list is converted to comma-separated string for form data
            expected_data = user_create.model_dump()
            expected_data["permissions"] = "read:jobs"  # List becomes comma-separated string
            mock_post.assert_called_once_with(
                "/users/",
                headers={"Authorization": "Bearer admin_token"},
                data=expected_data,
            )
            assert isinstance(result, UserResponse)
            assert result.username == "newuser"
            assert result.permissions == ["read:jobs"]

    @pytest.mark.asyncio
    @pytest.mark.admin_only
    async def test_create_user_non_admin(self):
        """Test user creation with non-admin token."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden",
            request=Mock(),
            response=Mock(status_code=403),
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            user_create = UserCreateRequest(
                username="newuser",
                password="pass",
            )

            async with AuthClient() as client:
                with pytest.raises(httpx.HTTPStatusError):
                    await client.create_user(
                        token="non_admin_token",
                        user_create=user_create,
                    )

    @pytest.mark.asyncio
    @pytest.mark.admin_only
    async def test_create_user_duplicate_username(self):
        """Test user creation with duplicate username."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400 Bad Request",
            request=Mock(),
            response=Mock(status_code=400),
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            user_create = UserCreateRequest(
                username="existing_user",
                password="pass",
            )

            async with AuthClient() as client:
                with pytest.raises(httpx.HTTPStatusError):
                    await client.create_user(
                        token="admin_token",
                        user_create=user_create,
                    )

    @pytest.mark.asyncio
    @pytest.mark.admin_only
    async def test_list_users_success(self):
        """Test successful user listing."""
        now = datetime.now(UTC)
        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = [
            {
                "id": 1,
                "username": "user1",
                "is_admin": False,
                "is_active": True,
                "created_at": now.isoformat(),
                "permissions": [],
            },
            {
                "id": 2,
                "username": "user2",
                "is_admin": True,
                "is_active": True,
                "created_at": now.isoformat(),
                "permissions": ["*"],
            },
        ]
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            async with AuthClient() as client:
                result = await client.list_users(
                    token="admin_token",
                    skip=0,
                    limit=10,
                )

            mock_get.assert_called_once_with(
                "/users/",
                headers={"Authorization": "Bearer admin_token"},
                params={"skip": 0, "limit": 10},
            )
            assert isinstance(result, list)
            assert len(result) == 2
            assert all(isinstance(u, UserResponse) for u in result)
            assert result[0].username == "user1"
            assert result[1].username == "user2"
            assert result[1].is_admin is True

    @pytest.mark.asyncio
    @pytest.mark.admin_only
    async def test_list_users_non_admin(self):
        """Test user listing with non-admin token."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden",
            request=Mock(),
            response=Mock(status_code=403),
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            async with AuthClient() as client:
                with pytest.raises(httpx.HTTPStatusError):
                    await client.list_users(token="non_admin_token")

    @pytest.mark.asyncio
    @pytest.mark.admin_only
    async def test_list_users_invalid_response_type(self):
        """Test list users with invalid response type (Pydantic validation)."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = {"not": "a list"}  # Invalid type
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            async with AuthClient() as client:
                # Iterating over dict keys, Pydantic will raise ValidationError
                with pytest.raises(ValidationError):
                    await client.list_users(token="admin_token")

    @pytest.mark.asyncio
    @pytest.mark.admin_only
    async def test_get_user_success(self):
        """Test successful get user by ID."""
        now = datetime.now(UTC)
        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = {
            "id": 2,
            "username": "targetuser",
            "is_admin": False,
            "is_active": True,
            "created_at": now.isoformat(),
            "permissions": ["read:jobs", "write:jobs"],
        }
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            async with AuthClient() as client:
                result = await client.get_user(token="admin_token", user_id=2)

            mock_get.assert_called_once_with(
                "/users/2",
                headers={"Authorization": "Bearer admin_token"},
            )
            assert isinstance(result, UserResponse)
            assert result.id == 2
            assert result.username == "targetuser"

    @pytest.mark.asyncio
    @pytest.mark.admin_only
    async def test_get_user_not_found(self):
        """Test get user with non-existent user ID."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=Mock(),
            response=Mock(status_code=404),
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            async with AuthClient() as client:
                with pytest.raises(httpx.HTTPStatusError):
                    await client.get_user(token="admin_token", user_id=999)

    @pytest.mark.asyncio
    @pytest.mark.admin_only
    async def test_update_user_success(self):
        """Test successful user update."""
        now = datetime.now(UTC)
        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = {
            "id": 2,
            "username": "updateduser",
            "is_admin": True,
            "is_active": True,
            "created_at": now.isoformat(),
            "permissions": ["*"],
        }
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "put", new_callable=AsyncMock
        ) as mock_put:
            mock_put.return_value = mock_response

            user_update = UserUpdateRequest(
                permissions=["*"],
                is_admin=True,
            )

            async with AuthClient() as client:
                result = await client.update_user(
                    token="admin_token",
                    user_id=2,
                    user_update=user_update,
                )

            # Verify only non-None fields are included, permissions list converted to string
            expected_data = {"permissions": "*", "is_admin": True}  # List becomes comma-separated string
            mock_put.assert_called_once_with(
                "/users/2",
                headers={"Authorization": "Bearer admin_token"},
                data=expected_data,
            )
            assert isinstance(result, UserResponse)
            assert result.is_admin is True
            assert result.permissions == ["*"]

    @pytest.mark.asyncio
    @pytest.mark.admin_only
    async def test_update_user_partial(self):
        """Test partial user update (only password)."""
        now = datetime.now(UTC)
        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = {
            "id": 2,
            "username": "user",
            "is_admin": False,
            "is_active": True,
            "created_at": now.isoformat(),
            "permissions": [],
        }
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "put", new_callable=AsyncMock
        ) as mock_put:
            mock_put.return_value = mock_response

            user_update = UserUpdateRequest(password="newpassword")

            async with AuthClient() as client:
                result = await client.update_user(
                    token="admin_token",
                    user_id=2,
                    user_update=user_update,
                )

            # Verify only password is included (using form data, not json)
            call_args = mock_put.call_args
            assert call_args[1]["data"] == {"password": "newpassword"}
            assert isinstance(result, UserResponse)

    @pytest.mark.asyncio
    @pytest.mark.admin_only
    async def test_update_user_not_found(self):
        """Test user update with non-existent user ID."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=Mock(),
            response=Mock(status_code=404),
        )

        with patch.object(
            httpx.AsyncClient, "put", new_callable=AsyncMock
        ) as mock_put:
            mock_put.return_value = mock_response

            user_update = UserUpdateRequest(is_active=False)

            async with AuthClient() as client:
                with pytest.raises(httpx.HTTPStatusError):
                    await client.update_user(
                        token="admin_token",
                        user_id=999,
                        user_update=user_update,
                    )

    @pytest.mark.asyncio
    @pytest.mark.admin_only
    async def test_delete_user_success(self):
        """Test successful user deletion."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "delete", new_callable=AsyncMock
        ) as mock_delete:
            mock_delete.return_value = mock_response

            async with AuthClient() as client:
                result = await client.delete_user(token="admin_token", user_id=2)

            mock_delete.assert_called_once_with(
                "/users/2",
                headers={"Authorization": "Bearer admin_token"},
            )
            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.admin_only
    async def test_delete_user_not_found(self):
        """Test user deletion with non-existent user ID."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=Mock(),
            response=Mock(status_code=404),
        )

        with patch.object(
            httpx.AsyncClient, "delete", new_callable=AsyncMock
        ) as mock_delete:
            mock_delete.return_value = mock_response

            async with AuthClient() as client:
                with pytest.raises(httpx.HTTPStatusError):
                    await client.delete_user(token="admin_token", user_id=999)

    @pytest.mark.asyncio
    @pytest.mark.admin_only
    async def test_delete_user_non_admin(self):
        """Test user deletion with non-admin token."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden",
            request=Mock(),
            response=Mock(status_code=403),
        )

        with patch.object(
            httpx.AsyncClient, "delete", new_callable=AsyncMock
        ) as mock_delete:
            mock_delete.return_value = mock_response

            async with AuthClient() as client:
                with pytest.raises(httpx.HTTPStatusError):
                    await client.delete_user(token="non_admin_token", user_id=2)


class TestAuthClientContextManager:
    """Tests for AuthClient async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self):
        """Test async context manager enter and exit."""
        async with AuthClient() as client:
            assert client._session is not None
            assert isinstance(client._session, httpx.AsyncClient)

        # After exit, session should be closed
        # (We can't easily verify this without accessing internals,
        # but we can verify no errors occur)

    @pytest.mark.asyncio
    async def test_manual_close(self):
        """Test manual close method."""
        client = AuthClient()
        assert client._session is not None

        await client.close()

        # Verify no errors occur during close
        # (httpx.AsyncClient.aclose() should complete successfully)
