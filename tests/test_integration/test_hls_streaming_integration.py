"""Integration tests for hls_streaming plugin.

These tests require a running server, worker, and MQTT broker.
Tests run in multiple auth modes: admin, user-with-permission, user-no-permission, no-auth.
Note: HLS streaming requires video files and ffmpeg.
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
async def test_hls_streaming_http_polling(
    test_video_1080p: Path, client: ComputeClient, auth_config: dict[str, Any]
):
    """Test HLS streaming with HTTP polling (secondary workflow)."""
    if should_succeed(auth_config, operation_type="plugin"):
        # Should succeed - run normal assertions
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
    else:
        # Should fail - expect auth error
        expected_code = get_expected_error(auth_config, operation_type="plugin")
        with pytest.raises(HTTPStatusError) as exc_info:
            await client.hls_streaming.generate_manifest(
                video=test_video_1080p,
                wait=True,
                timeout=60.0,
            )
        assert exc_info.value.response.status_code == expected_code


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hls_streaming_mqtt_callbacks(
    test_video_1080p: Path, client: ComputeClient, auth_config: dict[str, Any]
):
    """Test HLS streaming with MQTT callbacks (primary workflow)."""
    if should_succeed(auth_config, operation_type="plugin"):
        # Should succeed - run normal assertions
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
    else:
        # Should fail - expect auth error
        expected_code = get_expected_error(auth_config, operation_type="plugin")
        with pytest.raises(HTTPStatusError) as exc_info:
            await client.hls_streaming.generate_manifest(
                video=test_video_1080p,
                on_complete=lambda job: None,
            )
        assert exc_info.value.response.status_code == expected_code
