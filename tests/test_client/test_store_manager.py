"""Unit tests for StoreManager."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from cl_client.store_manager import StoreManager
from cl_client.store_models import (
    Entity,
    EntityListResponse,
    EntityPagination,
    EntityVersion,
    StoreConfig,
)


@pytest.fixture
def mock_store_client():
    """Create a mock StoreClient."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock()
    return client


@pytest.fixture
def store_manager(mock_store_client):
    """Create StoreManager with mocked StoreClient."""
    return StoreManager(store_client=mock_store_client)


class TestStoreManagerInit:
    """Tests for StoreManager initialization."""

    def test_guest_mode(self):
        """Test guest mode initialization."""
        manager = StoreManager.guest(base_url="http://example.com:8001")

        assert manager._store_client is not None
        assert manager._store_client._base_url == "http://example.com:8001"
        assert manager._store_client._auth_provider is None

    @pytest.mark.asyncio
    async def test_authenticated_mode(self):
        """Test authenticated mode initialization."""
        from cl_client.auth_models import UserResponse
        from cl_client.server_config import ServerConfig
        from cl_client.session_manager import SessionManager

        # Create session manager
        config = ServerConfig(
            auth_url="http://localhost:8000",
            store_url="http://localhost:8001",
        )
        session = SessionManager(server_config=config)

        # Mock login and get_current_user
        with patch.object(session._auth_client, "login") as mock_login, patch.object(
            session._auth_client, "get_current_user"
        ) as mock_get_user:
            mock_login.return_value = Mock(
                access_token="test_token",
                token_type="bearer",
            )
            mock_get_user.return_value = UserResponse(
                id=1,
                username="test_user",
                is_admin=False,
                is_active=True,
                created_at=1704067200000,
                permissions=[],
            )
            await session.__aenter__()
            await session.login("user", "password")

        # Create store manager from session
        manager = StoreManager.authenticated(session_manager=session)

        assert manager._store_client is not None
        assert manager._store_client._auth_provider is not None

        await session.__aexit__(None, None, None)


class TestStoreManagerReadOperations:
    """Tests for read operations."""

    @pytest.mark.asyncio
    async def test_list_entities_success(self, store_manager, mock_store_client):
        """Test successful entity listing."""
        # Mock response
        expected_response = EntityListResponse(
            items=[Entity(id=1, label="Test")],
            pagination=EntityPagination(
                page=1,
                page_size=20,
                total_items=1,
                total_pages=1,
                has_next=False,
                has_prev=False,
            ),
        )
        mock_store_client.list_entities.return_value = expected_response

        # Call manager
        result = await store_manager.list_entities(page=1, page_size=20)

        # Verify
        assert result.is_success
        assert result.data == expected_response
        assert result.success == "Entities retrieved successfully"
        mock_store_client.list_entities.assert_called_once_with(
            page=1,
            page_size=20,
            search_query=None,
        )

    @pytest.mark.asyncio
    async def test_list_entities_with_search(self, store_manager, mock_store_client):
        """Test entity listing with search query."""
        expected_response = EntityListResponse(
            items=[],
            pagination=EntityPagination(
                page=1,
                page_size=10,
                total_items=0,
                total_pages=0,
                has_next=False,
                has_prev=False,
            ),
        )
        mock_store_client.list_entities.return_value = expected_response

        result = await store_manager.list_entities(
            page=1,
            page_size=10,
            search_query="test query",
        )

        assert result.is_success
        mock_store_client.list_entities.assert_called_once_with(
            page=1,
            page_size=10,
            search_query="test query",
        )

    @pytest.mark.asyncio
    async def test_read_entity_success(self, store_manager, mock_store_client):
        """Test successful entity read."""
        expected_entity = Entity(id=123, label="Test Entity")
        mock_store_client.read_entity.return_value = expected_entity

        result = await store_manager.read_entity(entity_id=123)

        assert result.is_success
        assert result.data == expected_entity
        assert result.success == "Entity retrieved successfully"
        mock_store_client.read_entity.assert_called_once_with(
            entity_id=123,
            version=None,
        )

    @pytest.mark.asyncio
    async def test_read_entity_with_version(self, store_manager, mock_store_client):
        """Test reading specific version of entity."""
        expected_entity = Entity(id=123, label="Old Label")
        mock_store_client.read_entity.return_value = expected_entity

        result = await store_manager.read_entity(entity_id=123, version=2)

        assert result.is_success
        mock_store_client.read_entity.assert_called_once_with(
            entity_id=123,
            version=2,
        )

    @pytest.mark.asyncio
    async def test_get_versions_success(self, store_manager, mock_store_client):
        """Test getting version history."""
        expected_versions = [
            EntityVersion(version=1, transaction_id=100),
            EntityVersion(version=2, transaction_id=101),
        ]
        mock_store_client.get_versions.return_value = expected_versions

        result = await store_manager.get_versions(entity_id=123)

        assert result.is_success
        assert result.data == expected_versions
        assert result.success == "Version history retrieved successfully"
        mock_store_client.get_versions.assert_called_once_with(entity_id=123)


