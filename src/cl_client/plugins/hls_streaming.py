"""HLS streaming plugin client."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .base import BasePluginClient

if TYPE_CHECKING:
    from ..compute_client import ComputeClient
    from ..models import JobResponse, OnJobResponseCallback


class HlsStreamingClient(BasePluginClient):
    """Client for HLS streaming manifest generation.

    Converts videos to HLS format with adaptive bitrate streaming support.
    """

    def __init__(self, client: ComputeClient) -> None:
        """Initialize HLS streaming client.

        Args:
            client: ComputeClient instance
        """
        super().__init__(client, task_type="hls_streaming")

    async def generate_manifest(
        self,
        video: Path,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: OnJobResponseCallback = None,
        on_complete: OnJobResponseCallback = None,
    ) -> JobResponse:
        """Generate HLS streaming manifest from video.

        Args:
            video: Path to video file
            wait: If True, use HTTP polling until completion (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates (MQTT, primary workflow)
            on_complete: Callback for job completion (MQTT, primary workflow)

        Returns:
            JobResponse with manifest path in task_output["manifest_path"]

        Example (MQTT callbacks - primary):
            job = await client.hls_streaming.generate_manifest(
                video=Path("video.mp4"),
                on_complete=lambda j: print(f"Manifest: {j.task_output['manifest_path']}")
            )

        Example (HTTP polling - secondary):
            job = await client.hls_streaming.generate_manifest(
                video=Path("video.mp4"),
                wait=True
            )
            manifest = job.task_output["manifest_path"]
            print(f"HLS manifest ready: {manifest}")
        """
        return await self.submit_with_files(
            files={"file": video},
            wait=wait,
            timeout=timeout,
            on_progress=on_progress,
            on_complete=on_complete,
        )
