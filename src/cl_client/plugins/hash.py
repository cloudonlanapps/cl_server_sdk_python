"""Perceptual hash plugin client."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .base import BasePluginClient

if TYPE_CHECKING:
    from ..compute_client import ComputeClient
    from ..models import JobResponse, OnJobResponseCallback


class HashClient(BasePluginClient):
    """Client for perceptual image hashing.

    Computes perceptual hashes (phash, dhash) for duplicate detection and similarity matching.
    """

    def __init__(self, client: ComputeClient) -> None:
        """Initialize hash client.

        Args:
            client: ComputeClient instance
        """
        super().__init__(client, task_type="hash")

    async def compute(
        self,
        image: Path,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: OnJobResponseCallback = None,
        on_complete: OnJobResponseCallback = None,
    ) -> JobResponse:
        """Compute perceptual hashes from image.

        Args:
            image: Path to image file
            wait: If True, use HTTP polling until completion (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates (MQTT, primary workflow)
            on_complete: Callback for job completion (MQTT, primary workflow)

        Returns:
            JobResponse with hashes in task_output (dict with phash, dhash, etc.)

        Example (MQTT callbacks - primary):
            job = await client.hash.compute(
                image=Path("photo.jpg"),
                on_complete=lambda j: print(f"phash: {j.task_output['phash']}")
            )

        Example (HTTP polling - secondary):
            job = await client.hash.compute(
                image=Path("photo.jpg"),
                wait=True
            )
            hashes = job.task_output
            print(f"phash: {hashes['phash']}")
            print(f"dhash: {hashes['dhash']}")
        """
        return await self.submit_with_files(
            files={"file": image},
            wait=wait,
            timeout=timeout,
            on_progress=on_progress,
            on_complete=on_complete,
        )
