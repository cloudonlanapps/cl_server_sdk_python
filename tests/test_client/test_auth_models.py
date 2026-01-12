"""Tests for auth models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from cl_client.auth_models import (
    PublicKeyResponse,
    TokenResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)


class TestTokenResponse:
    """Tests for TokenResponse model."""

    def test_token_response_valid(self):
        """Test TokenResponse with valid data."""
        data = {"access_token": "eyJhbGc...", "token_type": "bearer"}

        token = TokenResponse(**data)

        assert token.access_token == "eyJhbGc..."
        assert token.token_type == "bearer"

    def test_token_response_from_json(self):
        """Test TokenResponse JSON deserialization."""
        data = {"access_token": "test_token", "token_type": "bearer"}

        token = TokenResponse.model_validate(data)

        assert token.access_token == "test_token"
        assert token.token_type == "bearer"

    def test_token_response_to_json(self):
        """Test TokenResponse JSON serialization."""
        token = TokenResponse(access_token="test_token", token_type="bearer")

        data = token.model_dump()

        assert data == {"access_token": "test_token", "token_type": "bearer"}

    def test_token_response_missing_fields(self):
        """Test TokenResponse validation with missing fields."""
        with pytest.raises(ValidationError):
            TokenResponse(access_token="test_token")  # type: ignore[call-arg]


class TestPublicKeyResponse:
    """Tests for PublicKeyResponse model."""

    def test_public_key_response_valid(self):
        """Test PublicKeyResponse with valid data."""
        data = {
            "public_key": "-----BEGIN PUBLIC KEY-----\n...",
            "algorithm": "ES256",
        }

        response = PublicKeyResponse(**data)

        assert response.public_key == "-----BEGIN PUBLIC KEY-----\n..."
        assert response.algorithm == "ES256"

    def test_public_key_response_from_json(self):
        """Test PublicKeyResponse JSON deserialization."""
        data = {"public_key": "test_key", "algorithm": "ES256"}

        response = PublicKeyResponse.model_validate(data)

        assert response.public_key == "test_key"
        assert response.algorithm == "ES256"


class TestUserResponse:
    """Tests for UserResponse model."""

    def test_user_response_valid(self):
        """Test UserResponse with valid data."""
        now = datetime.now(UTC)
        data = {
            "id": 1,
            "username": "testuser",
            "is_admin": False,
            "is_active": True,
            "created_at": now.isoformat(),
            "permissions": ["read:jobs", "write:jobs"],
        }

        user = UserResponse(**data)

        assert user.id == 1
        assert user.username == "testuser"
        assert user.is_admin is False
        assert user.is_active is True
        assert user.permissions == ["read:jobs", "write:jobs"]

    def test_user_response_defaults(self):
        """Test UserResponse default values."""
        now = datetime.now(UTC)
        data = {"id": 1, "username": "testuser", "created_at": now.isoformat()}

        user = UserResponse(**data)

        assert user.is_admin is False
        assert user.is_active is True
        assert user.permissions == []

    def test_user_response_from_json(self):
        """Test UserResponse JSON deserialization."""
        data = {
            "id": 2,
            "username": "admin",
            "is_admin": True,
            "is_active": True,
            "created_at": "2024-01-15T10:30:00Z",
            "permissions": ["*"],
        }

        user = UserResponse.model_validate(data)

        assert user.id == 2
        assert user.username == "admin"
        assert user.is_admin is True
        assert user.permissions == ["*"]

    def test_user_response_to_json(self):
        """Test UserResponse JSON serialization."""
        now = datetime.now(UTC)
        user = UserResponse(
            id=1,
            username="testuser",
            is_admin=False,
            is_active=True,
            created_at=now,
            permissions=["read:jobs"],
        )

        data = user.model_dump()

        assert data["id"] == 1
        assert data["username"] == "testuser"
        assert data["is_admin"] is False
        assert data["permissions"] == ["read:jobs"]


class TestUserCreateRequest:
    """Tests for UserCreateRequest model."""

    def test_user_create_request_valid(self):
        """Test UserCreateRequest with valid data."""
        data = {
            "username": "newuser",
            "password": "securepass",
            "is_admin": False,
            "is_active": True,
            "permissions": ["read:jobs"],
        }

        request = UserCreateRequest(**data)

        assert request.username == "newuser"
        assert request.password == "securepass"
        assert request.is_admin is False
        assert request.is_active is True
        assert request.permissions == ["read:jobs"]

    def test_user_create_request_defaults(self):
        """Test UserCreateRequest default values."""
        request = UserCreateRequest(username="newuser", password="password")

        assert request.is_admin is False
        assert request.is_active is True
        assert request.permissions == []

    def test_user_create_request_admin(self):
        """Test UserCreateRequest for admin user."""
        request = UserCreateRequest(
            username="admin",
            password="adminpass",
            is_admin=True,
            permissions=["*"],
        )

        assert request.is_admin is True
        assert request.permissions == ["*"]

    def test_user_create_request_to_json(self):
        """Test UserCreateRequest JSON serialization."""
        request = UserCreateRequest(
            username="testuser",
            password="testpass",
            permissions=["read:jobs", "write:jobs"],
        )

        data = request.model_dump()

        assert data["username"] == "testuser"
        assert data["password"] == "testpass"
        assert data["permissions"] == ["read:jobs", "write:jobs"]


class TestUserUpdateRequest:
    """Tests for UserUpdateRequest model."""

    def test_user_update_request_all_fields(self):
        """Test UserUpdateRequest with all fields."""
        data = {
            "password": "newpassword",
            "permissions": ["*"],
            "is_active": False,
            "is_admin": True,
        }

        request = UserUpdateRequest(**data)

        assert request.password == "newpassword"
        assert request.permissions == ["*"]
        assert request.is_active is False
        assert request.is_admin is True

    def test_user_update_request_partial(self):
        """Test UserUpdateRequest with partial updates."""
        # Only update password
        request1 = UserUpdateRequest(password="newpass")
        assert request1.password == "newpass"
        assert request1.permissions is None
        assert request1.is_active is None
        assert request1.is_admin is None

        # Only update permissions
        request2 = UserUpdateRequest(permissions=["read:jobs"])
        assert request2.password is None
        assert request2.permissions == ["read:jobs"]

    def test_user_update_request_empty(self):
        """Test UserUpdateRequest with no updates."""
        request = UserUpdateRequest()

        assert request.password is None
        assert request.permissions is None
        assert request.is_active is None
        assert request.is_admin is None

    def test_user_update_request_to_json_excludes_none(self):
        """Test UserUpdateRequest JSON serialization excludes None values."""
        request = UserUpdateRequest(password="newpass", is_admin=True)

        # Use exclude_none to only include non-None fields
        data = request.model_dump(exclude_none=True)

        assert "password" in data
        assert "is_admin" in data
        assert "permissions" not in data
        assert "is_active" not in data
