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
