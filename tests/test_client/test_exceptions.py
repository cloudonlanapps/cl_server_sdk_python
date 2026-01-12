"""Tests for exceptions.py"""

from cl_client.exceptions import (
    AuthenticationError,
    ComputeClientError,
    JobFailedError,
    JobNotFoundError,
    PermissionError,
    WorkerUnavailableError,
)
from cl_client.models import JobResponse


def test_compute_client_error():
    """Test base ComputeClientError."""
    error = ComputeClientError("Test error")
    assert str(error) == "Test error"
    assert isinstance(error, Exception)


def test_job_not_found_error():
    """Test JobNotFoundError."""
    error = JobNotFoundError("test-123")
    assert "test-123" in str(error)
    assert error.job_id == "test-123"
    assert isinstance(error, ComputeClientError)


def test_job_failed_error():
    """Test JobFailedError."""
    job = JobResponse(
        job_id="test-123",
        task_type="clip_embedding",
        status="failed",
        progress=50,
        created_at=1234567890,
        error_message="Something went wrong"
    )

    error = JobFailedError(job)
    assert "test-123" in str(error)
    assert "Something went wrong" in str(error)
    assert error.job == job
    assert isinstance(error, ComputeClientError)


def test_authentication_error():
    """Test AuthenticationError."""
    error = AuthenticationError("Unauthorized")
    assert isinstance(error, ComputeClientError)


def test_permission_error():
    """Test PermissionError."""
    error = PermissionError("Forbidden")
    assert isinstance(error, ComputeClientError)


def test_worker_unavailable_error():
    """Test WorkerUnavailableError."""
    error = WorkerUnavailableError(
        "clip_embedding",
        {"dino_embedding": 1, "exif": 1}
    )

    assert "clip_embedding" in str(error)
    assert error.task_type == "clip_embedding"
    assert error.available_capabilities == {"dino_embedding": 1, "exif": 1}
    assert isinstance(error, ComputeClientError)
