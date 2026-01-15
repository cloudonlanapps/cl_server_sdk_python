import asyncio
import pytest
import httpx
from pathlib import Path
from cl_client.store_manager import StoreManager
from cl_client.store_client import StoreClient

@pytest.mark.integration
@pytest.mark.asyncio
async def test_store_advanced_features(store_manager: StoreManager, test_image: Path):
    """Test advanced store features: hierarchy, versioning, and bulk delete."""
    
    # 1. Test Hierarchy (Parenting)
    collection_result = await store_manager.create_entity(
        label="Parent Collection",
        is_collection=True
    )
    assert collection_result.is_success
    parent_id = collection_result.data.id
    
    child_result = await store_manager.create_entity(
        label="Child Media",
        is_collection=False,
        parent_id=parent_id,
        image_path=test_image
    )
    assert child_result.is_success
    child_id = child_result.data.id
    assert child_result.data.parent_id == parent_id
    
    # 2. Test Versioning
    # Initial version is 1
    # Update label
    update1 = await store_manager.update_entity(
        entity_id=child_id,
        label="Child Media V2",
        is_collection=False,
        parent_id=parent_id
    )
    assert update1.is_success
    
    # Update description (Patch)
    patch1 = await store_manager.patch_entity(
        entity_id=child_id,
        description="Version 3 description"
    )
    assert patch1.is_success
    
    # Check versions
    versions_result = await store_manager.get_versions(child_id)
    assert versions_result.is_success
    # There should be 3 versions (create, update, patch)
    assert len(versions_result.data) >= 3
    
    # Read specific version
    v1_entity = await store_manager._store_client.read_entity(child_id, version=1)
    assert v1_entity.label == "Child Media"
    
    v2_entity = await store_manager._store_client.read_entity(child_id, version=2)
    assert v2_entity.label == "Child Media V2"
    
    # 3. Test pagination and search in list_entities
    list_result = await store_manager.list_entities(search_query="Parent")
    assert list_result.is_success
    assert any(e.label == "Parent Collection" for e in list_result.data.items)
    
    # 4. Test Error Response (404)
    read_non_existent = await store_manager.read_entity(999999)
    assert read_non_existent.is_error
    assert "Not Found" in read_non_existent.error
    
    # 5. Test Bulk Delete (Admin only usually, but let's try via client)
    # Note: store_manager is created with admin creds in conftest if available
    try:
        await store_manager._store_client.delete_all_entities()
        # Verify empty
        empty_list = await store_manager.list_entities()
        assert empty_list.is_success
        assert len(empty_list.data.items) == 0
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            pytest.skip("Bulk delete requires admin permissions")
        raise
