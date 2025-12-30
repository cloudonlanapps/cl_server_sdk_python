"""CLIP embedding plugin client."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from .base import BasePluginClient

if TYPE_CHECKING:
    from ..compute_client import ComputeClient
    from ..models import JobResponse


class ClipEmbeddingClient(BasePluginClient):
    """Client for CLIP image embeddings.

    Generates 512-dimensional CLIP embeddings from images using OpenAI's CLIP model.
    """

    def __init__(self, client: ComputeClient) -> None:
        """Initialize CLIP embedding client.

        Args:
            client: ComputeClient instance
        """
        super().__init__(client, task_type="clip_embedding")

    async def embed_image(
        self,
        image: Path,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: Callable[[JobResponse], None] | None = None,
        on_complete: Callable[[JobResponse], None] | None = None,
    ) -> JobResponse:
        """Generate CLIP embedding from image.

        Args:
            image: Path to image file
            wait: If True, use HTTP polling until completion (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates (MQTT, primary workflow)
            on_complete: Callback for job completion (MQTT, primary workflow)

        Returns:
            JobResponse with embedding in task_output["embedding"] (512-dimensional list)

        Example (MQTT callbacks - primary):
            job = await client.clip_embedding.embed_image(
                image=Path("photo.jpg"),
                on_complete=lambda j: print(f"Embedding: {j.task_output['embedding'][:5]}...")
            )

        Example (HTTP polling - secondary):
            job = await client.clip_embedding.embed_image(
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
