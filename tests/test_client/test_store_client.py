"""Unit tests for StoreClient."""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from cl_client.auth import NoAuthProvider
from cl_client.store_client import StoreClient
from cl_client.store_models import Entity, EntityListResponse, StoreConfig


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
async def store_client(mock_httpx_client):
    """Create StoreClient with mocked httpx client."""
    client = StoreClient(base_url="http://localhost:8001")
    await client.__aenter__()
    # Replace the real client with our mock
    client._client = mock_httpx_client
    yield client
    # Cleanup (though client is mocked)


class TestStoreClientInit:
    """Tests for StoreClient initialization."""

    def test_init_default(self):
        """Test default initialization."""
        client = StoreClient()
        assert client._base_url == "http://localhost:8001"
        assert client._timeout == 30.0
        assert client.auth_provider is None

    def test_init_with_auth(self):
        """Test initialization with auth provider."""
        auth = NoAuthProvider()
        client = StoreClient(
            base_url="http://example.com:8001",
            auth_provider=auth,
            timeout=60.0,
        )
        assert client._base_url == "http://example.com:8001"
        assert client._timeout == 60.0
        assert client.auth_provider is auth


class TestStoreClientReadOperations:
    """Tests for read operations."""

    @pytest.mark.asyncio
    async def test_list_entities(self, store_client, mock_httpx_client):
        """Test listing entities."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [
                {"id": 1, "label": "Entity 1"},
                {"id": 2, "label": "Entity 2"},
            ],
            "pagination": {
                "page": 1,
                "page_size": 20,
                "total_items": 2,
                "total_pages": 1,
                "has_next": False,
                "has_prev": False,
            },
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response

        result = await store_client.list_entities(page=1, page_size=20)

        assert isinstance(result, EntityListResponse)
        assert len(result.items) == 2
        assert result.items[0].id == 1
        assert result.pagination.page == 1

        # Verify correct API call
        mock_httpx_client.get.assert_called_once()
        call_args = mock_httpx_client.get.call_args
        assert call_args[0][0] == "http://localhost:8001/entities"
        assert call_args[1]["params"]["page"] == 1
        assert call_args[1]["params"]["page_size"] == 20

    @pytest.mark.asyncio
    async def test_list_entities_with_search(self, store_client, mock_httpx_client):
        """Test listing entities with search query."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [],
            "pagination": {
                "page": 1,
                "page_size": 10,
                "total_items": 0,
                "total_pages": 0,
                "has_next": False,
                "has_prev": False,
            },
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response

        await store_client.list_entities(page=1, page_size=10, search_query="test")

        call_args = mock_httpx_client.get.call_args
        assert call_args[1]["params"]["search_query"] == "test"

    @pytest.mark.asyncio
    async def test_read_entity(self, store_client, mock_httpx_client):
        """Test reading entity by ID."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 123,
            "label": "Test Entity",
            "description": "Test description",
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response

        result = await store_client.read_entity(entity_id=123)

        assert isinstance(result, Entity)
        assert result.id == 123
        assert result.label == "Test Entity"

        mock_httpx_client.get.assert_called_once()
        call_args = mock_httpx_client.get.call_args
        assert "entities/123" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_read_entity_with_version(self, store_client, mock_httpx_client):
        """Test reading specific version of entity."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 123,
            "label": "Old Label",
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response

        await store_client.read_entity(entity_id=123, version=2)

        call_args = mock_httpx_client.get.call_args
        assert call_args[1]["params"]["version"] == 2

    @pytest.mark.asyncio
    async def test_get_versions(self, store_client, mock_httpx_client):
        """Test getting version history."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"version": 1, "transaction_id": 100, "label": "V1"},
            {"version": 2, "transaction_id": 101, "label": "V2"},
        ]
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response

        result = await store_client.get_versions(entity_id=123)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].version == 1
        assert result[1].version == 2


class TestStoreClientWriteOperations:
    """Tests for write operations."""

    @pytest.mark.asyncio
    async def test_create_entity_collection(self, store_client, mock_httpx_client):
        """Test creating a collection entity."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 1,
            "label": "New Collection",
            "is_collection": True,
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post.return_value = mock_response

        result = await store_client.create_entity(
            is_collection=True,
            label="New Collection",
        )

        assert isinstance(result, Entity)
        assert result.id == 1
        assert result.is_collection is True

        # Verify multipart form data
        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args
        assert call_args[0][0] == "http://localhost:8001/entities"
        assert call_args[1]["data"]["is_collection"] == "true"
        assert call_args[1]["data"]["label"] == "New Collection"

    @pytest.mark.asyncio
    async def test_create_entity_with_file(self, store_client, mock_httpx_client, tmp_path):
        """Test creating entity with file upload."""
        # Create a temporary file
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake image data")

        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 2,
            "label": "Photo",
            "file_path": "/media/test.jpg",
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post.return_value = mock_response

        result = await store_client.create_entity(
            is_collection=False,
            label="Photo",
            image_path=test_file,
        )

        assert result.id == 2
        assert result.file_path == "/media/test.jpg"

        # Verify files parameter was passed
        call_args = mock_httpx_client.post.call_args
        assert "files" in call_args[1]

    @pytest.mark.asyncio
    async def test_update_entity(self, store_client, mock_httpx_client):
        """Test full update of entity."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 123,
            "label": "Updated Label",
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.put.return_value = mock_response

        result = await store_client.update_entity(
            entity_id=123,
            is_collection=False,
            label="Updated Label",
        )

        assert result.id == 123
        assert result.label == "Updated Label"

        mock_httpx_client.put.assert_called_once()
        call_args = mock_httpx_client.put.call_args
        assert "entities/123" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_patch_entity(self, store_client, mock_httpx_client):
        """Test partial update of entity."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 123,
            "label": "Patched Label",
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.patch.return_value = mock_response

        result = await store_client.patch_entity(
            entity_id=123,
            label="Patched Label",
        )

        assert result.label == "Patched Label"

        # Verify PATCH with form data (not JSON)
        mock_httpx_client.patch.assert_called_once()
        call_args = mock_httpx_client.patch.call_args
        assert "data" in call_args[1]  # Form data
        assert call_args[1]["data"]["label"] == "Patched Label"

    @pytest.mark.asyncio
    async def test_patch_entity_soft_delete(self, store_client, mock_httpx_client):
        """Test soft delete via patch."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 123,
            "is_deleted": True,
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.patch.return_value = mock_response

        result = await store_client.patch_entity(
            entity_id=123,
            is_deleted=True,
        )

        assert result.is_deleted is True

        call_args = mock_httpx_client.patch.call_args
        assert call_args[1]["data"]["is_deleted"] == "true"

    @pytest.mark.asyncio
    async def test_delete_entity(self, store_client, mock_httpx_client):
        """Test hard delete of entity."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_httpx_client.delete.return_value = mock_response

        await store_client.delete_entity(entity_id=123)

        mock_httpx_client.delete.assert_called_once()
        call_args = mock_httpx_client.delete.call_args
        assert "entities/123" in call_args[0][0]


