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

    Detects faces in images and returns bounding boxes, confidence scores,
    facial landmarks (5 keypoints), and cropped face images.
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
            JobResponse with faces in task_output["faces"]. Each face includes:
            - bbox: Normalized bounding box (x1, y1, x2, y2 in [0.0, 1.0])
            - confidence: Detection confidence score [0.0, 1.0]
            - landmarks: Five facial keypoints (right_eye, left_eye, nose_tip, mouth_right, mouth_left)
            - file_path: Path to cropped face image (downloadable via download_job_file)

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
            for face in job.task_output["faces"]:
                bbox = face["bbox"]
                print(f"Face at ({bbox['x1']}, {bbox['y1']}) confidence: {face['confidence']}")

                # Access landmarks
                landmarks = face["landmarks"]
                print(f"  Right eye: {landmarks['right_eye']}")

                # Download cropped face
                await client.download_job_file(job.job_id, face["file_path"], Path("face.png"))
        """
        return await self.submit_with_files(
            files={"file": image},
            wait=wait,
            timeout=timeout,
            on_progress=on_progress,
            on_complete=on_complete,
        )
