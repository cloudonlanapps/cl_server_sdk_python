"""Media thumbnail generation plugin client."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .base import BasePluginClient

if TYPE_CHECKING:
    from ..compute_client import ComputeClient
    from ..models import JobResponse, OnJobResponseCallback


class MediaThumbnailClient(BasePluginClient):
    """Client for media thumbnail generation.

    Generates thumbnails from images and videos with specified dimensions.
    """

    def __init__(self, client: ComputeClient) -> None:
        """Initialize media thumbnail client.

        Args:
            client: ComputeClient instance
        """
        super().__init__(client, task_type="media_thumbnail")

    async def generate(
        self,
        media: Path,
        width: int | None = None,
        height: int | None = None,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: OnJobResponseCallback = None,
        on_complete: OnJobResponseCallback = None,
    ) -> JobResponse:
        """Generate thumbnail from media file (image or video).

        Args:
            media: Path to media file (image or video)
            width: Target width in pixels (optional, maintains aspect ratio if only one dimension specified)
            height: Target height in pixels (optional, maintains aspect ratio if only one dimension specified)
            wait: If True, use HTTP polling until completion (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates (MQTT, primary workflow)
            on_complete: Callback for job completion (MQTT, primary workflow)

        Returns:
            JobResponse with thumbnail path in task_output["thumbnail_path"]

        Example (MQTT callbacks - primary):
            job = await client.media_thumbnail.generate(
                media=Path("video.mp4"),
                width=256,
                height=256,
                on_complete=lambda j: print(f"Thumbnail: {j.task_output['thumbnail_path']}")
            )

        Example (HTTP polling - secondary):
            job = await client.media_thumbnail.generate(
                media=Path("video.mp4"),
                width=256,
                height=256,
                wait=True
            )
            print(f"Thumbnail: {job.task_output['thumbnail_path']}")
        """
        params: dict[str, object] = {}
        if width is not None:
            params["width"] = width
        if height is not None:
            params["height"] = height

        return await self.submit_with_files(
            files={"file": media},
            params=params,
            wait=wait,
            timeout=timeout,
            on_progress=on_progress,
            on_complete=on_complete,
        )
