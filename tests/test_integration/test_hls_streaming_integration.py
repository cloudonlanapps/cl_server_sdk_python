"""Integration tests for hls_streaming plugin.

These tests require a running server, worker, and MQTT broker.
Note: HLS streaming requires video files and ffmpeg.
"""

import asyncio
from pathlib import Path

import pytest
from cl_client import ComputeClient


@pytest.fixture
def test_video() -> Path:
    """Get test video path."""
    locations = [
        Path("/Users/anandasarangaram/Work/videos"),
        Path("/Users/anandasarangaram/Work/test_media/videos"),
        Path.home() / "Work" / "videos",
    ]

    for loc in locations:
        if loc.exists():
            videos = list(loc.glob("*.mp4"))
            if videos:
                return videos[0]

    pytest.skip("No test videos found. Please provide test videos.")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hls_streaming_http_polling(test_video: Path):
    """Test HLS streaming with HTTP polling (secondary workflow)."""
    async with ComputeClient() as client:
        job = await client.hls_streaming.generate_manifest(
            video=test_video,
            wait=True,
            timeout=60.0,  # HLS generation may take longer
        )

        # Verify completion
        assert job.status == "completed"
        assert job.task_output is not None

        # Should have manifest_path
        assert "manifest_path" in job.task_output

        await client.delete_job(job.job_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hls_streaming_mqtt_callbacks(test_video: Path):
    """Test HLS streaming with MQTT callbacks (primary workflow)."""
    async with ComputeClient() as client:
        assert client._mqtt._connected, "MQTT not connected"

        completion_event = asyncio.Event()
        final_job = None

        def on_complete(job):
            nonlocal final_job
            final_job = job
            completion_event.set()

        job = await client.hls_streaming.generate_manifest(
            video=test_video,
            on_complete=on_complete,
        )

        await asyncio.wait_for(completion_event.wait(), timeout=60.0)

        assert final_job is not None
        assert final_job.status == "completed"
        assert "manifest_path" in final_job.task_output

        await client.delete_job(job.job_id)