class TestStoreManagerWriteOperations:
    """Tests for write operations."""

    @pytest.mark.asyncio
    async def test_create_entity_collection(self, store_manager, mock_store_client):
        """Test creating a collection entity."""
        expected_entity = Entity(id=1, label="New Collection", is_collection=True)
        mock_store_client.create_entity.return_value = expected_entity

        result = await store_manager.create_entity(
            label="New Collection",
            is_collection=True,
        )

        assert result.is_success
        assert result.data == expected_entity
        assert result.success == "Entity created successfully"
        mock_store_client.create_entity.assert_called_once_with(
            is_collection=True,
            label="New Collection",
            description=None,
            parent_id=None,
            image_path=None,
        )

    @pytest.mark.asyncio
    async def test_create_entity_with_file(self, store_manager, mock_store_client):
        """Test creating entity with file."""
        test_path = Path("/tmp/test.jpg")
        expected_entity = Entity(
            id=2,
            label="Photo",
            file_path="/media/test.jpg",
        )
        mock_store_client.create_entity.return_value = expected_entity

        result = await store_manager.create_entity(
            label="Photo",
            description="Test photo",
            is_collection=False,
            image_path=test_path,
        )

        assert result.is_success
        assert result.data.file_path == "/media/test.jpg"
        mock_store_client.create_entity.assert_called_once_with(
            is_collection=False,
            label="Photo",
            description="Test photo",
            parent_id=None,
            image_path=test_path,
        )

    @pytest.mark.asyncio
    async def test_update_entity_success(self, store_manager, mock_store_client):
        """Test full update of entity."""
        expected_entity = Entity(id=123, label="Updated Label")
        mock_store_client.update_entity.return_value = expected_entity

        result = await store_manager.update_entity(
            entity_id=123,
            label="Updated Label",
            is_collection=False,
        )

        assert result.is_success
        assert result.data.label == "Updated Label"
        mock_store_client.update_entity.assert_called_once_with(
            entity_id=123,
            is_collection=False,
            label="Updated Label",
            description=None,
            parent_id=None,
            image_path=None,
        )

    @pytest.mark.asyncio
    async def test_patch_entity_success(self, store_manager, mock_store_client):
        """Test partial update of entity."""
        expected_entity = Entity(id=123, label="Patched Label")
        mock_store_client.patch_entity.return_value = expected_entity

        result = await store_manager.patch_entity(
            entity_id=123,
            label="Patched Label",
        )

        assert result.is_success
        assert result.success == "Entity patched successfully"
        mock_store_client.patch_entity.assert_called_once_with(
            entity_id=123,
            label="Patched Label",
            description=None,
            parent_id=None,
            is_deleted=None,
        )

    @pytest.mark.asyncio
    async def test_patch_entity_soft_delete(self, store_manager, mock_store_client):
        """Test soft delete via patch."""
        expected_entity = Entity(id=123, is_deleted=True)
        mock_store_client.patch_entity.return_value = expected_entity

        result = await store_manager.patch_entity(
            entity_id=123,
            is_deleted=True,
        )

        assert result.is_success
        mock_store_client.patch_entity.assert_called_once_with(
            entity_id=123,
            label=None,
            description=None,
            parent_id=None,
            is_deleted=True,
        )

    @pytest.mark.asyncio
    async def test_delete_entity_success(self, store_manager, mock_store_client):
        """Test hard delete of entity."""
        mock_store_client.delete_entity.return_value = None

        result = await store_manager.delete_entity(entity_id=123)

        assert result.is_success
        assert result.data is None
        assert result.success == "Entity deleted successfully"
        mock_store_client.delete_entity.assert_called_once_with(entity_id=123)


