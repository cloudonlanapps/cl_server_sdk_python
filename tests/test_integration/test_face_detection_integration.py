"""Integration tests for face_detection plugin.

These tests require a running server, worker, and MQTT broker.
"""

import asyncio
from pathlib import Path

import pytest
from cl_client import ComputeClient




@pytest.mark.integration
@pytest.mark.asyncio
async def test_face_detection_http_polling(test_image: Path):
    """Test face detection with HTTP polling (secondary workflow)."""
    async with ComputeClient() as client:
        job = await client.face_detection.detect(
            image=test_image,
            wait=True,
            timeout=30.0,
        )

        # Verify completion
        assert job.status == "completed"
        assert job.task_output is not None

        # Should have faces list (may be empty if no faces)
        assert "faces" in job.task_output
        assert isinstance(job.task_output["faces"], list)

        await client.delete_job(job.job_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_face_detection_mqtt_callbacks(test_image: Path):
    """Test face detection with MQTT callbacks (primary workflow)."""
    async with ComputeClient() as client:
        assert client._mqtt._connected, "MQTT not connected"

        completion_event = asyncio.Event()
        final_job = None

        def on_complete(job):
            nonlocal final_job
            final_job = job
            completion_event.set()

        job = await client.face_detection.detect(
            image=test_image,
            on_complete=on_complete,
        )

        await asyncio.wait_for(completion_event.wait(), timeout=30.0)

        assert final_job is not None
        assert final_job.status == "completed"

        # MQTT callbacks don't include task_output, fetch via HTTP
        full_job = await client.get_job(job.job_id)
        assert "faces" in full_job.task_output

        await client.delete_job(job.job_id)
