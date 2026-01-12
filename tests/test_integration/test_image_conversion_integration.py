"""Integration tests for image_conversion plugin.

These tests require a running server, worker, and MQTT broker.
Tests run in multiple auth modes: admin, user-with-permission, user-no-permission, no-auth.
"""

import asyncio
import sys
from pathlib import Path
from pathlib import Path as PathlibPath
from typing import Any

import pytest
from httpx import HTTPStatusError

from cl_client import ComputeClient

sys.path.insert(0, str(PathlibPath(__file__).parent.parent))
from conftest import get_expected_error, should_succeed


@pytest.mark.integration
@pytest.mark.asyncio
async def test_image_conversion_http_polling(
    test_image: Path, client: ComputeClient, auth_config: dict[str, Any]
):
    """Test image conversion with HTTP polling (secondary workflow)."""
    if should_succeed(auth_config, operation_type="plugin"):
        # Should succeed - run normal assertions
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
    else:
        # Should fail - expect auth error
        expected_code = get_expected_error(auth_config, operation_type="plugin")
        with pytest.raises(HTTPStatusError) as exc_info:
            await client.image_conversion.convert(
                image=test_image,
                output_format="png",
                quality=90,
                wait=True,
                timeout=30.0,
            )
        assert exc_info.value.response.status_code == expected_code


@pytest.mark.integration
@pytest.mark.asyncio
async def test_image_conversion_mqtt_callbacks(
    test_image: Path, client: ComputeClient, auth_config: dict[str, Any]
):
    """Test image conversion with MQTT callbacks (primary workflow)."""
    if should_succeed(auth_config, operation_type="plugin"):
        # Should succeed - run normal assertions
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
    else:
        # Should fail - expect auth error
        expected_code = get_expected_error(auth_config, operation_type="plugin")
        with pytest.raises(HTTPStatusError) as exc_info:
            await client.image_conversion.convert(
                image=test_image,
                output_format="webp",
                quality=85,
                on_complete=lambda job: None,
            )
        assert exc_info.value.response.status_code == expected_code


@pytest.mark.integration
@pytest.mark.asyncio
async def test_image_conversion_multiple_formats(
    test_image: Path, client: ComputeClient, auth_config: dict[str, Any]
):
    """Test converting to multiple formats."""
    if should_succeed(auth_config, operation_type="plugin"):
        # Should succeed - run normal assertions
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
    else:
        # Should fail - expect auth error
        expected_code = get_expected_error(auth_config, operation_type="plugin")
        with pytest.raises(HTTPStatusError) as exc_info:
            await client.image_conversion.convert(
                image=test_image,
                output_format="png",
                wait=True,
                timeout=30.0,
            )
        assert exc_info.value.response.status_code == expected_code
