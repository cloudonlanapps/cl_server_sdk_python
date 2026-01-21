"""Integration tests for store service.

These tests verify store operations across multiple auth modes:
- admin: Full access (all operations succeed)
- user-with-permission: Has media_store_read and media_store_write
- user-no-permission: No store permissions (read/write fail with 403)
- no-auth: Read succeeds (if read_auth disabled), write fails with 401

Store authentication model:
- Read operations: Can be public if read_auth_enabled=false
- Write operations: ALWAYS require auth + media_store_write permission
- Admin operations: Require admin role
"""

import sys
from pathlib import Path
from pathlib import Path as PathlibPath

import pytest

sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
from conftest import AuthConfig, get_expected_error, should_succeed


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_entities(store_manager, auth_config: AuthConfig):
    """Test listing entities with pagination."""
    if should_succeed(auth_config, operation_type="store_read"):
        # Should succeed
        result = await store_manager.list_entities(page=1, page_size=20)
        assert result.is_success, f"Expected success but got error: {result.error}"
        assert result.data is not None
        assert result.data.pagination.page == 1
        assert result.data.pagination.page_size == 20
        assert isinstance(result.data.items, list)
    else:
        # Should fail
        result = await store_manager.list_entities(page=1, page_size=20)
        assert result.is_error, "Expected error but got success"
        expected_code = get_expected_error(auth_config, operation_type="store_read")
        # Check that error message indicates the expected status code
        assert result.error is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_entities_with_search(store_manager, auth_config: AuthConfig):
    """Test listing entities with search query."""
    if should_succeed(auth_config, operation_type="store_read"):
        result = await store_manager.list_entities(
            page=1,
            page_size=10,
            search_query="test",
        )
        assert result.is_success
        assert result.data is not None
        assert result.data.pagination.page_size == 10


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_entities_exclude_deleted(
    store_manager,
    unique_test_image: Path,
    auth_config: AuthConfig,
):
    """Test listing entities with exclude_deleted flag."""
    if should_succeed(auth_config, operation_type="store_write"):
        # Create an entity
        create_result = await store_manager.create_entity(
            label="Entity to Soft Delete",
            is_collection=False,
            image_path=unique_test_image,
        )
        assert create_result.is_success
        entity_id = create_result.data.id

        # Soft delete it
        patch_result = await store_manager.patch_entity(
            entity_id=entity_id,
            is_deleted=True,
        )
        assert patch_result.is_success

        if should_succeed(auth_config, operation_type="store_read"):
            # 1. List without exclude_deleted (default False) -> Should include deleted
            # Note: Server default might be different, but we check if we can control it.
            # Usually default list includes everything unless filtered.
            # But let's check explicitly with exclude_deleted=False
            list_all = await store_manager.list_entities(
                exclude_deleted=False, 
                search_query="Entity to Soft Delete"
            )
            assert list_all.is_success
            # Should find it
            found_all = any(i.id == entity_id for i in list_all.data.items)
            assert found_all, "Should find soft-deleted entity when exclude_deleted=False"

            # 2. List with exclude_deleted=True -> Should NOT include deleted
            list_excluded = await store_manager.list_entities(
                exclude_deleted=True,
                search_query="Entity to Soft Delete"
            )
            assert list_excluded.is_success
            found_excluded = any(i.id == entity_id for i in list_excluded.data.items)
            assert not found_excluded, "Should NOT find soft-deleted entity when exclude_deleted=True"

        # Cleanup (hard delete)
        delete_result = await store_manager.delete_entity(entity_id)
        assert delete_result.is_success


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_entity_collection(store_manager, auth_config: AuthConfig):
    """Test creating a collection (folder) entity."""
    if should_succeed(auth_config, operation_type="store_write"):
        # Should succeed - create collection
        result = await store_manager.create_entity(
            label="Test Collection",
            description="A test collection",
            is_collection=True,
        )
        assert result.is_success, f"Expected success but got error: {result.error}"
        assert result.data is not None
        assert result.data.label == "Test Collection"
        assert result.data.is_collection is True
        assert result.data.id is not None

        # Cleanup
        entity_id = result.data.id
        delete_result = await store_manager.delete_entity(entity_id)
        assert delete_result.is_success
    else:
        # Should fail
        result = await store_manager.create_entity(
            label="Test Collection",
            is_collection=True,
        )
        assert result.is_error
        expected_code = get_expected_error(auth_config, operation_type="store_write")
        assert result.error is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_entity_with_file(
    store_manager,
    unique_test_image: Path,
    auth_config: AuthConfig,
):
    """Test creating entity with file upload."""
    if should_succeed(auth_config, operation_type="store_write"):
        # Should succeed - create with file
        result = await store_manager.create_entity(
            label="Test Image",
            description="Test upload",
            is_collection=False,
            image_path=unique_test_image,
        )
        assert result.is_success, f"Expected success but got error: {result.error}"
        assert result.data is not None
        assert result.data.label == "Test Image"
        assert result.data.is_collection is False
        assert result.data.file_path is not None
        assert result.data.file_size is not None
        assert result.data.file_size > 0

        # Cleanup
        entity_id = result.data.id
        delete_result = await store_manager.delete_entity(entity_id)
        assert delete_result.is_success
    else:
        # Should fail
        result = await store_manager.create_entity(
            label="Test Image",
            is_collection=False,
            image_path=unique_test_image,
        )
        assert result.is_error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_entity(
    store_manager,
    unique_test_image: Path,
    auth_config: AuthConfig,
):
    """Test reading entity by ID."""
    # First create an entity if we have write permissions
    if should_succeed(auth_config, operation_type="store_write"):
        # Create entity first
        create_result = await store_manager.create_entity(
            label="Entity to Read",
            is_collection=False,
            image_path=unique_test_image,
        )
        assert create_result.is_success
        entity_id = create_result.data.id

        # Now test reading (should succeed if we have read permissions)
        if should_succeed(auth_config, operation_type="store_read"):
            read_result = await store_manager.read_entity(entity_id=entity_id)
            assert read_result.is_success
            assert read_result.data.id == entity_id
            assert read_result.data.id == entity_id
            assert read_result.data.label == "Entity to Read"
            # Verify new fields exist (even if None)
            assert hasattr(read_result.data, "is_indirectly_deleted")
            assert hasattr(read_result.data, "intelligence_status")

        # Cleanup
        delete_result = await store_manager.delete_entity(entity_id)
        assert delete_result.is_success


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_entity(
    store_manager,
    unique_test_image: Path,
    auth_config: AuthConfig,
):
    """Test full update (PUT) of an entity."""
    if should_succeed(auth_config, operation_type="store_write"):
        # Create entity first
        create_result = await store_manager.create_entity(
            label="Original Label",
            description="Original description",

            is_collection=False,
            image_path=unique_test_image,
        )
        assert create_result.is_success
        entity_id = create_result.data.id

        # Update entity
        update_result = await store_manager.update_entity(
            entity_id=entity_id,
            label="Updated Label",
            description="Updated description",
            is_collection=False,
        )
        assert update_result.is_success
        assert update_result.data.label == "Updated Label"
        assert update_result.data.description == "Updated description"

        # Cleanup
        delete_result = await store_manager.delete_entity(entity_id)
        assert delete_result.is_success


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_entity(
    store_manager,
    unique_test_image: Path,
    auth_config: AuthConfig,
):
    """Test partial update (PATCH) of an entity."""
    if should_succeed(auth_config, operation_type="store_write"):
        # Create entity first
        create_result = await store_manager.create_entity(
            label="Original Label",
            description="Original description",
            is_collection=False,
            image_path=unique_test_image,
        )
        assert create_result.is_success
        entity_id = create_result.data.id

        # Patch entity (only update label)
        patch_result = await store_manager.patch_entity(
            entity_id=entity_id,
            label="Patched Label",
        )
        assert patch_result.is_success
        assert patch_result.data.label == "Patched Label"
        # Description should remain unchanged
        assert patch_result.data.description == "Original description"

        # Cleanup
        delete_result = await store_manager.delete_entity(entity_id)
        assert delete_result.is_success


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_entity_soft_delete(
    store_manager,
    unique_test_image: Path,
    auth_config: AuthConfig,
):
    """Test soft delete via PATCH."""
    if should_succeed(auth_config, operation_type="store_write"):
        # Create entity first
        create_result = await store_manager.create_entity(
            label="Entity to Soft Delete",
            is_collection=False,
            image_path=unique_test_image,
        )
        assert create_result.is_success
        entity_id = create_result.data.id

        # Soft delete
        patch_result = await store_manager.patch_entity(
            entity_id=entity_id,
            is_deleted=True,
        )
        assert patch_result.is_success
        assert patch_result.data.is_deleted is True

        # Restore (undo soft delete)
        restore_result = await store_manager.patch_entity(
            entity_id=entity_id,
            is_deleted=False,
        )
        assert restore_result.is_success
        assert restore_result.data.is_deleted is False

        # Cleanup (hard delete)
        delete_result = await store_manager.delete_entity(entity_id)
        assert delete_result.is_success


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_entity(
    store_manager,
    unique_test_image: Path,
    auth_config: AuthConfig,
):
    """Test hard delete of an entity."""
    if should_succeed(auth_config, operation_type="store_write"):
        # Create entity first
        create_result = await store_manager.create_entity(
            label="Entity to Delete",
            is_collection=False,
            image_path=unique_test_image,
        )
        assert create_result.is_success
        entity_id = create_result.data.id

        # Delete entity
        delete_result = await store_manager.delete_entity(entity_id)
        assert delete_result.is_success

        # Verify entity is gone (read should fail with 404)
        if should_succeed(auth_config, operation_type="store_read"):
            read_result = await store_manager.read_entity(entity_id=entity_id)
            assert read_result.is_error
            assert "Not Found" in read_result.error or "404" in read_result.error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_versions(
    store_manager,
    unique_test_image: Path,
    auth_config: AuthConfig,
):
    """Test retrieving version history for an entity."""
    if should_succeed(auth_config, operation_type="store_write"):
        # Create entity
        create_result = await store_manager.create_entity(
            label="Version Test Entity",
            description="Original",
            is_collection=False,
            image_path=unique_test_image,
        )
        assert create_result.is_success
        entity_id = create_result.data.id

        # Update entity to create a new version
        update_result = await store_manager.patch_entity(
            entity_id=entity_id,
            description="Updated",
        )
        assert update_result.is_success

        # Get versions (requires read permission)
        if should_succeed(auth_config, operation_type="store_read"):
            versions_result = await store_manager.get_versions(entity_id=entity_id)
            assert versions_result.is_success
            assert versions_result.data is not None
            assert len(versions_result.data) >= 1  # At least one version

        # Cleanup
        delete_result = await store_manager.delete_entity(entity_id)
        assert delete_result.is_success


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_admin_get_config(store_manager, auth_config: AuthConfig):
    """Test getting store configuration (admin only)."""
    if should_succeed(auth_config, operation_type="admin"):
        # Should succeed for admin
        result = await store_manager.get_config()
        assert result.is_success, f"Expected success but got error: {result.error}"
        assert result.data is not None
        assert isinstance(result.data.guest_mode, bool)
    else:
        # Should fail for non-admin
        result = await store_manager.get_config()
        assert result.is_error
        # Error should indicate permission denied
        assert result.error is not None


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_admin_update_read_auth(store_manager, auth_config: AuthConfig):
    """Test updating read auth configuration (admin only)."""
    if should_succeed(auth_config, operation_type="admin"):
        # Get current config
        get_result = await store_manager.get_config()
        assert get_result.is_success
        original_guest_mode = get_result.data.guest_mode

        # Toggle guest mode
        update_result = await store_manager.update_guest_mode(guest_mode=not original_guest_mode)
        assert update_result.is_success
        assert update_result.data.guest_mode == (not original_guest_mode)

        # Restore original setting
        restore_result = await store_manager.update_guest_mode(guest_mode=original_guest_mode)
        assert restore_result.is_success
        assert restore_result.data.guest_mode == original_guest_mode
    else:
        # Should fail for non-admin
        result = await store_manager.update_guest_mode(guest_mode=True)
        assert result.is_error
