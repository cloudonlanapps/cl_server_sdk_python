import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from cl_client.store_manager import StoreManager
from cl_client.store_client import StoreClient


@pytest.fixture
def mock_store_client():
    return MagicMock(spec=StoreClient)

@pytest.fixture
def store_manager(mock_store_client):
    return StoreManager(mock_store_client)

def create_http_error(status_code, detail="Error"):
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = {"detail": detail}
    request = MagicMock(spec=httpx.Request)
    return httpx.HTTPStatusError("Error", request=request, response=response)

@pytest.mark.asyncio
async def test_store_manager_http_error_handling(store_manager:StoreManager, mock_store_client):
    """Test StoreManager error handling for various HTTP status codes."""
    # Mock list_entities to raise 401
    mock_store_client.list_entities = AsyncMock(side_effect=create_http_error(401))
    result = await store_manager.list_entities()
    assert result.is_error
    assert "Unauthorized" in result.error

    # Mock read_entity to raise 403
    mock_store_client.read_entity = AsyncMock(side_effect=create_http_error(403))
    result = await store_manager.read_entity(1)
    assert result.is_error
    assert "Forbidden" in result.error

    # Mock get_versions to raise 404
    mock_store_client.get_versions = AsyncMock(side_effect=create_http_error(404, "Not found"))
    result = await store_manager.get_versions(1)
    assert result.is_error
    assert "Not Found" in result.error

    # Mock create_entity to raise 422
    mock_store_client.create_entity = AsyncMock(side_effect=create_http_error(422, "Validation failed"))
    result = await store_manager.create_entity(label="test")
    assert result.is_error
    assert "Validation Error" in result.error

    # Mock update_entity to raise 500
    mock_store_client.update_entity = AsyncMock(side_effect=create_http_error(500, "Internal error"))
    result = await store_manager.update_entity(1, label="test")
    assert result.is_error
    assert "Error 500" in result.error

@pytest.mark.asyncio
async def test_store_manager_unexpected_error_handling(store_manager:StoreManager, mock_store_client):
    """Test StoreManager handling of unexpected exceptions."""
    mock_store_client.list_entities = AsyncMock(side_effect=Exception("Boom"))
    result = await store_manager.list_entities()
    assert result.is_error
    assert "Unexpected error: Boom" in result.error

    mock_store_client.read_entity = AsyncMock(side_effect=Exception("Boom"))
    result = await store_manager.read_entity(1)
    assert result.is_error
    assert "Unexpected error: Boom" in result.error

    mock_store_client.get_versions = AsyncMock(side_effect=Exception("Boom"))
    result = await store_manager.get_versions(1)
    assert result.is_error
    assert "Unexpected error: Boom" in result.error

    mock_store_client.create_entity = AsyncMock(side_effect=Exception("Boom"))
    result = await store_manager.create_entity(label="test")
    assert result.is_error
    assert "Unexpected error: Boom" in result.error

    mock_store_client.update_entity = AsyncMock(side_effect=Exception("Boom"))
    result = await store_manager.update_entity(1, label="test")
    assert result.is_error
    assert "Unexpected error: Boom" in result.error

    mock_store_client.patch_entity = AsyncMock(side_effect=Exception("Boom"))
    result = await store_manager.patch_entity(1, label="test")
    assert result.is_error
    assert "Unexpected error: Boom" in result.error

    mock_store_client.delete_entity = AsyncMock(side_effect=Exception("Boom"))
    result = await store_manager.delete_entity(1)
    assert result.is_error
    assert "Unexpected error: Boom" in result.error

    mock_store_client.get_pref = AsyncMock(side_effect=Exception("Boom"))
    result = await store_manager.get_pref()
    assert result.is_error
    assert "Unexpected error: Boom" in result.error

    mock_store_client.update_guest_mode = AsyncMock(side_effect=Exception("Boom"))
    result = await store_manager.update_guest_mode(True)
    assert result.is_error
    assert "Unexpected error: Boom" in result.error

@pytest.mark.asyncio
async def test_store_manager_json_decode_error_handling(store_manager:StoreManager, mock_store_client):
    """Test StoreManager handling of non-JSON error responses."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 500
    response.json.side_effect = ValueError("Not JSON")
    request = MagicMock(spec=httpx.Request)
    error = httpx.HTTPStatusError("Error", request=request, response=response)
    
    mock_store_client.list_entities = AsyncMock(side_effect=error)
    result = await store_manager.list_entities()
    assert result.is_error
    assert "Error 500" in result.error
