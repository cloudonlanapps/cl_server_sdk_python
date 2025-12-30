"""Face detection plugin client."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from .base import BasePluginClient

if TYPE_CHECKING:
    from ..compute_client import ComputeClient
    from ..models import JobResponse


class FaceDetectionClient(BasePluginClient):
    """Client for face detection.

    Detects faces in images and returns bounding boxes with confidence scores.
    """

    def __init__(self, client: ComputeClient) -> None:
        """Initialize face detection client.

        Args:
            client: ComputeClient instance
        """
        super().__init__(client, task_type="face_detection")

    async def detect(
        self,
        image: Path,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: Callable[[JobResponse], None] | None = None,
        on_complete: Callable[[JobResponse], None] | None = None,
    ) -> JobResponse:
        """Detect faces in image.

        Args:
            image: Path to image file
            wait: If True, use HTTP polling until completion (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates (MQTT, primary workflow)
            on_complete: Callback for job completion (MQTT, primary workflow)

        Returns:
            JobResponse with faces in task_output["faces"] (list of bounding boxes)

        Example (MQTT callbacks - primary):
            job = await client.face_detection.detect(
                image=Path("photo.jpg"),
                on_complete=lambda j: print(f"Found {len(j.task_output['faces'])} faces")
            )

        Example (HTTP polling - secondary):
            job = await client.face_detection.detect(
                image=Path("photo.jpg"),
                wait=True
            )
            faces = job.task_output["faces"]
            for face in faces:
                print(f"Face at ({face['x']}, {face['y']})")
        """
        return await self.submit_with_files(
            files={"file": image},
            wait=wait,
            timeout=timeout,
            on_progress=on_progress,
            on_complete=on_complete,
        )
