"""Integration tests for hls_streaming plugin.

These tests require a running server, worker, and MQTT broker.
Tests run in both no-auth and JWT modes via parametrized client fixture.
Note: HLS streaming requires video files and ffmpeg.
"""

import asyncio
from pathlib import Path

import pytest
from cl_client import ComputeClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hls_streaming_http_polling(test_video_1080p: Path, client: ComputeClient):
    """Test HLS streaming with HTTP polling (secondary workflow)."""
    job = await client.hls_streaming.generate_manifest(
        video=test_video_1080p,
        wait=True,
        timeout=60.0,  # HLS generation may take longer
    )

    # Verify completion
    assert job.status == "completed"
    assert job.task_output is not None

    # Should have master_playlist
    assert "master_playlist" in job.task_output
    assert "variants_generated" in job.task_output

    await client.delete_job(job.job_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hls_streaming_mqtt_callbacks(test_video_1080p: Path, client: ComputeClient):
    """Test HLS streaming with MQTT callbacks (primary workflow)."""
    assert client._mqtt._connected, "MQTT not connected"

    completion_event = asyncio.Event()
    final_job = None

    def on_complete(job):
        nonlocal final_job
        final_job = job
        completion_event.set()

    job = await client.hls_streaming.generate_manifest(
        video=test_video_1080p,
        on_complete=on_complete,
    )

    await asyncio.wait_for(completion_event.wait(), timeout=60.0)

    assert final_job is not None
    assert final_job.status == "completed"

    # MQTT callbacks don't include task_output, fetch via HTTP
    full_job = await client.get_job(job.job_id)
    assert "master_playlist" in full_job.task_output
    assert "variants_generated" in full_job.task_output

    await client.delete_job(job.job_id)
