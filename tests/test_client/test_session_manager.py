"""Tests for SessionManager."""

import base64
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from cl_client.auth import JWTAuthProvider, NoAuthProvider
from cl_client.auth_models import TokenResponse, UserResponse
from cl_client.session_manager import SessionManager


def _create_jwt_token(payload: dict[str, object]) -> str:
    """Helper to create a fake JWT token for testing."""
    header = {"alg": "ES256", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode()
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature_b64 = "fake_signature"
    return f"{header_b64}.{payload_b64}.{signature_b64}"


class TestSessionManagerInitialization:
    """Tests for SessionManager initialization."""

    def test_session_manager_default_config(self):
        """Test SessionManager with default configuration."""
        session = SessionManager()

        assert session._config is not None
        assert session._auth_client is not None
        assert session._current_token is None
        assert session._current_user is None
        assert not session.is_authenticated()

    def test_session_manager_custom_base_url(self):
        """Test SessionManager with custom base_url."""
        session = SessionManager(base_url="https://custom-auth.example.com")

        assert session._auth_client.base_url == "https://custom-auth.example.com"


class TestSessionManagerLoginLogout:
    """Tests for login/logout lifecycle."""

    @pytest.mark.asyncio
    async def test_login_success(self):
        """Test successful login."""
        now = datetime.now(UTC)
        mock_token_response = TokenResponse(
            access_token="test_token_123",
            token_type="bearer",
        )
        mock_user_response = UserResponse(
            id=1,
            username="testuser",
            is_admin=False,
            is_active=True,
            created_at=now,
            permissions=["read:jobs"],
        )

        session = SessionManager()

        with patch.object(
            session._auth_client, "login", new_callable=AsyncMock
        ) as mock_login:
            mock_login.return_value = mock_token_response

            with patch.object(
                session._auth_client, "get_current_user", new_callable=AsyncMock
            ) as mock_get_user:
                mock_get_user.return_value = mock_user_response

                result = await session.login("testuser", "testpass")

                mock_login.assert_called_once_with("testuser", "testpass")
                mock_get_user.assert_called_once_with("test_token_123")

                assert result == mock_token_response
                assert session.is_authenticated()
                assert session._current_token == "test_token_123"
                assert session._current_user == mock_user_response

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        session = SessionManager()

        with patch.object(
            session._auth_client, "login", new_callable=AsyncMock
        ) as mock_login:
            import httpx

            mock_login.side_effect = httpx.HTTPStatusError(
                "401 Unauthorized",
                request=Mock(),
                response=Mock(status_code=401),
            )

            with pytest.raises(httpx.HTTPStatusError):
                await session.login("invalid", "invalid")

            # Session should remain unauthenticated
            assert not session.is_authenticated()
            assert session._current_token is None

    @pytest.mark.asyncio
    async def test_logout(self):
        """Test logout clears session state."""
        now = datetime.now(UTC)
        session = SessionManager()

        # Set up authenticated state
        session._current_token = "test_token"
        session._current_user = UserResponse(
            id=1,
            username="testuser",
            is_admin=False,
            is_active=True,
            created_at=now,
            permissions=[],
        )

        # Logout
        await session.logout()

        assert not session.is_authenticated()
        assert session._current_token is None
        assert session._current_user is None

    @pytest.mark.asyncio
    async def test_is_authenticated(self):
        """Test is_authenticated() returns correct status."""
        session = SessionManager()

        # Initially not authenticated
        assert not session.is_authenticated()

        # After setting token
        session._current_token = "test_token"
        assert session.is_authenticated()

        # After logout
        await session.logout()
        assert not session.is_authenticated()


class TestSessionManagerUserInfo:
    """Tests for user information management."""

    @pytest.mark.asyncio
    async def test_get_current_user_cached(self):
        """Test get_current_user() returns cached user."""
        now = datetime.now(UTC)
        session = SessionManager()

        # Set up authenticated state with cached user
        session._current_token = "test_token"
        session._current_user = UserResponse(
            id=1,
            username="testuser",
            is_admin=False,
            is_active=True,
            created_at=now,
            permissions=["read:jobs"],
        )

        user = await session.get_current_user()

        assert user is not None
        assert user.username == "testuser"
        assert user.permissions == ["read:jobs"]

    @pytest.mark.asyncio
    async def test_get_current_user_fetch_from_server(self):
        """Test get_current_user() fetches from server if not cached."""
        now = datetime.now(UTC)
        session = SessionManager()

        # Set up authenticated state without cached user
        session._current_token = "test_token"
        session._current_user = None

        mock_user_response = UserResponse(
            id=1,
            username="testuser",
            is_admin=False,
            is_active=True,
            created_at=now,
            permissions=["read:jobs"],
        )

        with patch.object(
            session._auth_client, "get_current_user", new_callable=AsyncMock
        ) as mock_get_user:
            mock_get_user.return_value = mock_user_response

            user = await session.get_current_user()

            mock_get_user.assert_called_once_with("test_token")
            assert user == mock_user_response
            assert session._current_user == mock_user_response

    @pytest.mark.asyncio
    async def test_get_current_user_guest_mode(self):
        """Test get_current_user() returns None in guest mode."""
        session = SessionManager()

        # Not authenticated
        assert not session.is_authenticated()

        user = await session.get_current_user()

        assert user is None


class TestSessionManagerTokenManagement:
    """Tests for token management and refresh."""

    def test_get_token_authenticated(self):
        """Test get_token() returns current token."""
        session = SessionManager()
        session._current_token = "test_token_123"

        token = session.get_token()

        assert token == "test_token_123"

    def test_get_token_not_authenticated(self):
        """Test get_token() raises error when not authenticated."""
        session = SessionManager()

        with pytest.raises(ValueError, match="Not authenticated"):
            session.get_token()

    @pytest.mark.asyncio
    async def test_get_valid_token_fresh_token(self):
        """Test get_valid_token() returns token without refresh."""
        # Create token that expires in 5 minutes (fresh)
        expiry_time = datetime.now(UTC) + timedelta(minutes=5)
        exp_timestamp = int(expiry_time.timestamp())
        token = _create_jwt_token({"sub": "user123", "exp": exp_timestamp})

        session = SessionManager()
        session._current_token = token

        result = await session.get_valid_token()

        assert result == token

    @pytest.mark.asyncio
    async def test_get_valid_token_with_refresh(self):
        """Test get_valid_token() refreshes expiring token."""
        # Create token that expires in 30 seconds (needs refresh)
        expiry_time = datetime.now(UTC) + timedelta(seconds=30)
        exp_timestamp = int(expiry_time.timestamp())
        old_token = _create_jwt_token({"sub": "user123", "exp": exp_timestamp})

        # Create new token that expires in 1 hour
        new_expiry = datetime.now(UTC) + timedelta(hours=1)
        new_exp_timestamp = int(new_expiry.timestamp())
        new_token = _create_jwt_token({"sub": "user123", "exp": new_exp_timestamp})

        session = SessionManager()
        session._current_token = old_token

        mock_token_response = TokenResponse(
            access_token=new_token,
            token_type="bearer",
        )

        with patch.object(
            session._auth_client, "refresh_token", new_callable=AsyncMock
        ) as mock_refresh:
            mock_refresh.return_value = mock_token_response

            result = await session.get_valid_token()

            mock_refresh.assert_called_once_with(old_token)
            assert result == new_token
            assert session._current_token == new_token

    @pytest.mark.asyncio
    async def test_get_valid_token_not_authenticated(self):
        """Test get_valid_token() raises error when not authenticated."""
        session = SessionManager()

        with pytest.raises(ValueError, match="Not authenticated"):
            await session.get_valid_token()


class TestSessionManagerComputeClient:
    """Tests for create_compute_client() factory."""

    def test_create_compute_client_authenticated(self):
        """Test create_compute_client() with authenticated session."""
        # Create token that expires in 5 minutes
        expiry_time = datetime.now(UTC) + timedelta(minutes=5)
        exp_timestamp = int(expiry_time.timestamp())
        token = _create_jwt_token({"sub": "user123", "exp": exp_timestamp})

        session = SessionManager()
        session._current_token = token

        client = session.create_compute_client()

        assert client is not None
        assert isinstance(client.auth, JWTAuthProvider)
        assert client.base_url == session._config.compute_url

    def test_create_compute_client_guest_mode(self):
        """Test create_compute_client() in guest mode."""
        session = SessionManager()

        # Not authenticated
        assert not session.is_authenticated()

        client = session.create_compute_client()

        assert client is not None
        assert isinstance(client.auth, NoAuthProvider)
        assert client.base_url == session._config.compute_url

    def test_create_compute_client_uses_config(self):
        """Test SessionManager stores and uses ServerConfig."""
        from cl_client.server_config import ServerConfig

        config = ServerConfig(
            compute_url="https://custom-compute.example.com",
            mqtt_broker="custom-broker",
            mqtt_port=8883,
        )

        session = SessionManager(server_config=config)

        # Verify config is stored
        assert session._config == config
        assert session._config.compute_url == "https://custom-compute.example.com"
        assert session._config.mqtt_broker == "custom-broker"
        assert session._config.mqtt_port == 8883


class TestSessionManagerContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self):
        """Test async context manager enter and exit."""
        async with SessionManager() as session:
            assert session is not None
            assert session._auth_client is not None

        # After exit, resources should be cleaned up
        # (We can't easily verify this without accessing internals)

    @pytest.mark.asyncio
    async def test_manual_close(self):
        """Test manual close method."""
        session = SessionManager()

        with patch.object(
            session._auth_client, "close", new_callable=AsyncMock
        ) as mock_close:
            await session.close()

            mock_close.assert_called_once()


