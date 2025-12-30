"""Image format conversion plugin client."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from .base import BasePluginClient

if TYPE_CHECKING:
    from ..compute_client import ComputeClient
    from ..models import JobResponse


class ImageConversionClient(BasePluginClient):
    """Client for image format conversion.

    Converts images between formats (JPEG, PNG, WebP, etc.) with optional quality settings.
    """

    def __init__(self, client: ComputeClient) -> None:
        """Initialize image conversion client.

        Args:
            client: ComputeClient instance
        """
        super().__init__(client, task_type="image_conversion")

    async def convert(
        self,
        image: Path,
        output_format: str,
        quality: int | None = None,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: Callable[[JobResponse], None] | None = None,
        on_complete: Callable[[JobResponse], None] | None = None,
    ) -> JobResponse:
        """Convert image to different format.

        Args:
            image: Path to image file
            output_format: Target format (e.g., "jpg", "png", "webp")
            quality: Quality for lossy formats (1-100, optional)
            wait: If True, use HTTP polling until completion (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates (MQTT, primary workflow)
            on_complete: Callback for job completion (MQTT, primary workflow)

        Returns:
            JobResponse with converted image path in task_output["output_path"]

        Example (MQTT callbacks - primary):
            job = await client.image_conversion.convert(
                image=Path("photo.png"),
                output_format="jpg",
                quality=90,
                on_complete=lambda j: print(f"Converted: {j.task_output['output_path']}")
            )

        Example (HTTP polling - secondary):
            job = await client.image_conversion.convert(
                image=Path("photo.png"),
                output_format="webp",
                quality=85,
                wait=True
            )
            output_path = job.task_output["output_path"]
            print(f"Converted to WebP: {output_path}")
        """
        params: dict[str, object] = {"format": output_format}
        if quality is not None:
            params["quality"] = quality

        return await self.submit_with_files(
            files={"file": image},
            params=params,
            wait=wait,
            timeout=timeout,
            on_progress=on_progress,
            on_complete=on_complete,
        )
