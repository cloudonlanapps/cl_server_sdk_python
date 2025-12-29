"""Modular authentication system.

Auth providers follow a simple protocol: they must implement get_headers().
This allows easy swapping between no-auth, JWT, API key, etc.
"""

from abc import ABC, abstractmethod


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
    """JWT token authentication (Phase 2 - FUTURE).

    Will integrate with auth server for token management.
    """

    def __init__(self, token: str) -> None:
        """Initialize with JWT token.

        Args:
            token: JWT token from auth server
        """
        self.token = token

    def get_headers(self) -> dict[str, str]:
        """Get authentication headers.

        Returns:
            Authorization header with Bearer token
        """
        return {"Authorization": f"Bearer {self.token}"}


def get_default_auth() -> AuthProvider:
    """Get default auth provider (no-auth for Phase 1).

    Returns:
        NoAuthProvider instance
    """
    return NoAuthProvider()
