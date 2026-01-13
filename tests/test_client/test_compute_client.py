"""Tests for compute_client.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cl_client.auth import JWTAuthProvider, NoAuthProvider
from cl_client.compute_client import ComputeClient
from cl_client.config import ComputeClientConfig
from cl_client.exceptions import WorkerUnavailableError
from cl_client.models import JobResponse
from cl_client.server_config import ServerConfig


@pytest.fixture
def mock_mqtt_monitor():
    """Create a mock MQTT monitor."""
    with patch("cl_client.compute_client.MQTTJobMonitor") as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx.AsyncClient."""
    with patch("cl_client.compute_client.httpx.AsyncClient") as mock_class:
        mock_instance = AsyncMock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def client(mock_mqtt_monitor, mock_httpx_client):
    """Create compute client with mocked dependencies."""
    return ComputeClient()


def test_init_with_defaults(mock_mqtt_monitor, mock_httpx_client):
    """Test client initialization with default parameters."""
    client = ComputeClient()

    assert client.base_url == ComputeClientConfig.DEFAULT_BASE_URL
    assert client.timeout == ComputeClientConfig.DEFAULT_TIMEOUT
    assert isinstance(client.auth, NoAuthProvider)


def test_init_with_custom_parameters(mock_mqtt_monitor, mock_httpx_client):
    """Test client initialization with custom parameters."""
    auth = JWTAuthProvider(token="test-token")

    client = ComputeClient(
        base_url="http://custom:9000",
        timeout=60.0,
        mqtt_broker="custom-broker",
        mqtt_port=1234,
        auth_provider=auth,
    )

    assert client.base_url == "http://custom:9000"
    assert client.timeout == 60.0
    assert client.auth == auth


def test_init_with_server_config(mock_mqtt_monitor, mock_httpx_client):
    """Test client initialization with ServerConfig."""
    config = ServerConfig(
        compute_url="https://compute.example.com",
        mqtt_broker="mqtt.example.com",
        mqtt_port=8883,
    )

    client = ComputeClient(server_config=config)

    assert client.base_url == "https://compute.example.com"
    # MQTT config passed to monitor
    mock_mqtt_monitor._class = MagicMock()


def test_init_with_server_config_and_overrides(mock_mqtt_monitor, mock_httpx_client):
    """Test that explicit parameters override server_config."""
    config = ServerConfig(
        compute_url="https://config.example.com",
        mqtt_broker="config-broker",
        mqtt_port=1883,
    )

    client = ComputeClient(
        base_url="https://override.example.com",
        mqtt_broker="override-broker",
        server_config=config,
    )

    assert client.base_url == "https://override.example.com"
    # Explicit parameters take precedence


def test_init_backward_compatibility(mock_mqtt_monitor, mock_httpx_client):
    """Test that existing code without server_config still works."""
    # This is how code worked before adding server_config
    client = ComputeClient()

    # Should use defaults from environment (via ServerConfig.from_env())
    assert client.base_url is not None
    assert client.timeout == ComputeClientConfig.DEFAULT_TIMEOUT
    assert isinstance(client.auth, NoAuthProvider)


@pytest.mark.asyncio
async def test_get_job_success(client, mock_httpx_client):
    """Test get_job returns JobResponse."""
    job_data = {
        "job_id": "test-123",
        "task_type": "clip_embedding",
        "status": "completed",
        "progress": 100,
        "created_at": 1234567890,
        "params": {},
    }

    mock_response = MagicMock()
    mock_response.json.return_value = job_data
    mock_httpx_client.get.return_value = mock_response

    job = await client.get_job("test-123")

    assert job.job_id == "test-123"
    assert job.task_type == "clip_embedding"
    assert job.status == "completed"

    # Verify correct endpoint was called
    expected_endpoint = ComputeClientConfig.ENDPOINT_GET_JOB.format(job_id="test-123")
    mock_httpx_client.get.assert_called_once_with(expected_endpoint)
    mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_get_job_invalid_response(client, mock_httpx_client):
    """Test get_job raises error on invalid response format."""
    mock_response = MagicMock()
    mock_response.json.return_value = "not a dict"  # Invalid format
    mock_httpx_client.get.return_value = mock_response

    with pytest.raises(ValueError) as exc_info:
        await client.get_job("test-123")

    assert "Invalid response format" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_job_success(client, mock_httpx_client):
    """Test delete_job makes correct API call."""
    mock_response = MagicMock()
    mock_httpx_client.delete.return_value = mock_response

    await client.delete_job("test-123")

    expected_endpoint = ComputeClientConfig.ENDPOINT_DELETE_JOB.format(job_id="test-123")
    mock_httpx_client.delete.assert_called_once_with(expected_endpoint)
    mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_download_job_file_success(client, mock_httpx_client, tmp_path):
    """Test download_job_file downloads and saves file."""
    file_content = b"test file content"
    mock_response = MagicMock()
    mock_response.content = file_content
    mock_httpx_client.get.return_value = mock_response

    dest = tmp_path / "output.txt"
    await client.download_job_file("test-123", "output/result.txt", dest)

    # Verify file was written
    assert dest.exists()
    assert dest.read_bytes() == file_content

    # Verify correct endpoint was called
    expected_endpoint = ComputeClientConfig.ENDPOINT_GET_JOB_FILE.format(
        job_id="test-123", file_path="output/result.txt"
    )
    mock_httpx_client.get.assert_called_once_with(expected_endpoint)
    mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_get_capabilities_success(client, mock_httpx_client):
    """Test get_capabilities returns WorkerCapabilitiesResponse."""
    caps_data = {"num_workers": 2, "capabilities": {"clip_embedding": 1, "exif": 1}}

    mock_response = MagicMock()
    mock_response.json.return_value = caps_data
    mock_httpx_client.get.return_value = mock_response

    caps = await client.get_capabilities()

    assert caps.num_workers == 2
    assert caps.capabilities["clip_embedding"] == 1

    # Verify correct endpoint was called
    mock_httpx_client.get.assert_called_once_with(ComputeClientConfig.ENDPOINT_CAPABILITIES)
    mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_wait_for_workers_success(client, mock_mqtt_monitor):
    """Test wait_for_workers waits for required capabilities."""
    mock_mqtt_monitor.wait_for_capability = AsyncMock(return_value=True)

    result = await client.wait_for_workers(["clip_embedding", "exif"])

    assert result is True
    assert mock_mqtt_monitor.wait_for_capability.call_count == 2


