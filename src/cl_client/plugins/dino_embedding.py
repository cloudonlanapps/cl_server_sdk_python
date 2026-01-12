"""DINO embedding plugin client."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .base import BasePluginClient

if TYPE_CHECKING:
    from ..compute_client import ComputeClient
    from ..models import JobResponse, OnJobResponseCallback


class DinoEmbeddingClient(BasePluginClient):
    """Client for DINO image embeddings.

    Generates 384-dimensional DINO embeddings from images using Facebook's DINO model.
    """

    def __init__(self, client: ComputeClient) -> None:
        """Initialize DINO embedding client.

        Args:
            client: ComputeClient instance
        """
        super().__init__(client, task_type="dino_embedding")

    async def embed_image(
        self,
        image: Path,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: OnJobResponseCallback = None,
        on_complete: OnJobResponseCallback = None,
    ) -> JobResponse:
        """Generate DINO embedding from image.

        Args:
            image: Path to image file
            wait: If True, use HTTP polling until completion (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates (MQTT, primary workflow)
            on_complete: Callback for job completion (MQTT, primary workflow)

        Returns:
            JobResponse with embedding in task_output["embedding"] (384-dimensional list)

        Example (MQTT callbacks - primary):
            job = await client.dino_embedding.embed_image(
                image=Path("photo.jpg"),
                on_complete=lambda j: print(f"Embedding: {j.task_output['embedding'][:5]}...")
            )

        Example (HTTP polling - secondary):
            job = await client.dino_embedding.embed_image(
                image=Path("photo.jpg"),
                wait=True
            )
            embedding = job.task_output["embedding"]
            print(f"Generated {len(embedding)}-dim embedding")
        """
        return await self.submit_with_files(
            files={"file": image},
            wait=wait,
            timeout=timeout,
            on_progress=on_progress,
            on_complete=on_complete,
        )
