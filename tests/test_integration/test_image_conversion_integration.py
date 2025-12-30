"""Integration tests for image_conversion plugin.

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
async def test_image_conversion_http_polling(test_image: Path):
    """Test image conversion with HTTP polling (secondary workflow)."""
    async with ComputeClient() as client:
        job = await client.image_conversion.convert(
            image=test_image,
            output_format="png",
            quality=90,
            wait=True,
            timeout=30.0,
        )

        # Verify completion
        assert job.status == "completed"
        assert job.task_output is not None

        # Should have output_path
        assert "output_path" in job.task_output

        await client.delete_job(job.job_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_image_conversion_mqtt_callbacks(test_image: Path):
    """Test image conversion with MQTT callbacks (primary workflow)."""
    async with ComputeClient() as client:
        assert client._mqtt._connected, "MQTT not connected"

        completion_event = asyncio.Event()
        final_job = None

        def on_complete(job):
            nonlocal final_job
            final_job = job
            completion_event.set()

        job = await client.image_conversion.convert(
            image=test_image,
            output_format="webp",
            quality=85,
            on_complete=on_complete,
        )

        await asyncio.wait_for(completion_event.wait(), timeout=30.0)

        assert final_job is not None
        assert final_job.status == "completed"
        assert "output_path" in final_job.task_output

        await client.delete_job(job.job_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_image_conversion_multiple_formats(test_image: Path):
    """Test converting to multiple formats."""
    async with ComputeClient() as client:
        formats = ["png", "webp"]

        for fmt in formats:
            job = await client.image_conversion.convert(
                image=test_image,
                output_format=fmt,
                wait=True,
                timeout=30.0,
            )

            assert job.status == "completed"
            assert "output_path" in job.task_output

            await client.delete_job(job.job_id)
