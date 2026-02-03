"""High-level session management for authentication.

SessionManager provides a facade for common auth operations:
- Login/logout lifecycle
- Automatic token refresh (< 60 seconds before expiry)
- User information management
- Pre-configured ComputeClient creation

Use SessionManager for high-level auth operations. For low-level access
to auth endpoints, use AuthClient directly.
"""

from typing import TYPE_CHECKING

from .auth import JWTAuthProvider, NoAuthProvider
from .auth_client import AuthClient
from .auth_models import TokenResponse, UserResponse
from .config import ComputeClientConfig
from .server_pref import ServerPref

if TYPE_CHECKING:
    from .compute_client import ComputeClient
    from .store_manager import StoreManager


class SessionManager:
    """High-level session management for authentication.

    Provides login/logout, automatic token refresh, and ComputeClient factory.
    Matches Dart SDK SessionManager API for consistency across client libraries.

    Token refresh is automatic: when get_valid_token() is called and the token
    has < 60 seconds until expiry, it will be refreshed transparently.

    Example (Basic usage):
        async with SessionManager() as session:
            # Login
            await session.login(username="user", password="pass")

            # Check authentication
            if session.is_authenticated():
                print(f"Logged in as: {session.get_current_user().username}")

            # Create pre-configured compute client
            client = session.create_compute_client()
            # ... use client ...

            # Logout
            await session.logout()

    Example (Automatic token refresh):
        session = SessionManager()
        await session.login("user", "pass")

        # Token automatically refreshed if < 60 seconds until expiry
        token = await session.get_valid_token()

        # Use token for API calls
        # ...

    Example (Guest mode):
        session = SessionManager()
        # No login - operates in guest mode
        client = session.create_compute_client()
        # Client uses NoAuthProvider
    """

    def __init__(
        self,
        base_url: str | None = None,
        server_pref: ServerPref | None = None,
    ) -> None:
        """Initialize session manager.

        Args:
            base_url: Auth service URL (overrides server_pref.auth_url)
            server_pref: Server configuration (default: from environment)
        """
        self._config: ServerPref = server_pref or ServerPref.from_env()
        self._auth_client: AuthClient = AuthClient(
            base_url=base_url,
            server_pref=self._config,
            timeout=ComputeClientConfig.DEFAULT_TIMEOUT,
        )

        # Session state
        self._current_token: str | None = None
        self._current_user: UserResponse | None = None
        self._credentials: tuple[str, str] | None = None

    @property
    def server_pref(self) -> ServerPref:
        """Get the current server configuration."""
        return self._config

    @property
    def auth_client(self) -> AuthClient:
        """Access to underlying AuthClient for advanced operations.

        Provides direct access to AuthClient methods for user management
        and other advanced operations not wrapped by SessionManager.

        Returns:
            The underlying AuthClient instance
        """
        return self._auth_client

    # ========================================================================
    # Authentication Lifecycle
    # ========================================================================

    async def login(self, username: str, password: str) -> TokenResponse:
        """Login with username and password.

        Args:
            username: User's username
            password: User's password

        Returns:
            TokenResponse with access token and token type

        Raises:
            httpx.HTTPStatusError: If credentials are invalid

        Example:
            session = SessionManager()
            token = await session.login("user", "password")
            print(f"Logged in with token: {token.access_token[:10]}...")
        """
        token_response = await self._auth_client.login(username, password)

        # Store token and credentials for this session
        self._current_token = token_response.access_token
        self._credentials = (username, password)

        # Fetch and cache user info
        self._current_user = await self._auth_client.get_current_user(self._current_token)

        return token_response

    async def logout(self) -> None:
        """Logout and clear session state.

        Clears the current token and user information. Does not make any
        API calls (tokens are stateless JWTs).

        Example:
            await session.logout()
            assert not session.is_authenticated()
        """
        self._current_token = None
        self._current_user = None
        self._credentials = None

    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated.

        Returns:
            True if authenticated (has valid token), False otherwise

        Example:
            if session.is_authenticated():
                print("User is logged in")
            else:
                print("Guest mode")
        """
        return self._current_token is not None

    async def get_current_user(self) -> UserResponse | None:
        """Get current authenticated user info.

        Returns cached user info if available, otherwise fetches from server.

        Returns:
            UserResponse if authenticated, None if guest mode

        Example:
            user = await session.get_current_user()
            if user:
                print(f"Username: {user.username}")
                print(f"Admin: {user.is_admin}")
        """
        if not self.is_authenticated():
            return None

        # Return cached user if available
        if self._current_user is not None:
            return self._current_user

        # Fetch user info if not cached
        assert self._current_token is not None
        self._current_user = await self._auth_client.get_current_user(self._current_token)
        return self._current_user

    # ========================================================================
    # Token Management
    # ========================================================================

    def get_token(self) -> str:
        """Get current token (synchronous, no refresh).

        This is a synchronous helper for JWTAuthProvider integration.
        For token refresh, use get_valid_token() instead.

        Returns:
            Current access token

        Raises:
            ValueError: If not authenticated
        """
        if self._current_token is None:
            raise ValueError("Not authenticated - call login() first")
        return self._current_token

    async def get_valid_token(self) -> str:
        """Get valid token with automatic refresh.

        Checks if current token needs refresh (< 60 seconds until expiry).
        If refresh is needed, automatically refreshes the token before returning.

        This is the recommended way to get tokens for API calls, as it ensures
        the token is always fresh.

        Returns:
            Valid access token (refreshed if needed)

        Raises:
            ValueError: If not authenticated

        Example:
            # Token automatically refreshed if needed
            token = await session.get_valid_token()

            # Use token for API call
            headers = {"Authorization": f"Bearer {token}"}
        """
        if self._current_token is None:
            raise ValueError("Not authenticated - call login() first")

        # Check if token needs refresh
        provider = JWTAuthProvider(token=self._current_token)
        if provider.should_refresh(self._current_token):
            try:
                # Refresh token
                token_response = await self._auth_client.refresh_token(self._current_token)
                self._current_token = token_response.access_token
            except Exception:
                # If refresh fails and we have credentials, try re-login
                if self._credentials:
                    username, password = self._credentials
                    try:
                        token_response = await self._auth_client.login(username, password)
                        self._current_token = token_response.access_token
                        return self._current_token
                    except Exception:
                        # If re-login also fails, raise original or new exception
                        raise
                raise

        return self._current_token

    # ========================================================================
    # Client Factories
    # ========================================================================

    def create_compute_client(self, timeout: float | None = None) -> "ComputeClient":
        """Create a ComputeClient using this session's configuration and auth.

        Returns:
            ComputeClient instance configured with this session's auth
        """
        # Import here to avoid circular dependency
        from .compute_client import ComputeClient

        if self.is_authenticated():
            # Create JWT auth provider with SessionManager integration
            # Pass both sync getter (for backward compat) and async getter (for token refresh)
            auth_provider = JWTAuthProvider(
                get_cached_token=self.get_token,
                get_valid_token_async=self.get_valid_token
            )
        else:
            # Guest mode - no authentication
            auth_provider = NoAuthProvider()

        return ComputeClient(
            base_url=self._config.compute_url,
            mqtt_url=self._config.mqtt_url,
            auth_provider=auth_provider,
            server_pref=self.server_pref,
            timeout=timeout,
        )

    def create_store_manager(self, timeout: float = 30.0) -> "StoreManager":
        """Create a StoreManager using this session's configuration and auth.

        Returns:
            StoreManager instance configured with this session's auth
        """
        # Import here to avoid circular dependency
        from .store_manager import StoreManager

        if not self.is_authenticated():
            raise RuntimeError("Not authenticated. Call login() first.")

        return StoreManager.authenticated(
            server_pref=self.server_pref,
            get_cached_token=self.get_token,
            get_valid_token_async=self.get_valid_token,
            timeout=timeout,
        )

    # ========================================================================
    # Cleanup
    # ========================================================================

    async def close(self) -> None:
        """Close HTTP session and cleanup resources."""
        await self._auth_client.close()

    async def __aenter__(self) -> "SessionManager":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Async context manager exit."""
        await self.close()
