"""Integration tests for MInsight endpoints."""

import sys
from pathlib import Path as PathlibPath

import pytest

sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
from conftest import AuthConfig, should_succeed


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.admin_only
async def test_get_m_insight_status(store_manager, auth_config: AuthConfig):
    """Test getting MInsight status."""
    if should_succeed(auth_config, operation_type="admin"):
        # Should succeed for admin
        result = await store_manager.get_m_insight_status()
        assert result.is_success, f"Expected success but got error: {result.error}"
        assert result.data is not None
        assert isinstance(result.data, dict)
        # We don't assert specific content as it depends on whether MInsight is running/connected
    else:
        # Should fail for non-admin
        result = await store_manager.get_m_insight_status()
        assert result.is_error
        # Error should indicate permission denied (403 or 401)
        assert result.error is not None
