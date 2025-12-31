"""Integration tests for clip_embedding plugin.

These tests require a running server, worker, and MQTT broker.
Tests run in multiple auth modes: admin, user-with-permission, user-no-permission, no-auth.
"""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from cl_client import ComputeClient
from httpx import HTTPStatusError

import sys
from pathlib import Path as PathlibPath
sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
from conftest import get_expected_error, should_succeed


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clip_embedding_http_polling(
    test_image: Path, client: ComputeClient, auth_config: dict[str, Any]
):
    """Test CLIP embedding with HTTP polling (secondary workflow)."""
    if should_succeed(auth_config, operation_type="plugin"):
        # Should succeed - run normal assertions
        job = await client.clip_embedding.embed_image(
            image=test_image,
            wait=True,
            timeout=30.0,
        )

        # Verify completion
        assert job.status == "completed"
        assert job.progress == 100
        assert job.task_output is not None

        # Verify embedding metadata
        assert "embedding_dim" in job.task_output
        assert job.task_output["embedding_dim"] == 512  # CLIP dimension
        assert "normalized" in job.task_output

        # Cleanup
        await client.delete_job(job.job_id)
    else:
        # Should fail - expect auth error
        expected_code = get_expected_error(auth_config, operation_type="plugin")
        with pytest.raises(HTTPStatusError) as exc_info:
            await client.clip_embedding.embed_image(
                image=test_image,
                wait=True,
                timeout=30.0,
            )
        assert exc_info.value.response.status_code == expected_code


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clip_embedding_mqtt_callbacks(
    test_image: Path, client: ComputeClient, auth_config: dict[str, Any]
):
    """Test CLIP embedding with MQTT callbacks (primary workflow)."""
    if should_succeed(auth_config, operation_type="plugin"):
        # Should succeed - run normal assertions
        # Verify MQTT connected
        assert client._mqtt._connected, "MQTT not connected"

        # Track callbacks
        progress_updates = []
        completion_event = asyncio.Event()
        final_job = None

        def on_progress(job):
            progress_updates.append((job.status, job.progress))

        def on_complete(job):
            nonlocal final_job
            final_job = job
            completion_event.set()

        # Submit with callbacks
        job = await client.clip_embedding.embed_image(
            image=test_image,
            on_progress=on_progress,
            on_complete=on_complete,
        )

        # Wait for completion
        await asyncio.wait_for(completion_event.wait(), timeout=30.0)

        # Verify callbacks were called
        assert len(progress_updates) > 0, "No progress updates received"
        assert final_job is not None, "Completion callback not called"
        assert final_job.status == "completed"

        # Note: MQTT callbacks don't include task_output, only status/progress
        # To verify output, fetch full job details via HTTP
        full_job = await client.get_job(job.job_id)
        assert full_job.task_output is not None
        assert "embedding_dim" in full_job.task_output
        assert full_job.task_output["embedding_dim"] == 512

        # Cleanup
        await client.delete_job(job.job_id)
    else:
        # Should fail - expect auth error (MQTT may connect but job submission fails)
        expected_code = get_expected_error(auth_config, operation_type="plugin")
        with pytest.raises(HTTPStatusError) as exc_info:
            await client.clip_embedding.embed_image(
                image=test_image,
                on_progress=lambda job: None,
                on_complete=lambda job: None,
            )
        assert exc_info.value.response.status_code == expected_code


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clip_embedding_both_callbacks(
    test_image: Path, client: ComputeClient, auth_config: dict[str, Any]
):
    """Test that both on_progress and on_complete callbacks work."""
    if should_succeed(auth_config, operation_type="plugin"):
        # Should succeed - run normal assertions
        progress_called = False
        complete_called = False
        completion_event = asyncio.Event()

        def on_progress(job):
            nonlocal progress_called
            progress_called = True

        def on_complete(job):
            nonlocal complete_called
            complete_called = True
            completion_event.set()

        job = await client.clip_embedding.embed_image(
            image=test_image,
            on_progress=on_progress,
            on_complete=on_complete,
        )

        await asyncio.wait_for(completion_event.wait(), timeout=30.0)

        assert progress_called, "on_progress was not called"
        assert complete_called, "on_complete was not called"

        await client.delete_job(job.job_id)
    else:
        # Should fail - expect auth error
        expected_code = get_expected_error(auth_config, operation_type="plugin")
        with pytest.raises(HTTPStatusError) as exc_info:
            await client.clip_embedding.embed_image(
                image=test_image,
                on_progress=lambda job: None,
                on_complete=lambda job: None,
            )
        assert exc_info.value.response.status_code == expected_code


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clip_embedding_file_download(
    test_image: Path, client: ComputeClient, auth_config: dict[str, Any]
):
    """Test downloading generated embedding file."""
    if should_succeed(auth_config, operation_type="plugin"):
        # Should succeed - run normal assertions
        import tempfile

        # Generate embedding
        job = await client.clip_embedding.embed_image(
            image=test_image,
            wait=True,
        )

        assert job.status == "completed"
        assert job.task_output is not None

        # Download the output file (embedding is saved as .npy file)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "clip_embedding.npy"
            await client.download_job_file(
                job_id=job.job_id,
                file_path="output/clip_embedding.npy",
                dest=output_path
            )

            # Verify file was downloaded and has content
            assert output_path.exists()
            assert output_path.stat().st_size > 0

        # Cleanup
        await client.delete_job(job.job_id)
    else:
        # Should fail - expect auth error
        expected_code = get_expected_error(auth_config, operation_type="plugin")
        with pytest.raises(HTTPStatusError) as exc_info:
            await client.clip_embedding.embed_image(
                image=test_image,
                wait=True,
            )
        assert exc_info.value.response.status_code == expected_code


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clip_embedding_worker_capabilities(
    test_image: Path, client: ComputeClient, auth_config: dict[str, Any]
):
    """Test worker capability detection.

    Note: Workers broadcast capabilities on a heartbeat (default 30s).
    For faster tests, start worker with shorter heartbeat:
        MQTT_HEARTBEAT_INTERVAL=2 uv run compute-worker --worker-id test-worker --tasks clip_embedding
    """
    if not should_succeed(auth_config, operation_type="plugin"):
        # Skip worker capability tests in auth failure modes
        # (This test is about infrastructure, not auth)
        pytest.skip("Skipping worker capability test in auth failure mode")

    # Wait for workers to broadcast (retry with timeout)
    max_wait = 35  # Slightly longer than default heartbeat
    check_interval = 1.0

    for i in range(int(max_wait / check_interval)):
        workers = client._mqtt.get_worker_capabilities()

        if len(workers) > 0:
            # Check if any worker has clip_embedding capability
            has_capability = any(
                "clip_embedding" in worker.capabilities
                for worker in workers.values()
            )
            if has_capability:
                # Success!
                return

        # Wait before next check
        if i < int(max_wait / check_interval) - 1:
            await asyncio.sleep(check_interval)

    # Final check and report
    workers = client._mqtt.get_worker_capabilities()
    assert len(workers) > 0, (
        f"No workers detected after {max_wait}s. "
        "Ensure worker is running with: "
        "uv run compute-worker --worker-id test-worker --tasks clip_embedding"
    )

    has_capability = any(
        "clip_embedding" in worker.capabilities
        for worker in workers.values()
    )
    assert has_capability, (
        f"No worker with clip_embedding capability. "
        f"Found workers: {list(workers.keys())} "
        f"with capabilities: {[w.capabilities for w in workers.values()]}"
    )
