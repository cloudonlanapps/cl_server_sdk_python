"""Tests for dynamic header updates in ComputeClient."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from cl_client.compute_client import ComputeClient
from cl_client.auth import AuthProvider
from cl_client.server_config import ServerConfig

@pytest.mark.asyncio
async def test_dynamic_header_updates(mqtt_url):
    """Verify that ComputeClient uses fresh headers for each request."""
    
    # Mock AuthProvider
    mock_auth = Mock(spec=AuthProvider)
    mock_auth.refresh_token_if_needed = AsyncMock()
    
    # Setup get_headers to return different values on subsequent calls
    mock_auth.get_headers.side_effect = [
        {"Authorization": "Bearer token1"},  # Init call
        {"Authorization": "Bearer token2"},  # First request
        {"Authorization": "Bearer token3"},  # Second request
    ]
    
    # Initialize client
    client = ComputeClient(
        base_url="http://test.local",
        auth_provider=mock_auth,
        server_config=ServerConfig(
            mqtt_url=mqtt_url,
            auth_url="http://auth.local",
            compute_url="http://test.local",
        )
    )
    
    # Verify init called get_headers once
    assert mock_auth.get_headers.call_count == 1
    
    # Mock httpx session
    with patch.object(client._session, 'get', new_callable=AsyncMock) as mock_get:
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "job1", 
            "status": "completed", 
            "task_type": "test",
            "created_at": 1234567890,
            "updated_at": 1234567890
        }
        mock_get.return_value = mock_response
        
        # Make first request
        await client.get_job("job1")
        
        # Verify first request used token2
        mock_get.assert_called_with(
            "/jobs/job1", 
            headers={"Authorization": "Bearer token2"}
        )
        
        # Verify refresh was checked
        mock_auth.refresh_token_if_needed.assert_called()
        
        # Make second request
        await client.get_job("job1")
        
        # Verify second request used token3
        mock_get.assert_called_with(
            "/jobs/job1", 
            headers={"Authorization": "Bearer token3"}
        )
        
    await client.close()
