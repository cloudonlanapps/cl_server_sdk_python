"""Integration tests for store system/audit operations."""

import sys
from pathlib import Path as PathlibPath
import pytest

sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
from conftest import AuthConfig, should_succeed


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_get_audit_report(store_manager, auth_config: AuthConfig):
    """Test getting system audit report (admin only)."""
    if should_succeed(auth_config, operation_type="admin"):
        # Should succeed for admin
        result = await store_manager.get_audit_report()
        assert result.is_success, f"Expected success but got error: {result.error}"
        assert result.data is not None
        
        # Verify report structure
        report = result.data
        assert hasattr(report, "orphaned_files")
        assert hasattr(report, "orphaned_faces")
        assert hasattr(report, "orphaned_vectors")
        assert hasattr(report, "orphaned_mqtt")
        assert isinstance(report.orphaned_files, list)
    else:
        # Should fail for non-admin
        result = await store_manager.get_audit_report()
        assert result.is_error
        assert "Forbidden" in str(result.error) or "403" in str(result.error)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_clear_orphans(store_manager, auth_config: AuthConfig):
    """Test clearing orphaned resources (admin only)."""
    if should_succeed(auth_config, operation_type="admin"):
        # Should succeed for admin
        result = await store_manager.clear_orphans()
        assert result.is_success, f"Expected success but got error: {result.error}"
        assert result.data is not None
        
        # Verify cleanup report structure
        report = result.data
        assert hasattr(report, "files_deleted")
        assert hasattr(report, "faces_deleted")
        assert hasattr(report, "vectors_deleted")
        assert hasattr(report, "mqtt_cleared")
        assert isinstance(report.files_deleted, int)
    else:
        # Should fail for non-admin
        result = await store_manager.clear_orphans()
        assert result.is_error
        assert "Forbidden" in str(result.error) or "403" in str(result.error)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_entity_id_autoincrement_no_reuse(store_manager, unique_test_image: PathlibPath):
    """Test that SQLite AUTOINCREMENT prevents ID reuse after deletion."""
    # 1. Create first entity
    res1 = await store_manager.create_entity(
        label="Entity One",
        is_collection=False,
        image_path=unique_test_image
    )
    assert res1.is_success
    id1 = res1.data.id

    # 2. Delete it (hard delete)
    del_res = await store_manager.delete_entity(id1, force=True)
    assert del_res.is_success

    # 3. Create second entity
    # Use a different unique image to avoid any MD5 collisions
    res2 = await store_manager.create_entity(
        label="Entity Two",
        is_collection=False,
        image_path=unique_test_image
    )
    assert res2.is_success
    id2 = res2.data.id

    # 4. Verify ID is NOT reused
    # With AUTOINCREMENT, id2 must be greater than id1 even if 1 was deleted
    assert id2 > id1, f"ID reuse detected! id1={id1}, id2={id2}. AUTOINCREMENT might be missing."
