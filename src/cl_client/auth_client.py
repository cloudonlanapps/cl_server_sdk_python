"""Low-level client for auth service API.

Provides direct wrappers for all auth service endpoints without lifecycle management.
For high-level auth operations (login, logout, token refresh), use SessionManager instead.
"""

from typing import cast

import httpx

from .auth_models import (
    PublicKeyResponse,
    TokenResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from .server_config import ServerConfig


class AuthClient:
    """Low-level client for auth service REST API.

    Provides direct access to auth service endpoints without lifecycle management.
    All methods are async and return parsed Pydantic models.

    Example:
        # Direct auth client usage
        async with AuthClient(base_url="http://localhost:8000") as auth:
            # Login
            token = await auth.login(username="user", password="pass")
            print(token.access_token)

            # Get current user
            user = await auth.get_current_user(token.access_token)
            print(user.username)
    """

    def __init__(
        self,
        base_url: str | None = None,
        server_config: ServerConfig | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize auth client.

        Args:
            base_url: Auth service URL (overrides server_config.auth_url)
            server_config: Server configuration (default: from environment)
            timeout: Request timeout in seconds
        """
        config = server_config or ServerConfig.from_env()
        self.base_url: str = base_url or config.auth_url
        self.timeout: float = timeout

        self._session: httpx.AsyncClient = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        )

    # ========================================================================
    # Token Management
    # ========================================================================

    async def login(self, username: str, password: str) -> TokenResponse:
        """Login with username and password.

        POST /auth/token

        Args:
            username: User's username
            password: User's password

        Returns:
            TokenResponse with access_token and token_type

        Raises:
            httpx.HTTPStatusError: 401 if credentials invalid, 422 if malformed

        Example:
            token = await client.login(username="user", password="pass")
            print(token.access_token)
        """
        response = await self._session.post(
            "/auth/token",
            data={"username": username, "password": password},
        )
        _ = response.raise_for_status()

        return TokenResponse.model_validate(response.json())

    async def refresh_token(self, token: str) -> TokenResponse:
        """Refresh access token.

        POST /auth/token/refresh

        Args:
            token: Current access token

        Returns:
            TokenResponse with new access_token

        Raises:
            httpx.HTTPStatusError: 401 if token invalid or expired

        Example:
            new_token = await client.refresh_token(token="old_token")
            print(new_token.access_token)
        """
        response = await self._session.post(
            "/auth/token/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        _ = response.raise_for_status()

        return TokenResponse.model_validate(response.json())

    async def get_public_key(self) -> PublicKeyResponse:
        """Get public key for token verification.

        GET /auth/public-key

        Returns:
            PublicKeyResponse with public_key (PEM) and algorithm

        Example:
            key_info = await client.get_public_key()
            print(key_info.algorithm)  # ES256
        """
        response = await self._session.get("/auth/public-key")
        _ = response.raise_for_status()

        return PublicKeyResponse.model_validate(response.json())

    # ========================================================================
    # User Management
    # ========================================================================

    async def get_current_user(self, token: str) -> UserResponse:
        """Get current authenticated user info.

        GET /users/me

        Args:
            token: Access token

        Returns:
            UserResponse with user details

        Raises:
            httpx.HTTPStatusError: 401 if token invalid

        Example:
            user = await client.get_current_user(token="jwt_token")
            print(f"Username: {user.username}, Admin: {user.is_admin}")
        """
        response = await self._session.get(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        _ = response.raise_for_status()

        return UserResponse.model_validate(response.json())

    # ========================================================================
    # Admin User Management
    # ========================================================================

    async def create_user(
        self,
        token: str,
        user_create: UserCreateRequest,
    ) -> UserResponse:
        """Create new user (admin only).

        POST /users/

        Args:
            token: Admin access token
            user_create: User creation request

        Returns:
            UserResponse for created user

        Raises:
            httpx.HTTPStatusError:
                - 401 if not authenticated
                - 403 if not admin
                - 400 if username already exists
                - 422 if invalid request format

        Example:
            request = UserCreateRequest(
                username="newuser",
                password="securepass",
                permissions=["read:jobs", "write:jobs"]
            )
            user = await client.create_user(token="admin_token", user_create=request)
            print(f"Created user: {user.username}")
        """
        # Convert model to form data, converting permissions list to comma-separated string
        form_data = user_create.to_api_payload()

        response = await self._session.post(
            "/users/",
            headers={"Authorization": f"Bearer {token}"},
            data=form_data,
        )
        _ = response.raise_for_status()

        return UserResponse.model_validate(response.json())

    async def list_users(
        self,
        token: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[UserResponse]:
        """List all users (admin only).

        GET /users/?skip={skip}&limit={limit}

        Args:
            token: Admin access token
            skip: Number of users to skip (pagination)
            limit: Maximum number of users to return

        Returns:
            List of UserResponse objects

        Raises:
            httpx.HTTPStatusError:
                - 401 if not authenticated
                - 403 if not admin

        Example:
            users = await client.list_users(token="admin_token", skip=0, limit=10)
            for user in users:
                print(f"User: {user.username}, Admin: {user.is_admin}")
        """
        response = await self._session.get(
            "/users/",
            headers={"Authorization": f"Bearer {token}"},
            params={"skip": skip, "limit": limit},
        )
        _ = response.raise_for_status()

        data = cast(list[object], response.json())
        return [UserResponse.model_validate(item) for item in data]

    async def get_user(self, token: str, user_id: int) -> UserResponse:
        """Get user by ID (admin only).

        GET /users/{user_id}

        Args:
            token: Admin access token
            user_id: User ID to fetch

        Returns:
            UserResponse for requested user

        Raises:
            httpx.HTTPStatusError:
                - 401 if not authenticated
                - 403 if not admin
                - 404 if user not found

        Example:
            user = await client.get_user(token="admin_token", user_id=2)
            print(f"User {user.id}: {user.username}")
        """
        response = await self._session.get(
            f"/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        _ = response.raise_for_status()

        return UserResponse.model_validate(response.json())

    async def update_user(
        self,
        token: str,
        user_id: int,
        user_update: UserUpdateRequest,
    ) -> UserResponse:
        """Update user (admin only).

        PUT /users/{user_id}

        Args:
            token: Admin access token
            user_id: User ID to update
            user_update: Update request (partial updates supported)

        Returns:
            Updated UserResponse

        Raises:
            httpx.HTTPStatusError:
                - 401 if not authenticated
                - 403 if not admin
                - 404 if user not found

        Example:
            update = UserUpdateRequest(
                permissions=["*"],
                is_admin=True
            )
            user = await client.update_user(
                token="admin_token",
                user_id=2,
                user_update=update
            )
            print(f"Updated user: {user.username}, Admin: {user.is_admin}")
        """
        # Only include non-None fields for partial updates
        update_data = user_update.to_api_payload()

        response = await self._session.put(
            f"/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
            data=update_data,
        )
        _ = response.raise_for_status()

        return UserResponse.model_validate(response.json())

    async def delete_user(self, token: str, user_id: int) -> None:
        """Delete user (admin only).

        DELETE /users/{user_id}

        Args:
            token: Admin access token
            user_id: User ID to delete

        Raises:
            httpx.HTTPStatusError:
                - 401 if not authenticated
                - 403 if not admin
                - 404 if user not found

        Example:
            await client.delete_user(token="admin_token", user_id=2)
            print("User deleted successfully")
        """
        response = await self._session.delete(
            f"/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        _ = response.raise_for_status()

    # ========================================================================
    # Cleanup
    # ========================================================================

    async def close(self) -> None:
        """Close HTTP session and cleanup resources."""
        await self._session.aclose()

    async def __aenter__(self) -> "AuthClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Async context manager exit."""
        await self.close()
