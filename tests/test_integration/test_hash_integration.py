"""Integration tests for hash plugin.

These tests require a running server, worker, and MQTT broker.
"""

import asyncio
from pathlib import Path

import pytest
from cl_client import ComputeClient


@pytest.fixture
def test_image() -> Path:
    """Get test image path."""
    locations = [
        Path("/Users/anandasarangaram/Work/images"),
        Path("/Users/anandasarangaram/Work/test_media/images"),
        Path.home() / "Work" / "images",
    ]

    for loc in locations:
        if loc.exists():
            images = list(loc.glob("*.jpg"))
            if images:
                return images[0]

    pytest.skip("No test images found. Please provide test images.")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hash_http_polling(test_image: Path):
    """Test perceptual hash with HTTP polling (secondary workflow)."""
    async with ComputeClient() as client:
        job = await client.hash.compute(
            image=test_image,
            wait=True,
            timeout=30.0,
        )

        # Verify completion
        assert job.status == "completed"
        assert job.task_output is not None

        # Should have hash values (phash, dhash, etc.)
        assert isinstance(job.task_output, dict)
        # Typically includes: phash, dhash, average_hash, etc.

        await client.delete_job(job.job_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hash_mqtt_callbacks(test_image: Path):
    """Test perceptual hash with MQTT callbacks (primary workflow)."""
    async with ComputeClient() as client:
        assert client._mqtt._connected, "MQTT not connected"

        completion_event = asyncio.Event()
        final_job = None

        def on_complete(job):
            nonlocal final_job
            final_job = job
            completion_event.set()

        job = await client.hash.compute(
            image=test_image,
            on_complete=on_complete,
        )

        await asyncio.wait_for(completion_event.wait(), timeout=30.0)

        assert final_job is not None
        assert final_job.status == "completed"

        # MQTT callbacks don't include task_output, fetch via HTTP
        full_job = await client.get_job(job.job_id)
        assert isinstance(full_job.task_output, dict)

        await client.delete_job(job.job_id)