class TestStoreManagerAdminOperations:
    """Tests for admin operations."""

    @pytest.mark.asyncio
    async def test_get_config_success(self, store_manager, mock_store_client):
        """Test getting store configuration."""
        expected_config = StoreConfig(
            guest_mode=False,
            updated_at=1704067200000,
            updated_by="admin",
        )
        mock_store_client.get_config.return_value = expected_config

        result = await store_manager.get_config()

        assert result.is_success
        assert result.data == expected_config
        assert result.success == "Configuration retrieved successfully"
        mock_store_client.get_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_read_auth_success(self, store_manager, mock_store_client):
        """Test updating read auth configuration."""
        expected_config = StoreConfig(
            guest_mode=True,
            updated_at=1704153600000,
        )
        mock_store_client.update_read_auth.return_value = expected_config

        result = await store_manager.update_read_auth(enabled=False)

        assert result.is_success
        assert result.data.guest_mode is True
        assert result.success == "Read authentication configuration updated successfully"
        mock_store_client.update_read_auth.assert_called_once_with(enabled=False)


class TestStoreManagerErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_unauthorized_error(self, store_manager, mock_store_client):
        """Test handling 401 Unauthorized."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"detail": "Invalid token"}

        error = httpx.HTTPStatusError(
            "Unauthorized",
            request=Mock(),
            response=mock_response,
        )
        mock_store_client.list_entities.side_effect = error

        result = await store_manager.list_entities()

        assert result.is_error
        assert result.error == "Unauthorized: Invalid or missing token"
        assert result.data is None

    @pytest.mark.asyncio
    async def test_forbidden_error(self, store_manager, mock_store_client):
        """Test handling 403 Forbidden."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"detail": "Insufficient permissions"}

        error = httpx.HTTPStatusError(
            "Forbidden",
            request=Mock(),
            response=mock_response,
        )
        mock_store_client.create_entity.side_effect = error

        result = await store_manager.create_entity(label="Test", is_collection=False)

        assert result.is_error
        assert result.error == "Forbidden: Insufficient permissions"

    @pytest.mark.asyncio
    async def test_not_found_error(self, store_manager, mock_store_client):
        """Test handling 404 Not Found."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"detail": "Entity not found"}

        error = httpx.HTTPStatusError(
            "Not Found",
            request=Mock(),
            response=mock_response,
        )
        mock_store_client.read_entity.side_effect = error

        result = await store_manager.read_entity(entity_id=999)

        assert result.is_error
        assert "Not Found: Entity not found" in result.error

    @pytest.mark.asyncio
    async def test_validation_error(self, store_manager, mock_store_client):
        """Test handling 422 Validation Error."""
        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "detail": "Invalid field value",
        }

        error = httpx.HTTPStatusError(
            "Validation Error",
            request=Mock(),
            response=mock_response,
        )
        mock_store_client.patch_entity.side_effect = error

        result = await store_manager.patch_entity(entity_id=123, label="")

        assert result.is_error
        assert "Validation Error:" in result.error

    @pytest.mark.asyncio
    async def test_generic_http_error(self, store_manager, mock_store_client):
        """Test handling other HTTP errors."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"detail": "Internal server error"}

        error = httpx.HTTPStatusError(
            "Server Error",
            request=Mock(),
            response=mock_response,
        )
        mock_store_client.delete_entity.side_effect = error

        result = await store_manager.delete_entity(entity_id=123)

        assert result.is_error
        assert "Error 500:" in result.error

    @pytest.mark.asyncio
    async def test_unexpected_exception(self, store_manager, mock_store_client):
        """Test handling unexpected exceptions."""
        mock_store_client.list_entities.side_effect = ValueError("Unexpected error")

        result = await store_manager.list_entities()

        assert result.is_error
        assert "Unexpected error: Unexpected error" in result.error

    @pytest.mark.asyncio
    async def test_error_response_without_json(self, store_manager, mock_store_client):
        """Test handling errors when response.json() fails."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.side_effect = Exception("Not JSON")

        error = httpx.HTTPStatusError(
            "Server Error",
            request=Mock(),
            response=mock_response,
        )
        mock_store_client.read_entity.side_effect = error

        result = await store_manager.read_entity(entity_id=123)

        assert result.is_error
        # Should fall back to str(error)
        assert "Error 500:" in result.error


class TestStoreManagerContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_store_client):
        """Test async context manager entry and exit."""
        manager = StoreManager(store_client=mock_store_client)

        async with manager as m:
            assert m is manager
            mock_store_client.__aenter__.assert_called_once()

        mock_store_client.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self, mock_store_client):
        """Test context manager properly closes on exception."""
        manager = StoreManager(store_client=mock_store_client)

        try:
            async with manager:
                raise ValueError("Test exception")
        except ValueError:
            pass

        # __aexit__ should still be called
        mock_store_client.__aexit__.assert_called_once()