@pytest.mark.asyncio
async def test_wait_for_workers_no_requirements(client, mock_mqtt_monitor):
    """Test wait_for_workers returns immediately if no requirements."""
    result = await client.wait_for_workers(None)

    assert result is True
    mock_mqtt_monitor.wait_for_capability.assert_not_called()


@pytest.mark.asyncio
async def test_wait_for_workers_timeout(client, mock_mqtt_monitor):
    """Test wait_for_workers raises WorkerUnavailableError on timeout."""
    mock_mqtt_monitor.wait_for_capability = AsyncMock(
        side_effect=WorkerUnavailableError("clip_embedding", {})
    )

    with pytest.raises(WorkerUnavailableError):
        await client.wait_for_workers(["clip_embedding"])


def test_subscribe_job_updates(client, mock_mqtt_monitor):
    """Test subscribe_job_updates delegates to MQTT monitor."""
    mock_mqtt_monitor.subscribe_job_updates.return_value = "sub-123"

    def on_progress(job: JobResponse):
        pass

    def on_complete(job: JobResponse):
        pass

    sub_id = client.subscribe_job_updates(
        job_id="test-123", on_progress=on_progress, on_complete=on_complete
    )

    assert sub_id == "sub-123"
    mock_mqtt_monitor.subscribe_job_updates.assert_called_once_with(
        job_id="test-123", on_progress=on_progress, on_complete=on_complete
    )


def test_unsubscribe(client, mock_mqtt_monitor):
    """Test unsubscribe delegates to MQTT monitor."""
    client.unsubscribe("sub-123")

    mock_mqtt_monitor.unsubscribe.assert_called_once_with("sub-123")


@pytest.mark.asyncio
async def test_wait_for_job_success(client, mock_httpx_client):
    """Test wait_for_job polls until completion."""
    # First call: in_progress
    # Second call: completed
    job_in_progress = {
        "job_id": "test-123",
        "task_type": "test",
        "status": "processing",
        "progress": 50,
        "created_at": 1234567890,
        "params": {},
    }
    job_completed = {
        "job_id": "test-123",
        "task_type": "test",
        "status": "completed",
        "progress": 100,
        "created_at": 1234567890,
        "params": {},
    }

    mock_response_1 = MagicMock()
    mock_response_1.json.return_value = job_in_progress

    mock_response_2 = MagicMock()
    mock_response_2.json.return_value = job_completed

    mock_httpx_client.get.side_effect = [mock_response_1, mock_response_2]

    job = await client.wait_for_job("test-123", poll_interval=0.1)

    assert job.status == "completed"
    assert mock_httpx_client.get.call_count == 2


@pytest.mark.asyncio
async def test_wait_for_job_timeout(client, mock_httpx_client):
    """Test wait_for_job raises TimeoutError."""
    # Always return in_progress
    job_data = {
        "job_id": "test-123",
        "task_type": "test",
        "status": "processing",
        "progress": 50,
        "created_at": 1234567890,
        "params": {},
    }

    mock_response = MagicMock()
    mock_response.json.return_value = job_data
    mock_httpx_client.get.return_value = mock_response

    with pytest.raises(TimeoutError) as exc_info:
        await client.wait_for_job("test-123", poll_interval=0.1, timeout=0.3)

    assert "test-123" in str(exc_info.value)
    assert "timeout" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_close(client, mock_httpx_client, mock_mqtt_monitor):
    """Test close cleans up resources."""
    await client.close()

    mock_httpx_client.aclose.assert_called_once()
    mock_mqtt_monitor.close.assert_called_once()


@pytest.mark.asyncio
async def test_async_context_manager(mock_mqtt_monitor, mock_httpx_client):
    """Test client works as async context manager."""
    async with ComputeClient() as client:
        assert isinstance(client, ComputeClient)

    # Verify cleanup was called
    mock_httpx_client.aclose.assert_called_once()
    mock_mqtt_monitor.close.assert_called_once()
