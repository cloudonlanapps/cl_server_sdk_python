"""Integration tests for image_conversion plugin.

These tests require a running server, worker, and MQTT broker.
Tests run in both no-auth and JWT modes via parametrized client fixture.
"""

import asyncio
from pathlib import Path

import pytest
from cl_client import ComputeClient




@pytest.mark.integration
@pytest.mark.asyncio
async def test_image_conversion_http_polling(test_image: Path, client: ComputeClient):
    """Test image conversion with HTTP polling (secondary workflow)."""
    job = await client.image_conversion.convert(
        image=test_image,
        output_format="png",
        quality=90,
        wait=True,
        timeout=30.0,
    )

    # Verify completion
    assert job.status == "completed"

    # image_conversion stores output in params, not task_output
    assert "output_path" in job.params
    assert "format" in job.params
    assert job.params["format"] == "png"

    await client.delete_job(job.job_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_image_conversion_mqtt_callbacks(test_image: Path, client: ComputeClient):
    """Test image conversion with MQTT callbacks (primary workflow)."""
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

    # MQTT callbacks don't include full params, fetch via HTTP
    full_job = await client.get_job(job.job_id)
    assert "output_path" in full_job.params
    assert full_job.params["format"] == "webp"

    await client.delete_job(job.job_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_image_conversion_multiple_formats(test_image: Path, client: ComputeClient):
    """Test converting to multiple formats."""
    formats = ["png", "webp"]

    for fmt in formats:
        job = await client.image_conversion.convert(
            image=test_image,
            output_format=fmt,
            wait=True,
            timeout=30.0,
        )

        assert job.status == "completed"
        # image_conversion stores output in params, not task_output
        assert "output_path" in job.params
        assert job.params["format"] == fmt

        await client.delete_job(job.job_id)
