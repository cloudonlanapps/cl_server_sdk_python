"""Tests for models.py"""

from cl_client.models import JobResponse, WorkerCapabilitiesResponse, WorkerCapability


def test_job_response_basic():
    """Test basic JobResponse creation."""
    job = JobResponse(
        job_id="test-123",
        task_type="clip_embedding",
        status="completed",
        progress=100,
        created_at=1234567890,
    )

    assert job.job_id == "test-123"
    assert job.task_type == "clip_embedding"
    assert job.status == "completed"
    assert job.progress == 100
    assert job.params == {}
    assert job.task_output is None


def test_job_response_with_output():
    """Test JobResponse with task_output."""
    job = JobResponse(
        job_id="test-123",
        task_type="clip_embedding",
        status="completed",
        progress=100,
        created_at=1234567890,
        task_output={"embedding": [0.1, 0.2, 0.3]},
    )

    assert job.task_output is not None
    assert "embedding" in job.task_output
    assert isinstance(job.task_output["embedding"], list)


def test_worker_capabilities_response():
    """Test WorkerCapabilitiesResponse."""
    caps = WorkerCapabilitiesResponse(
        num_workers=2,
        capabilities={"clip_embedding": 1, "dino_embedding": 1}
    )

    assert caps.num_workers == 2
    assert caps.capabilities["clip_embedding"] == 1
    assert caps.capabilities["dino_embedding"] == 1


def test_worker_capability():
    """Test WorkerCapability."""
    worker = WorkerCapability(
        worker_id="worker-1",
        capabilities=["clip_embedding", "dino_embedding"],
        idle_count=1,
        timestamp=1234567890
    )

    assert worker.worker_id == "worker-1"
    assert len(worker.capabilities) == 2
    assert "clip_embedding" in worker.capabilities
    assert worker.idle_count == 1
