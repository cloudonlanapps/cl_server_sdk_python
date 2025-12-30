"""Modular authentication system.

Auth providers follow a simple protocol: they must implement get_headers().
This allows easy swapping between no-auth, JWT, API key, etc.
"""

import base64
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .session_manager import SessionManager


class AuthProvider(ABC):
    """Abstract base class for auth providers (protocol-based)."""

    @abstractmethod
    def get_headers(self) -> dict[str, str]:
        """Get authentication headers for HTTP requests.

        Returns:
            Dictionary of headers to add to requests
        """
        pass


class NoAuthProvider(AuthProvider):
    """No authentication (Phase 1).

    Returns empty headers for all requests.
    """

    def get_headers(self) -> dict[str, str]:
        """Get authentication headers.

        Returns:
            Empty dict (no authentication)
        """
        return {}


class JWTAuthProvider(AuthProvider):
    """JWT token authentication with automatic refresh support.

    Supports two modes:
    1. Direct token mode: Initialized with a static token string
    2. SessionManager mode: Integrated with SessionManager for automatic token refresh

    The provider can parse JWT tokens to extract expiry time and determine
    when tokens need refreshing (< 60 seconds before expiry).

    Note: get_headers() is synchronous and cannot perform async token refresh.
    The SessionManager is responsible for calling get_valid_token() before
    using this provider to ensure the token is fresh.

    Example (Direct mode):
        provider = JWTAuthProvider(token="eyJhbGc...")
        headers = provider.get_headers()

    Example (SessionManager mode):
        provider = JWTAuthProvider(session_manager=session)
        # SessionManager handles token refresh automatically
    """

    def __init__(
        self,
        token: str | None = None,
        session_manager: "SessionManager | None" = None,
    ) -> None:
        """Initialize JWT auth provider.

        Args:
            token: Direct JWT token (for static token mode)
            session_manager: SessionManager instance (for auto-refresh mode)

        Raises:
            ValueError: If neither token nor session_manager is provided
        """
        if token is None and session_manager is None:
            raise ValueError("Either token or session_manager must be provided")

        self._token = token
        self._session_manager = session_manager

    def _parse_token_expiry(self, token: str) -> datetime | None:
        """Parse JWT token to extract expiry time.

        Decodes the JWT payload (without verification) to extract the 'exp' claim.
        This is used for determining when to refresh the token, not for validation.

        Args:
            token: JWT token string

        Returns:
            Expiry datetime in UTC, or None if parsing fails or no exp claim

        Example:
            >>> provider = JWTAuthProvider(token="eyJhbGc...")
            >>> expiry = provider._parse_token_expiry(token)
            >>> if expiry:
            ...     print(f"Token expires at {expiry}")
        """
        try:
            # JWT format: header.payload.signature
            parts = token.split(".")
            if len(parts) != 3:
                return None

            # Decode payload (second part)
            payload_b64 = parts[1]

            # Add padding if needed (base64 requires length multiple of 4)
            padding = 4 - (len(payload_b64) % 4)
            if padding != 4:
                payload_b64 += "=" * padding

            # Decode and parse JSON
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload_raw = cast(object, json.loads(payload_bytes.decode("utf-8")))

            # Validate payload is a dictionary
            if not isinstance(payload_raw, dict):
                return None

            payload = cast(dict[str, object], payload_raw)

            # Extract exp claim (Unix timestamp)
            exp_timestamp_raw = payload.get("exp")
            if exp_timestamp_raw is None:
                return None

            # Validate exp is a number
            if not isinstance(exp_timestamp_raw, (int, float)):
                return None

            exp_timestamp = float(exp_timestamp_raw)

            # Convert to datetime
            return datetime.fromtimestamp(exp_timestamp, tz=UTC)

        except (ValueError, KeyError, json.JSONDecodeError):
            # If parsing fails, return None (token refresh will use other mechanisms)
            return None

    def should_refresh(self, token: str) -> bool:
        """Check if token should be refreshed.

        Tokens should be refreshed when less than 60 seconds remain until expiry.
        This threshold matches the Dart SDK implementation.

        Args:
            token: JWT token to check

        Returns:
            True if token should be refreshed, False otherwise

        Example:
            >>> provider = JWTAuthProvider(token="eyJhbGc...")
            >>> if provider.should_refresh(token):
            ...     # Trigger token refresh
            ...     new_token = await session.get_valid_token()
        """
        expiry = self._parse_token_expiry(token)
        if expiry is None:
            # Can't determine expiry, assume token is valid
            return False

        now = datetime.now(UTC)
        time_until_expiry = (expiry - now).total_seconds()

        # Refresh if less than 60 seconds until expiry
        return time_until_expiry < 60

    def get_token(self) -> str:
        """Get current token.

        Returns:
            Current JWT token

        Raises:
            ValueError: If no token is available
        """
        if self._token is not None:
            return self._token

        if self._session_manager is not None:
            # In SessionManager mode, get token from manager
            # This will be implemented when SessionManager is created
            return self._session_manager.get_token()

        raise ValueError("No token available")

    def get_headers(self) -> dict[str, str]:
        """Get authentication headers with Bearer token.

        Returns the current token as Authorization header. This method is
        synchronous and cannot perform token refresh. The SessionManager
        should call get_valid_token() before using this provider.

        Returns:
            Authorization header with Bearer token

        Raises:
            ValueError: If no token is available
        """
        token = self.get_token()
        return {"Authorization": f"Bearer {token}"}


def get_default_auth() -> AuthProvider:
    """Get default auth provider (no-auth for Phase 1).

    Returns:
        NoAuthProvider instance
    """
    return NoAuthProvider()
