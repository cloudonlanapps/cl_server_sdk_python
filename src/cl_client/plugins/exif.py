"""EXIF metadata extraction plugin client."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from .base import BasePluginClient

if TYPE_CHECKING:
    from ..compute_client import ComputeClient
    from ..models import JobResponse


class ExifClient(BasePluginClient):
    """Client for EXIF metadata extraction.

    Extracts EXIF metadata from images including camera model, date, GPS, etc.
    """

    def __init__(self, client: ComputeClient) -> None:
        """Initialize EXIF client.

        Args:
            client: ComputeClient instance
        """
        super().__init__(client, task_type="exif")

    async def extract(
        self,
        image: Path,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: Callable[[JobResponse], None] | None = None,
        on_complete: Callable[[JobResponse], None] | None = None,
    ) -> JobResponse:
        """Extract EXIF metadata from image.

        Args:
            image: Path to image file
            wait: If True, use HTTP polling until completion (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates (MQTT, primary workflow)
            on_complete: Callback for job completion (MQTT, primary workflow)

        Returns:
            JobResponse with EXIF data in task_output (dict with camera, date, GPS, etc.)

        Example (MQTT callbacks - primary):
            job = await client.exif.extract(
                image=Path("photo.jpg"),
                on_complete=lambda j: print(f"Camera: {j.task_output.get('Make')}")
            )

        Example (HTTP polling - secondary):
            job = await client.exif.extract(
                image=Path("photo.jpg"),
                wait=True
            )
            exif_data = job.task_output
            print(f"Date: {exif_data.get('DateTime')}")
        """
        return await self.submit_with_files(
            files={"file": image},
            wait=wait,
            timeout=timeout,
            on_progress=on_progress,
            on_complete=on_complete,
        )
