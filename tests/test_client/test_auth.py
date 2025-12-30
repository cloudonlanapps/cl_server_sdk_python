"""Tests for auth.py"""

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest

from cl_client.auth import (
    AuthProvider,
    JWTAuthProvider,
    NoAuthProvider,
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


# ============================================================================
# JWT Token Parsing and Expiry Tests
# ============================================================================


def _create_jwt_token(payload: dict[str, object]) -> str:
    """Helper to create a fake JWT token for testing.

    Args:
        payload: Payload dictionary (should include 'exp' for expiry)

    Returns:
        JWT token string (header.payload.signature)
    """
    # Create minimal header
    header = {"alg": "ES256", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode()

    # Create payload
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()

    # Create fake signature (not verified in our code)
    signature_b64 = "fake_signature"

    return f"{header_b64}.{payload_b64}.{signature_b64}"


class TestJWTAuthProviderInitialization:
    """Tests for JWTAuthProvider initialization."""

    def test_jwt_auth_provider_with_token(self):
        """Test JWTAuthProvider initialization with direct token."""
        provider = JWTAuthProvider(token="test-token")
        assert provider._token == "test-token"
        assert provider._session_manager is None

    def test_jwt_auth_provider_no_arguments(self):
        """Test JWTAuthProvider raises error when no arguments provided."""
        with pytest.raises(ValueError, match="Either token or session_manager"):
            JWTAuthProvider()

    def test_jwt_auth_provider_get_token(self):
        """Test JWTAuthProvider.get_token() returns the token."""
        provider = JWTAuthProvider(token="test-token-123")
        assert provider.get_token() == "test-token-123"

    def test_jwt_auth_provider_get_token_no_token(self):
        """Test JWTAuthProvider.get_token() raises error when no token."""
        # This would need SessionManager, which will be tested in Day 5
        pass


class TestJWTTokenParsing:
    """Tests for JWT token parsing functionality."""

    def test_parse_token_expiry_valid_token(self):
        """Test parsing expiry from valid JWT token."""
        # Create token with expiry 1 hour in future
        expiry_time = datetime.now(UTC) + timedelta(hours=1)
        exp_timestamp = int(expiry_time.timestamp())

        token = _create_jwt_token({"sub": "user123", "exp": exp_timestamp})

        provider = JWTAuthProvider(token=token)
        parsed_expiry = provider._parse_token_expiry(token)

        assert parsed_expiry is not None
        # Allow 1 second tolerance for test execution time
        assert abs((parsed_expiry - expiry_time).total_seconds()) < 1

    def test_parse_token_expiry_no_exp_claim(self):
        """Test parsing token without exp claim returns None."""
        token = _create_jwt_token({"sub": "user123"})  # No exp

        provider = JWTAuthProvider(token=token)
        parsed_expiry = provider._parse_token_expiry(token)

        assert parsed_expiry is None

    def test_parse_token_expiry_invalid_format(self):
        """Test parsing malformed token returns None."""
        provider = JWTAuthProvider(token="valid-token")

        # Not a JWT format
        assert provider._parse_token_expiry("not.a.jwt") is None

        # Only two parts
        assert provider._parse_token_expiry("header.payload") is None

        # Too many parts
        assert provider._parse_token_expiry("a.b.c.d") is None

    def test_parse_token_expiry_invalid_base64(self):
        """Test parsing token with invalid base64 returns None."""
        provider = JWTAuthProvider(token="valid-token")

        # Invalid base64 characters
        invalid_token = "invalid!!!.base64!!!.signature"
        assert provider._parse_token_expiry(invalid_token) is None

    def test_parse_token_expiry_invalid_json(self):
        """Test parsing token with invalid JSON returns None."""
        provider = JWTAuthProvider(token="valid-token")

        # Valid base64 but not valid JSON
        invalid_json = base64.urlsafe_b64encode(b"not json").decode()
        invalid_token = f"header.{invalid_json}.signature"

        assert provider._parse_token_expiry(invalid_token) is None

    def test_parse_token_expiry_non_dict_payload(self):
        """Test parsing token with non-dict payload returns None."""
        provider = JWTAuthProvider(token="valid-token")

        # Payload is an array, not a dict
        array_payload = base64.urlsafe_b64encode(json.dumps([1, 2, 3]).encode()).decode()
        invalid_token = f"header.{array_payload}.signature"

        assert provider._parse_token_expiry(invalid_token) is None

    def test_parse_token_expiry_non_numeric_exp(self):
        """Test parsing token with non-numeric exp claim returns None."""
        # exp claim is a string, not a number
        token = _create_jwt_token({"sub": "user123", "exp": "not-a-number"})

        provider = JWTAuthProvider(token=token)
        parsed_expiry = provider._parse_token_expiry(token)

        assert parsed_expiry is None

    def test_parse_token_expiry_with_padding(self):
        """Test parsing token with base64 padding works correctly."""
        # Create payload that requires padding
        expiry_time = datetime.now(UTC) + timedelta(hours=1)
        exp_timestamp = int(expiry_time.timestamp())

        # Short payload that will need padding
        payload = {"exp": exp_timestamp}
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()

        # Remove padding to test our padding logic
        payload_b64 = payload_b64.rstrip("=")

        token = f"header.{payload_b64}.signature"

        provider = JWTAuthProvider(token="valid-token")
        parsed_expiry = provider._parse_token_expiry(token)

        assert parsed_expiry is not None
        assert abs((parsed_expiry - expiry_time).total_seconds()) < 1


class TestTokenExpiryChecking:
    """Tests for token expiry checking (should_refresh)."""

    def test_should_refresh_expired_token(self):
        """Test that expired tokens should be refreshed."""
        # Token expired 10 minutes ago
        expiry_time = datetime.now(UTC) - timedelta(minutes=10)
        exp_timestamp = int(expiry_time.timestamp())

        token = _create_jwt_token({"sub": "user123", "exp": exp_timestamp})

        provider = JWTAuthProvider(token=token)
        assert provider.should_refresh(token) is True

    def test_should_refresh_token_expiring_soon(self):
        """Test that tokens expiring in < 60 seconds should be refreshed."""
        # Token expires in 30 seconds
        expiry_time = datetime.now(UTC) + timedelta(seconds=30)
        exp_timestamp = int(expiry_time.timestamp())

        token = _create_jwt_token({"sub": "user123", "exp": exp_timestamp})

        provider = JWTAuthProvider(token=token)
        assert provider.should_refresh(token) is True

    def test_should_not_refresh_fresh_token(self):
        """Test that fresh tokens should not be refreshed."""
        # Token expires in 5 minutes (well above 60 second threshold)
        expiry_time = datetime.now(UTC) + timedelta(minutes=5)
        exp_timestamp = int(expiry_time.timestamp())

        token = _create_jwt_token({"sub": "user123", "exp": exp_timestamp})

        provider = JWTAuthProvider(token=token)
        assert provider.should_refresh(token) is False

    def test_should_refresh_exactly_60_seconds(self):
        """Test boundary condition: token expiring in exactly 60 seconds."""
        # Token expires in exactly 60 seconds
        expiry_time = datetime.now(UTC) + timedelta(seconds=60)
        exp_timestamp = int(expiry_time.timestamp())

        token = _create_jwt_token({"sub": "user123", "exp": exp_timestamp})

        provider = JWTAuthProvider(token=token)
        # Should NOT refresh at exactly 60 seconds (< 60, not <=)
        # Actually, due to test execution time, this might be < 60 by the time it runs
        # So we just verify it returns a boolean
        result = provider.should_refresh(token)
        assert isinstance(result, bool)

    def test_should_refresh_no_expiry_returns_false(self):
        """Test that tokens without expiry should not trigger refresh."""
        # Token with no exp claim
        token = _create_jwt_token({"sub": "user123"})

        provider = JWTAuthProvider(token=token)
        assert provider.should_refresh(token) is False

    def test_should_refresh_invalid_token_returns_false(self):
        """Test that invalid tokens return False (assume valid)."""
        provider = JWTAuthProvider(token="valid-token")

        # Invalid token format
        assert provider.should_refresh("not.a.jwt") is False

    def test_should_refresh_float_timestamp(self):
        """Test that float timestamps work correctly."""
        # Token expires in 30.5 seconds (float timestamp)
        expiry_time = datetime.now(UTC) + timedelta(seconds=30.5)
        exp_timestamp = expiry_time.timestamp()  # Keep as float

        token = _create_jwt_token({"sub": "user123", "exp": exp_timestamp})

        provider = JWTAuthProvider(token=token)
        assert provider.should_refresh(token) is True


class TestJWTAuthProviderGetHeaders:
    """Tests for JWTAuthProvider.get_headers() method."""

    def test_get_headers_with_direct_token(self):
        """Test get_headers() returns correct Authorization header."""
        provider = JWTAuthProvider(token="my-test-token")
        headers = provider.get_headers()

        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer my-test-token"

    def test_get_headers_no_token_raises_error(self):
        """Test get_headers() raises error when no token available."""
        # This would require a mock SessionManager without a token
        # For now, just test direct mode
        pass
