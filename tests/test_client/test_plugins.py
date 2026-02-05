"""Unit tests for plugin clients."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cl_client import ComputeClient
from cl_client.models import JobResponse
from cl_client.plugins.base import BasePluginClient
from cl_client.plugins.clip_embedding import ClipEmbeddingClient
from cl_client.plugins.dino_embedding import DinoEmbeddingClient
from cl_client.plugins.exif import ExifClient
from cl_client.plugins.face_detection import FaceDetectionClient
from cl_client.plugins.face_embedding import FaceEmbeddingClient
from cl_client.plugins.hash import HashClient
from cl_client.plugins.hls_streaming import HlsStreamingClient
from cl_client.plugins.image_conversion import ImageConversionClient
from cl_client.plugins.media_thumbnail import MediaThumbnailClient


@pytest.fixture
def mock_compute_client():
    """Create a mock ComputeClient."""
    client = MagicMock(spec=ComputeClient)
    client.base_url = "http://localhost:8002"
    client._mqtt = MagicMock()
    client.auth = MagicMock()
    client.auth.get_headers.return_value = {}

    # Mock get_job by default - will be overridden in individual tests
    # Returns a simple job that matches the job_id
    client.get_job = AsyncMock()
    return client


@pytest.fixture
def temp_image_file(tmp_path: Path) -> Path:
    """Create a temporary image file for testing."""
    image_file = tmp_path / "test_image.jpg"
    image_file.write_bytes(b"fake image data")
    return image_file


@pytest.fixture
def temp_video_file(tmp_path: Path) -> Path:
    """Create a temporary video file for testing."""
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"fake video data")
    return video_file


# BasePluginClient tests


def test_base_plugin_init(mock_compute_client):
    """Test BasePluginClient initialization."""
    plugin = BasePluginClient(mock_compute_client, task_type="clip_embedding")

    assert plugin.client == mock_compute_client
    assert plugin.task_type == "clip_embedding"
    assert plugin.endpoint == "/jobs/clip_embedding"


@pytest.mark.asyncio
async def test_base_plugin_submit_job_not_implemented(mock_compute_client):
    """Test that submit_job raises NotImplementedError."""
    plugin = BasePluginClient(mock_compute_client, task_type="clip_embedding")

    with pytest.raises(NotImplementedError):
        await plugin.submit_job({})


@pytest.mark.asyncio
async def test_base_plugin_submit_with_files(mock_compute_client, temp_image_file):
    """Test BasePluginClient.submit_with_files."""
    plugin = BasePluginClient(mock_compute_client, task_type="media_thumbnail")

    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "job_id": "test-job-123",
        "task_type": "media_thumbnail",
        "status": "queued",
        "progress": 0,
        "priority": 5,
        "created_at": 1234567890,
        "params": {},
    }
    mock_response.raise_for_status = MagicMock()

    # Mock http_submit_job
    mock_compute_client.http_submit_job = AsyncMock(return_value="test-job-123")

    # Mock get_job to return matching job
    mock_compute_client.get_job.return_value = JobResponse(
        job_id="test-job-123",
        task_type="media_thumbnail",
        status="queued",
        progress=0,
        priority=7,
        created_at=1234567890,
    )

    # Submit job
    job = await plugin.submit_with_files(
        files={"file": temp_image_file},
        params={"width": 256, "height": 256},
        priority=7,
    )

    # Verify http_submit_job was called
    mock_compute_client.http_submit_job.assert_called_once()
    call_args = mock_compute_client.http_submit_job.call_args
    assert "/jobs/media_thumbnail" in call_args[0][0]

    # Verify response
    assert isinstance(job, JobResponse)
    assert job.job_id == "test-job-123"
    assert job.status == "queued"


@pytest.mark.asyncio
async def test_base_plugin_submit_with_files_and_wait(mock_compute_client, temp_image_file):
    """Test BasePluginClient.submit_with_files with wait=True."""
    plugin = BasePluginClient(mock_compute_client, task_type="media_thumbnail")

    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "job_id": "test-job-123",
        "task_type": "media_thumbnail",
        "status": "queued",
        "progress": 0,
        "priority": 5,
        "created_at": 1234567890,
        "params": {},
    }

    # Mock http_submit_job
    mock_compute_client.http_submit_job = AsyncMock(return_value="test-job-123")

    # Mock get_job (called first)
    queued_job = JobResponse(
        job_id="test-job-123",
        task_type="media_thumbnail",
        status="queued",
        progress=0,
        created_at=1234567890,
    )
    mock_compute_client.get_job = AsyncMock(return_value=queued_job)

    # Mock wait_for_job (called when wait=True)
    completed_job = JobResponse(
        job_id="test-job-123",
        task_type="media_thumbnail",
        status="completed",
        progress=100,
        created_at=1234567890,
    )
    mock_compute_client.wait_for_job = AsyncMock(return_value=completed_job)

    # Submit job with wait
    job = await plugin.submit_with_files(
        files={"file": temp_image_file},
        wait=True,
        timeout=30.0,
    )

    # Verify wait_for_job was called
    mock_compute_client.wait_for_job.assert_called_once_with(
        job_id="test-job-123", timeout=30.0
    )

    # Verify response
    assert job.status == "completed"


@pytest.mark.asyncio
async def test_base_plugin_submit_with_callbacks(mock_compute_client, temp_image_file):
    """Test BasePluginClient.submit_with_files with callbacks."""
    plugin = BasePluginClient(mock_compute_client, task_type="media_thumbnail")

    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "job_id": "test-job-123",
        "task_type": "media_thumbnail",
        "status": "queued",
        "progress": 0,
        "priority": 5,
        "created_at": 1234567890,
        "params": {},
    }

    # Mock http_submit_job
    mock_compute_client.http_submit_job = AsyncMock(return_value="test-job-123")

    # Mock get_job to return matching job
    mock_compute_client.get_job = AsyncMock(return_value=JobResponse(
        job_id="test-job-123",
        task_type="media_thumbnail",
        status="queued",
        progress=0,
        created_at=1234567890,
    ))

    # Mock subscribe_job_updates
    mock_compute_client.mqtt_subscribe_job_updates = MagicMock(return_value="sub-123")

    # Callbacks
    on_progress = MagicMock()
    on_complete = MagicMock()

    # Submit job with callbacks
    job = await plugin.submit_with_files(
        files={"file": temp_image_file},
        on_progress=on_progress,
        on_complete=on_complete,
    )

    # Verify subscription
    mock_compute_client.mqtt_subscribe_job_updates.assert_called_once_with(
        job_id="test-job-123",
        on_progress=on_progress,
        on_complete=on_complete,
        task_type="media_thumbnail",
    )

    # Verify response
    assert job.job_id == "test-job-123"


@pytest.mark.asyncio
async def test_base_plugin_file_not_found(mock_compute_client, tmp_path):
    """Test that FileNotFoundError is raised for missing files."""
    plugin = BasePluginClient(mock_compute_client, task_type="media_thumbnail")

    missing_file = tmp_path / "missing.jpg"

    with pytest.raises(FileNotFoundError):
        await plugin.submit_with_files(files={"file": missing_file})


# Individual plugin tests


def test_clip_embedding_init(mock_compute_client):
    """Test ClipEmbeddingClient initialization."""
    plugin = ClipEmbeddingClient(mock_compute_client)
    assert plugin.task_type == "clip_embedding"


@pytest.mark.asyncio
async def test_clip_embedding_embed_image(mock_compute_client, temp_image_file):
    """Test ClipEmbeddingClient.embed_image."""
    plugin = ClipEmbeddingClient(mock_compute_client)

    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "job_id": "test-job-123",
        "task_type": "clip_embedding",
        "status": "queued",
        "progress": 0,
        "priority": 5,
        "created_at": 1234567890,
        "params": {},
    }

    # Mock http_submit_job
    mock_compute_client.http_submit_job = AsyncMock(return_value="test-job-123")

    # Mock get_job to return matching job
    mock_compute_client.get_job.return_value = JobResponse(
        job_id="test-job-123",
        task_type="clip_embedding",
        status="queued",
        progress=0,
        created_at=1234567890,
    )

    job = await plugin.embed_image(image=temp_image_file)

    assert job.job_id == "test-job-123"
    assert job.task_type == "clip_embedding"


def test_dino_embedding_init(mock_compute_client):
    """Test DinoEmbeddingClient initialization."""
    plugin = DinoEmbeddingClient(mock_compute_client)
    assert plugin.task_type == "dino_embedding"


def test_exif_init(mock_compute_client):
    """Test ExifClient initialization."""
    plugin = ExifClient(mock_compute_client)
    assert plugin.task_type == "exif"


def test_face_detection_init(mock_compute_client):
    """Test FaceDetectionClient initialization."""
    plugin = FaceDetectionClient(mock_compute_client)
    assert plugin.task_type == "face_detection"


def test_face_embedding_init(mock_compute_client):
    """Test FaceEmbeddingClient initialization."""
    plugin = FaceEmbeddingClient(mock_compute_client)
    assert plugin.task_type == "face_embedding"


def test_hash_init(mock_compute_client):
    """Test HashClient initialization."""
    plugin = HashClient(mock_compute_client)
    assert plugin.task_type == "hash"


def test_hls_streaming_init(mock_compute_client):
    """Test HlsStreamingClient initialization."""
    plugin = HlsStreamingClient(mock_compute_client)
    assert plugin.task_type == "hls_streaming"


def test_image_conversion_init(mock_compute_client):
    """Test ImageConversionClient initialization."""
    plugin = ImageConversionClient(mock_compute_client)
    assert plugin.task_type == "image_conversion"


@pytest.mark.asyncio
async def test_image_conversion_convert(mock_compute_client, temp_image_file):
    """Test ImageConversionClient.convert."""
    plugin = ImageConversionClient(mock_compute_client)

    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "job_id": "test-job-456",
        "task_type": "image_conversion",
        "status": "queued",
        "progress": 0,
        "priority": 5,
        "created_at": 1234567890,
        "params": {},
    }

    # Mock http_submit_job
    mock_compute_client.http_submit_job = AsyncMock(return_value="test-job-456")

    # Mock get_job to return matching job
    mock_compute_client.get_job.return_value = JobResponse(
        job_id="test-job-456",
        task_type="image_conversion",
        status="queued",
        progress=0,
        created_at=1234567890,
    )

    job = await plugin.convert(
        image=temp_image_file,
        output_format="png",
        quality=90,
    )

    assert job.job_id == "test-job-456"
    assert job.task_type == "image_conversion"


def test_media_thumbnail_init(mock_compute_client):
    """Test MediaThumbnailClient initialization."""
    plugin = MediaThumbnailClient(mock_compute_client)
    assert plugin.task_type == "media_thumbnail"


@pytest.mark.asyncio
async def test_media_thumbnail_generate(mock_compute_client, temp_image_file):
    """Test MediaThumbnailClient.generate."""
    plugin = MediaThumbnailClient(mock_compute_client)

    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "job_id": "test-job-789",
        "task_type": "media_thumbnail",
        "status": "queued",
        "progress": 0,
        "priority": 5,
        "created_at": 1234567890,
        "params": {},
    }

    # Mock http_submit_job
    mock_compute_client.http_submit_job = AsyncMock(return_value="test-job-789")

    # Mock get_job to return matching job
    mock_compute_client.get_job.return_value = JobResponse(
        job_id="test-job-789",
        task_type="media_thumbnail",
        status="queued",
        progress=0,
        created_at=1234567890,
    )

    job = await plugin.generate(
        media=temp_image_file,
        width=256,
        height=256,
    )

    assert job.job_id == "test-job-789"
    assert job.task_type == "media_thumbnail"


# Test plugin lazy loading in ComputeClient


def test_compute_client_lazy_load_clip_embedding():
    """Test lazy loading of ClipEmbeddingClient."""
    with patch("cl_client.compute_client.get_mqtt_monitor") as mock_mqtt:
        with patch("cl_client.compute_client.httpx.AsyncClient"):
            # Mock the get_mqtt_monitor to return a mock MQTTJobMonitor
            mock_mqtt.return_value = MagicMock()
            client = ComputeClient()

            # Access plugin property
            plugin = client.clip_embedding

            # Verify type
            assert isinstance(plugin, ClipEmbeddingClient)

            # Verify same instance on second access
            assert client.clip_embedding is plugin


def test_compute_client_lazy_load_all_plugins():
    """Test lazy loading of all 9 plugins."""
    with patch("cl_client.compute_client.get_mqtt_monitor") as mock_mqtt:
        with patch("cl_client.compute_client.httpx.AsyncClient"):
            # Mock the get_mqtt_monitor to return a mock MQTTJobMonitor
            mock_mqtt.return_value = MagicMock()
            client = ComputeClient()

            # Test all plugin properties
            assert isinstance(client.clip_embedding, ClipEmbeddingClient)
            assert isinstance(client.dino_embedding, DinoEmbeddingClient)
            assert isinstance(client.exif, ExifClient)
            assert isinstance(client.face_detection, FaceDetectionClient)
            assert isinstance(client.face_embedding, FaceEmbeddingClient)
            assert isinstance(client.hash, HashClient)
            assert isinstance(client.hls_streaming, HlsStreamingClient)
            assert isinstance(client.image_conversion, ImageConversionClient)
            assert isinstance(client.media_thumbnail, MediaThumbnailClient)
