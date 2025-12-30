"""Face embedding plugin client."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from .base import BasePluginClient

if TYPE_CHECKING:
    from ..compute_client import ComputeClient
    from ..models import JobResponse


class FaceEmbeddingClient(BasePluginClient):
    """Client for face embeddings.

    Generates 128-dimensional face embeddings for face recognition and similarity matching.
    """

    def __init__(self, client: ComputeClient) -> None:
        """Initialize face embedding client.

        Args:
            client: ComputeClient instance
        """
        super().__init__(client, task_type="face_embedding")

    async def embed_faces(
        self,
        image: Path,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: Callable[[JobResponse], None] | None = None,
        on_complete: Callable[[JobResponse], None] | None = None,
    ) -> JobResponse:
        """Generate face embeddings from image.

        Args:
            image: Path to image file
            wait: If True, use HTTP polling until completion (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates (MQTT, primary workflow)
            on_complete: Callback for job completion (MQTT, primary workflow)

        Returns:
            JobResponse with embeddings in task_output["embeddings"] (list of 128-dim vectors)

        Example (MQTT callbacks - primary):
            job = await client.face_embedding.embed_faces(
                image=Path("photo.jpg"),
                on_complete=lambda j: print(f"Found {len(j.task_output['embeddings'])} faces")
            )

        Example (HTTP polling - secondary):
            job = await client.face_embedding.embed_faces(
                image=Path("photo.jpg"),
                wait=True
            )
            embeddings = job.task_output["embeddings"]
            for emb in embeddings:
                print(f"Face embedding: {len(emb)}-dimensional")
        """
        return await self.submit_with_files(
            files={"file": image},
            wait=wait,
            timeout=timeout,
            on_progress=on_progress,
            on_complete=on_complete,
        )
