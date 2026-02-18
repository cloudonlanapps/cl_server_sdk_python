"""HLS streaming plugin client."""

from __future__ import annotations

from pathlib import Path

from ..models import JobResponse, OnJobResponseCallback
from .base import BasePluginClient, ClientProtocol


class HlsStreamingClient(BasePluginClient):
    """Client for HLS streaming manifest generation.

    Converts videos to HLS format with adaptive bitrate streaming support.
    """

    def __init__(self, client: ClientProtocol) -> None:
        """Initialize HLS streaming client.

        Args:
            client: ComputeClient instance
        """
        super().__init__(client, task_type="hls_streaming")

    async def generate_manifest(
        self,
        video: Path | None = None,
        input_absolute_path: str | None = None,
        output_absolute_path: str | None = None,
        include_original: bool = True,
        priority: int = 5,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: OnJobResponseCallback = None,
        on_complete: OnJobResponseCallback = None,
    ) -> JobResponse:
        """Generate HLS streaming manifest from video.

        Args:
            video: Path to video file (if uploading)
            input_absolute_path: Absolute path to input video on worker filesystem
            output_absolute_path: Absolute path to output directory on worker filesystem
            include_original: Whether to include original quality without transcoding
            priority: Job priority (0-10, lower is higher)
            wait: If True, use HTTP polling until completion (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates (MQTT, primary workflow)
            on_complete: Callback for job completion (MQTT, primary workflow)

        Returns:
            JobResponse with manifest path
        """
        params = {
            "include_original": str(include_original).lower(),
        }
        if input_absolute_path:
            params["input_absolute_path"] = input_absolute_path
        if output_absolute_path:
            params["output_absolute_path"] = output_absolute_path

        if video:
            return await self.submit_with_files(
                files={"file": video},
                params=params,
                priority=priority,
                wait=wait,
                timeout=timeout,
                on_progress=on_progress,
                on_complete=on_complete,
            )
        else:
            return await self.submit_job(
                params=params,
                priority=priority,
                wait=wait,
                timeout=timeout,
                on_progress=on_progress,
                on_complete=on_complete,
            )
