"""Shared test fixtures for CLI tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cl_client.models import JobResponse


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


@pytest.fixture
def mock_compute_client():
    """Create a mock ComputeClient for CLI testing."""
    with patch("cl_client_cli.main.ComputeClient") as mock_client_class:
        # Create mock client instance
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock plugin clients
        mock_client.clip_embedding = MagicMock()
        mock_client.dino_embedding = MagicMock()
        mock_client.exif = MagicMock()
        mock_client.face_detection = MagicMock()
        mock_client.face_embedding = MagicMock()
        mock_client.hash = MagicMock()
        mock_client.hls_streaming = MagicMock()
        mock_client.image_conversion = MagicMock()
        mock_client.media_thumbnail = MagicMock()

        # Configure the class to return our mock instance
        mock_client_class.return_value = mock_client

        yield mock_client


@pytest.fixture
def completed_job() -> JobResponse:
    """Create a completed job response."""
    return JobResponse(
        job_id="test-job-123",
        task_type="clip_embedding",
        status="completed",
        progress=100,
        params={},
        task_output={"embedding": [0.1] * 512},
        priority=5,
        created_at=1234567890000,
        completed_at=1234567891000,
    )


@pytest.fixture
def queued_job() -> JobResponse:
    """Create a queued job response."""
    return JobResponse(
        job_id="test-job-123",
        task_type="clip_embedding",
        status="queued",
        progress=0,
        params={},
        priority=5,
        created_at=1234567890000,
    )


@pytest.fixture
def failed_job() -> JobResponse:
    """Create a failed job response."""
    return JobResponse(
        job_id="test-job-123",
        task_type="clip_embedding",
        status="failed",
        progress=50,
        params={},
        error_message="Test error",
        priority=5,
        created_at=1234567890000,
        completed_at=1234567891000,
    )
