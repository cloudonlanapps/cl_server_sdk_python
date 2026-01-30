"""Authentication models mirroring auth service schemas.

This module provides Pydantic models for all auth service endpoints,
ensuring type-safe interactions with the authentication API.
"""

from datetime import datetime

from pydantic import BaseModel, Field

# ============================================================================
# Token Models
# ============================================================================


class TokenResponse(BaseModel):
    """Response from /auth/token and /auth/token/refresh endpoints.

    Example:
        {
            "access_token": "eyJhbGc...",
            "token_type": "bearer"
        }
    """

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(..., description="Token type (always 'bearer')")


class PublicKeyResponse(BaseModel):
    """Response from /auth/public-key endpoint.

    Example:
        {
            "public_key": "-----BEGIN PUBLIC KEY-----\n...",
            "algorithm": "ES256"
        }
    """

    public_key: str = Field(..., description="Public key for token verification (PEM format)")
    algorithm: str = Field(..., description="JWT algorithm (ES256)")


# ============================================================================
# User Models
# ============================================================================


class UserResponse(BaseModel):
    """User information from /users/* endpoints.

    Represents a user account with authentication and authorization details.

    Example:
        {
            "id": 1,
            "username": "testuser",
            "is_admin": false,
            "is_active": true,
            "created_at": "2024-01-15T10:30:00",
            "permissions": ["read:jobs", "write:jobs"]
        }
    """

    id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    is_admin: bool = Field(False, description="Whether user has admin privileges")
    is_active: bool = Field(True, description="Whether user account is active")
    created_at: datetime = Field(..., description="Account creation timestamp")
    permissions: list[str] = Field(default_factory=list, description="User permissions")


class UserCreateRequest(BaseModel):
    """Request body for POST /users/.

    Used to create a new user account. All fields except username and password
    are optional and have sensible defaults.

    Example:
        {
            "username": "newuser",
            "password": "securepassword",
            "is_admin": false,
            "is_active": true,
            "permissions": ["read:jobs"]
        }
    """

    username: str = Field(..., description="Username (must be unique)")
    password: str = Field(..., description="User password (will be hashed)")
    is_admin: bool = Field(False, description="Grant admin privileges")
    is_active: bool = Field(True, description="Set account active status")
    permissions: list[str] = Field(default_factory=list, description="Initial permissions")

    def to_api_payload(self) -> dict[str, str]:
        """Convert to form data payload suitable for POST /users/.

        Returns:
            Dictionary with string values for form data submission.
            Booleans are converted to lowercase strings ("true"/"false").
        """
        data_dict = self.model_dump(exclude_none=True)

        # Convert to string values for form data
        data: dict[str, str] = {}
        for key, value in data_dict.items():
            if key == "permissions":
                data[key] = ",".join(self.permissions)
            elif isinstance(value, bool):
                data[key] = "true" if value else "false"
            else:
                data[key] = str(value)

        return data


class UserUpdateRequest(BaseModel):
    """Request body for PUT /users/{user_id}.

    All fields are optional to support partial updates. Only provided fields
    will be updated on the user account.

    Example:
        {
            "password": "newpassword",
            "permissions": ["*"],
            "is_admin": true
        }
    """

    password: str | None = Field(None, description="New password (optional)")
    permissions: list[str] | None = Field(None, description="Update permissions (optional)")
    is_active: bool | None = Field(None, description="Update active status (optional)")
    is_admin: bool | None = Field(None, description="Update admin status (optional)")

    def to_api_payload(self) -> dict[str, str]:
        """Convert to form data payload suitable for PUT /users/{user_id}.

        Returns:
            Dictionary with string values for form data submission.
            Booleans are converted to lowercase strings ("true"/"false").
        """
        data_dict = self.model_dump(exclude_none=True)

        # Convert to string values for form data
        data: dict[str, str] = {}
        for key, value in data_dict.items():
            if key == "permissions" and value is not None:
                data[key] = ",".join(value) if isinstance(value, list) else str(value)
            elif isinstance(value, bool):
                data[key] = "true" if value else "false"
            else:
                data[key] = str(value)

        return data