class TestSessionManagerIntegration:
    """Integration tests for SessionManager workflows."""

    @pytest.mark.asyncio
    async def test_full_login_workflow(self):
        """Test complete login workflow with token refresh."""
        now = datetime.now(UTC)

        # Create token that expires soon
        expiry_time = datetime.now(UTC) + timedelta(seconds=30)
        exp_timestamp = int(expiry_time.timestamp())
        initial_token = _create_jwt_token({"sub": "user123", "exp": exp_timestamp})

        # Create refreshed token
        new_expiry = datetime.now(UTC) + timedelta(hours=1)
        new_exp_timestamp = int(new_expiry.timestamp())
        refreshed_token = _create_jwt_token({"sub": "user123", "exp": new_exp_timestamp})

        session = SessionManager()

        # Mock login
        mock_token_response = TokenResponse(
            access_token=initial_token,
            token_type="bearer",
        )
        mock_user_response = UserResponse(
            id=1,
            username="testuser",
            is_admin=False,
            is_active=True,
            created_at=now,
            permissions=["read:jobs"],
        )

        with patch.object(
            session._auth_client, "login", new_callable=AsyncMock
        ) as mock_login:
            mock_login.return_value = mock_token_response

            with patch.object(
                session._auth_client, "get_current_user", new_callable=AsyncMock
            ) as mock_get_user:
                mock_get_user.return_value = mock_user_response

                # Step 1: Login
                await session.login("testuser", "testpass")
                assert session.is_authenticated()

                # Step 2: Get user info
                user = await session.get_current_user()
                assert user.username == "testuser"

                # Step 3: Get valid token (should trigger refresh)
                mock_refresh_response = TokenResponse(
                    access_token=refreshed_token,
                    token_type="bearer",
                )

                with patch.object(
                    session._auth_client, "refresh_token", new_callable=AsyncMock
                ) as mock_refresh:
                    mock_refresh.return_value = mock_refresh_response

                    token = await session.get_valid_token()
                    assert token == refreshed_token

                # Step 4: Create compute client
                client = session.create_compute_client()
                assert isinstance(client.auth, JWTAuthProvider)

                # Step 5: Logout
                await session.logout()
                assert not session.is_authenticated()