class TestStoreClientAdminOperations:
    """Tests for admin operations."""

    @pytest.mark.asyncio
    async def test_get_config(self, store_client, mock_httpx_client):
        """Test getting store configuration."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "guest_mode": False,
            "updated_at": 1704067200000,
            "updated_by": "admin",
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response

        result = await store_client.get_config()

        assert isinstance(result, StoreConfig)
        assert result.guest_mode is False
        assert result.updated_by == "admin"

    @pytest.mark.asyncio
    async def test_update_guest_mode(self, store_client, mock_httpx_client):
        """Test updating guest mode configuration."""
        mock_put_response = Mock()
        mock_put_response.raise_for_status = Mock()

        # Mock GET response for get_config() call after PUT (if needed, but update_guest_mode returns bool)
        # Actually update_guest_mode just returns True.

        mock_httpx_client.put.return_value = mock_put_response

        result = await store_client.update_guest_mode(guest_mode=True)

        assert result is True

        # Verify multipart form data
        call_args = mock_httpx_client.put.call_args
        assert call_args[1]["data"]["guest_mode"] == "true"


class TestStoreClientErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_http_error(self, store_client, mock_httpx_client):
        """Test handling HTTP errors."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found",
            request=Mock(),
            response=mock_response,
        )
        mock_httpx_client.get.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            await store_client.read_entity(entity_id=999)

    @pytest.mark.asyncio
    async def test_client_not_initialized(self):
        """Test error when client not initialized."""
        client = StoreClient()
        # Don't call __aenter__

        with pytest.raises(RuntimeError, match="not initialized"):
            await client.list_entities()


class TestStoreClientAuthIntegration:
    """Tests for auth provider integration."""

    @pytest.mark.asyncio
    async def test_auth_headers_applied(self, mock_httpx_client):
        """Test that auth headers are applied to requests."""
        from cl_client.auth import NoAuthProvider

        auth_provider = NoAuthProvider()
        client = StoreClient(auth_provider=auth_provider)
        await client.__aenter__()
        client._client = mock_httpx_client

        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [],
            "pagination": {
                "page": 1,
                "page_size": 20,
                "total_items": 0,
                "total_pages": 0,
                "has_next": False,
                "has_prev": False,
            },
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response

        await client.list_entities()

        # Verify headers were passed
        call_args = mock_httpx_client.get.call_args
        assert "headers" in call_args[1]
