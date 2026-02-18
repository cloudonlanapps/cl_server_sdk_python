"""Base plugin client for job submission.

Provides common functionality for all plugin clients:
- Job submission with file uploads
- MQTT callback-based monitoring (primary)
- Optional HTTP polling (secondary)
- Configuration-based endpoint lookup
"""

from __future__ import annotations

from collections.abc import Awaitable
from pathlib import Path
from typing import Protocol

from httpx._types import RequestData, RequestFiles

from ..config import ComputeClientConfig
from ..http_utils import HttpUtils
from ..models import JobResponse, OnJobResponseCallback


class ClientProtocol(Protocol):
    def http_submit_job(
        self,
        endpoint: str,
        data: RequestData | None,
        files: RequestFiles | None,
    ) -> Awaitable[str]: ...

    def get_job(self, job_id: str) -> Awaitable[JobResponse]: ...
    def wait_for_job(
        self,
        job_id: str,
        poll_interval: float | None = None,
        timeout: float | None = None,
    ) -> Awaitable[JobResponse]: ...

    def mqtt_subscribe_job_updates(
        self,
        job_id: str,
        on_progress: OnJobResponseCallback = None,
        on_complete: OnJobResponseCallback = None,
        task_type: str = "unknown",
    ) -> str: ...

    pass


class BasePluginClient:
    """Base class for plugin-specific clients.

    Each plugin client extends this to provide typed, plugin-specific methods.
    Handles job submission, file uploads, and monitoring.
    """

    def __init__(self, client: ClientProtocol, task_type: str) -> None:
        """Initialize plugin client.

        Args:
            client: ClientProtocol instance
            task_type: Plugin task type (used to lookup endpoint from config)
        """
        self.client: ClientProtocol = client
        self.task_type: str = task_type

        # Get endpoint from config (NOT hardcoded)
        self.endpoint: str = ComputeClientConfig.get_plugin_endpoint(task_type)

    async def submit_job(
        self,
        params: dict[str, object] | None = None,
        priority: int = 5,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: OnJobResponseCallback = None,
        on_complete: OnJobResponseCallback = None,
    ) -> JobResponse:
        """Submit job without file uploads.

        Args:
            params: Task parameters (plugin-specific)
            priority: Job priority (0-10)
            wait: If True, use HTTP polling until completion (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates (primary workflow)
            on_complete: Callback for job completion (primary workflow)

        Returns:
            JobResponse with job details
        """

        # Submit job (accessing protected _session is intentional for plugin clients)
        job_id = await self.client.http_submit_job(  # type: ignore[reportPrivateUsage]
            self.endpoint,
            files=None,
            data=HttpUtils.build_form_data(params, priority),
        )

        # Fetch full job details (submission response may be minimal)
        job = await self.client.get_job(job_id)

        # Subscribe to MQTT callbacks if provided
        if on_progress or on_complete:
            _ = self.client.mqtt_subscribe_job_updates(
                job_id=job.job_id,
                on_progress=on_progress,
                on_complete=on_complete,
                task_type=self.task_type,
            )

        # Wait for completion if requested (secondary workflow)
        if wait:
            job = await self.client.wait_for_job(job_id=job.job_id, timeout=timeout)

        return job

    async def submit_with_files(
        self,
        files: dict[str, Path],
        params: dict[str, object] | None = None,
        priority: int = 5,
        wait: bool = False,
        timeout: float | None = None,
        on_progress: OnJobResponseCallback = None,
        on_complete: OnJobResponseCallback = None,
    ) -> JobResponse:
        """Submit job with file uploads (PRIMARY METHOD).

        Uploads files via multipart/form-data and optionally monitors completion.
        Uses MQTT callbacks (primary) or HTTP polling (secondary) based on parameters.

        Args:
            files: Dict mapping field names to file paths (e.g., {"image": Path("img.jpg")})
            params: Additional task parameters (plugin-specific)
            priority: Job priority (0-10)
            wait: If True, use HTTP polling until completion (secondary workflow)
            timeout: Timeout for wait (optional)
            on_progress: Callback for job progress updates (MQTT, primary workflow)
            on_complete: Callback for job completion (MQTT, primary workflow)

        Returns:
            JobResponse with job details
            - If wait=True: Returns final job status (completed/failed)
            - If callbacks provided: Returns initial job status, callbacks invoked later
            - Otherwise: Returns initial job status (queued)

        Raises:
            FileNotFoundError: If any file doesn't exist
            httpx.HTTPStatusError: If request fails

        Example (MQTT callbacks - primary):
            job = await client.media_thumbnail.generate(
                media=Path("video.mp4"),
                width=256,
                height=256,
                on_complete=lambda j: print(f"Done: {j.status}")
            )

        Example (HTTP polling - secondary):
            job = await client.media_thumbnail.generate(
                media=Path("video.mp4"),
                width=256,
                height=256,
                wait=True,
                timeout=30.0
            )
        """

        # Prepare form data
        multipart = HttpUtils.open_multipart_files(files)
        try:
            # Submit job (accessing protected _session is intentional for plugin clients)
            job_id = await self.client.http_submit_job(  # type: ignore[reportPrivateUsage]
                self.endpoint,
                files=multipart,  # type: ignore[arg-type]
                data=HttpUtils.build_form_data(params, priority),
            )

            # Fetch full job details (submission response may be minimal)
            job = await self.client.get_job(job_id)

            # Subscribe to MQTT callbacks if provided
            if on_progress or on_complete:
                _ = self.client.mqtt_subscribe_job_updates(
                    job_id=job.job_id,
                    on_progress=on_progress,
                    on_complete=on_complete,
                    task_type=self.task_type,
                )

            # Wait for completion if requested (secondary workflow)
            if wait:
                job = await self.client.wait_for_job(job_id=job.job_id, timeout=timeout)

            return job

        finally:
            HttpUtils.close_multipart_files(multipart)
