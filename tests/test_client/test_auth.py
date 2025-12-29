"""Tests for auth.py"""

import pytest
from cl_client.auth import (
    AuthProvider,
    NoAuthProvider,
    JWTAuthProvider,
    get_default_auth,
)


def test_no_auth_provider():
    """Test NoAuthProvider returns empty headers."""
    provider = NoAuthProvider()
    headers = provider.get_headers()

    assert headers == {}
    assert isinstance(provider, AuthProvider)


def test_jwt_auth_provider():
    """Test JWTAuthProvider returns Bearer token."""
    provider = JWTAuthProvider(token="test-token-123")
    headers = provider.get_headers()

    assert "Authorization" in headers
    assert headers["Authorization"] == "Bearer test-token-123"
    assert isinstance(provider, AuthProvider)


def test_get_default_auth():
    """Test get_default_auth returns NoAuthProvider."""
    provider = get_default_auth()

    assert isinstance(provider, NoAuthProvider)
    assert provider.get_headers() == {}


def test_auth_provider_is_abstract():
    """Test that AuthProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        AuthProvider()  # type: ignore[abstract]


def test_auth_providers_are_swappable():
    """Test that auth providers can be swapped."""
    # Start with no-auth
    provider: AuthProvider = NoAuthProvider()
    assert provider.get_headers() == {}

    # Swap to JWT
    provider = JWTAuthProvider(token="new-token")
    assert provider.get_headers()["Authorization"] == "Bearer new-token"
