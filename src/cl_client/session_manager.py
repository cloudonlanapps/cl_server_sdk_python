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
from .server_config import ServerConfig

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
        server_config: ServerConfig | None = None,
    ) -> None:
        """Initialize session manager.

        Args:
            base_url: Auth service URL (overrides server_config.auth_url)
            server_config: Server configuration (default: from environment)
        """
        self._config = server_config or ServerConfig.from_env()
        self._auth_client = AuthClient(
            base_url=base_url,
            server_config=self._config,
        )

        # Session state
        self._current_token: str | None = None
        self._current_user: UserResponse | None = None

    @property
    def _server_config(self) -> ServerConfig:
        """Get server configuration (for use by client factories)."""
        return self._config

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

        # Store token for this session
        self._current_token = token_response.access_token

        # Fetch and cache user info
        self._current_user = await self._auth_client.get_current_user(
            self._current_token
        )

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
        self._current_user = await self._auth_client.get_current_user(
            self._current_token
        )
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
            # Refresh token
            token_response = await self._auth_client.refresh_token(self._current_token)
            self._current_token = token_response.access_token

        return self._current_token

    # ========================================================================
    # Client Factories
    # ========================================================================

    def create_compute_client(self) -> "ComputeClient":
        """Create ComputeClient with appropriate authentication.

        Creates a ComputeClient pre-configured with:
        - JWTAuthProvider if authenticated (with SessionManager integration)
        - NoAuthProvider if guest mode

        The created client will use this SessionManager for automatic token
        refresh when making API calls.

        Returns:
            Pre-configured ComputeClient instance

        Example (Authenticated):
            session = SessionManager()
            await session.login("user", "pass")

            # Client uses JWT auth with auto-refresh
            client = session.create_compute_client()
            job = await client.clip_embedding.embed_image(...)

        Example (Guest mode):
            session = SessionManager()
            # No login - guest mode

            # Client uses no-auth mode
            client = session.create_compute_client()
            job = await client.clip_embedding.embed_image(...)
        """
        # Import here to avoid circular dependency
        from .compute_client import ComputeClient

        if self.is_authenticated():
            # Create JWT auth provider with SessionManager integration
            auth_provider = JWTAuthProvider(session_manager=self)
        else:
            # Guest mode - no authentication
            auth_provider = NoAuthProvider()

        return ComputeClient(
            base_url=self._config.compute_url,
            mqtt_broker=self._config.mqtt_broker,
            mqtt_port=self._config.mqtt_port,
            auth_provider=auth_provider,
        )

    def create_store_manager(self) -> "StoreManager":
        """Create StoreManager with authentication from this session.

        Creates a StoreManager pre-configured with authentication from this
        SessionManager. Requires prior authentication via login().

        Returns:
            Pre-configured StoreManager instance

        Raises:
            RuntimeError: If not authenticated (call login() first)

        Example (Authenticated):
            session = SessionManager()
            await session.login("user", "password")

            # Create store manager with auth
            store = session.create_store_manager()

            # Upload image
            result = await store.create_entity(
                label="My Photo",
                image_path=Path("photo.jpg")
            )
            if result.is_success:
                print(f"Created entity ID: {result.data.id}")

        Example (Guest mode - read-only):
            # For guest mode, use StoreManager.guest() instead
            from cl_client import StoreManager
            store = StoreManager.guest()
            result = await store.list_entities()
        """
        # Import here to avoid circular dependency
        from .store_manager import StoreManager

        if not self.is_authenticated():
            raise RuntimeError("Not authenticated. Call login() first.")

        return StoreManager.authenticated(
            session_manager=self,
            base_url=self._config.store_url,
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

    async def __aexit__(
        self, exc_type: object, exc_val: object, exc_tb: object
    ) -> None:
        """Async context manager exit."""
        await self.close()
