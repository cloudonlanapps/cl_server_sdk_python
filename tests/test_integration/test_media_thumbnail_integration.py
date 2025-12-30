"""Integration tests for media_thumbnail plugin.

These tests require a running server, worker, and MQTT broker.
"""

import asyncio
from pathlib import Path

import pytest
from cl_client import ComputeClient




@pytest.mark.integration
@pytest.mark.asyncio
async def test_media_thumbnail_http_polling(test_image: Path):
    """Test media_thumbnail with HTTP polling (secondary workflow)."""
    async with ComputeClient() as client:
        # Submit and wait for completion
        job = await client.media_thumbnail.generate(
            media=test_image,
            width=256,
            height=256,
            wait=True,
            timeout=30.0,
        )
        
        # Verify completion
        assert job.status == "completed"
        assert job.progress == 100
        assert job.task_output is not None
        
        # Cleanup
        await client.delete_job(job.job_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_media_thumbnail_mqtt_callbacks(test_image: Path):
    """Test media_thumbnail with MQTT callbacks (primary workflow)."""
    async with ComputeClient() as client:
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
        job = await client.media_thumbnail.generate(
            media=test_image,
            width=256,
            height=256,
            on_progress=on_progress,
            on_complete=on_complete,
        )
        
        # Wait for completion
        await asyncio.wait_for(completion_event.wait(), timeout=30.0)
        
        # Verify callbacks were called
        assert len(progress_updates) > 0, "No progress updates received"
        assert final_job is not None, "Completion callback not called"
        assert final_job.status == "completed"
        
        # Cleanup
        await client.delete_job(job.job_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_media_thumbnail_both_callbacks(test_image: Path):
    """Test that both on_progress and on_complete callbacks work."""
    async with ComputeClient() as client:
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
        
        job = await client.media_thumbnail.generate(
            media=test_image,
            width=128,
            height=128,
            on_progress=on_progress,
            on_complete=on_complete,
        )
        
        await asyncio.wait_for(completion_event.wait(), timeout=30.0)
        
        assert progress_called, "on_progress was not called"
        assert complete_called, "on_complete was not called"
        
        await client.delete_job(job.job_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_media_thumbnail_worker_capabilities(test_image: Path):
    """Test worker capability detection.

    Note: Workers broadcast capabilities on a heartbeat (default 30s).
    For faster tests, start worker with shorter heartbeat:
        WORKER_HEARTBEAT_INTERVAL=2 uv run compute-worker --worker-id test-worker --tasks media_thumbnail
    """
    async with ComputeClient() as client:
        # Wait for workers to broadcast (retry with timeout)
        max_wait = 35  # Slightly longer than default heartbeat
        check_interval = 1.0

        for i in range(int(max_wait / check_interval)):
            workers = client._mqtt.get_worker_capabilities()

            if len(workers) > 0:
                # Check if any worker has media_thumbnail capability
                has_thumbnail = any(
                    "media_thumbnail" in worker.capabilities
                    for worker in workers.values()
                )
                if has_thumbnail:
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
            "uv run compute-worker --worker-id test-worker --tasks media_thumbnail"
        )

        has_thumbnail = any(
            "media_thumbnail" in worker.capabilities
            for worker in workers.values()
        )
        assert has_thumbnail, (
            f"No worker with media_thumbnail capability. "
            f"Found workers: {list(workers.keys())} "
            f"with capabilities: {[w.capabilities for w in workers.values()]}"
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_media_thumbnail_file_download(test_image: Path):
    """Test downloading generated thumbnail file."""
    import tempfile
    
    async with ComputeClient() as client:
        # Generate thumbnail
        job = await client.media_thumbnail.generate(
            media=test_image,
            width=128,
            height=128,
            wait=True,
        )
        
        assert job.status == "completed"
        assert job.task_output is not None
        
        # Try to download the output file if path is in task_output
        # Note: This depends on server returning file path in task_output
        
        # Cleanup
        await client.delete_job(job.job_id)
